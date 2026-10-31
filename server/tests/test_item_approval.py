"""Approval-gate tests that never contact an external tracker."""

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID

from fastapi.testclient import TestClient
import pytest

from app.agents.action import execute_approved_action
from app.main import app
from app.routers import items as item_routes
from app.routers.meetings import get_supabase_client

ITEM_ID = "00000000-0000-0000-0000-000000000050"
MEETING_ID = "00000000-0000-0000-0000-000000000010"


class FakeQuery:
    """Small in-memory implementation of item reads and state updates."""

    def __init__(self, client: "FakeSupabase", table_name: str) -> None:
        self.client = client
        self.table_name = table_name
        self.filters: dict[str, str] = {}
        self.updated_values: dict[str, object] | None = None
        self.inserted_values: list[dict[str, object]] | None = None

    def select(self, _: str) -> "FakeQuery":
        return self

    def order(self, _: str, *, desc: bool = False) -> "FakeQuery":
        del desc
        return self

    def or_(self, _: str) -> "FakeQuery":
        return self

    def eq(self, column: str, value: str) -> "FakeQuery":
        self.filters[column] = value
        return self

    def update(self, values: dict[str, object]) -> "FakeQuery":
        self.updated_values = values
        return self

    def insert(self, values: list[dict[str, object]]) -> "FakeQuery":
        self.inserted_values = values
        return self

    async def execute(self) -> SimpleNamespace:
        rows = self.client.rows[self.table_name]
        if self.inserted_values is not None:
            rows.extend(self.inserted_values)
            return SimpleNamespace(data=self.inserted_values)
        if self.updated_values is not None:
            for row in rows:
                if all(str(row.get(key)) == value for key, value in self.filters.items()):
                    row.update(self.updated_values)
        filtered = [
            row
            for row in rows
            if all(str(row.get(key)) == value for key, value in self.filters.items())
        ]
        return SimpleNamespace(data=filtered)


class FakeSupabase:
    """Database double for one pending action and its owner lookup."""

    def __init__(self) -> None:
        self.rows: dict[str, list[dict[str, object]]] = {
            "items": [
                {
                    "id": ITEM_ID,
                    "meeting_id": MEETING_ID,
                    "type": "action",
                    "topic": "Launch",
                    "text": "Prepare the launch plan.",
                    "owner_id": None,
                    "deadline": None,
                    "confidence": 0.9,
                    "source_quote": "Rahul: I will prepare the launch plan.",
                    "speaker": "Rahul",
                    "status": "pending",
                    "tracker_ref": None,
                    "created_at": datetime.now(UTC).isoformat(),
                }
            ],
            "members": [],
            "reminders": [],
        }

    def table(self, table_name: str) -> FakeQuery:
        return FakeQuery(self, table_name)


class FakeTracker:
    """Records task creation requests without external network access."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def create_task(self, title: str, description: str) -> str:
        self.calls.append((title, description))
        return "https://tracker.example/tasks/1"


def test_action_agent_refuses_unapproved_items() -> None:
    """The action agent checks persisted approval before using the tracker."""
    supabase = FakeSupabase()
    tracker = FakeTracker()
    item_id = UUID(ITEM_ID)

    with pytest.raises(ValueError, match="must be approved"):
        asyncio.run(execute_approved_action(supabase, item_id, tracker))  # type: ignore[arg-type]
    assert tracker.calls == []

    supabase.rows["items"][0]["status"] = "approved"
    reference = asyncio.run(execute_approved_action(supabase, item_id, tracker))  # type: ignore[arg-type]
    assert reference == "https://tracker.example/tasks/1"
    assert tracker.calls[0][0] == "Prepare the launch plan."
    assert "Rahul: I will prepare the launch plan." in tracker.calls[0][1]
    assert supabase.rows["items"][0]["tracker_ref"] == reference


def test_tracker_action_runs_only_after_explicit_approval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Listing pending work does not post; approving it records state first."""
    supabase = FakeSupabase()
    calls: list[str] = []
    tracker = object()

    async def fake_execute_approved_action(
        client: object,
        item_id: UUID,
        adapter: object | None = None,
    ) -> str:
        del client
        assert adapter is tracker
        item = supabase.rows["items"][0]
        assert item["status"] == "approved"
        calls.append(str(item_id))
        return "https://tracker.example/tasks/1"

    monkeypatch.setattr(item_routes, "create_tracker", lambda: tracker)
    monkeypatch.setattr(item_routes.settings, "telegram_bot_token", "configured")
    monkeypatch.setattr(item_routes.settings, "telegram_chat_id", "123")
    monkeypatch.setattr(item_routes.settings, "demo_mode", True)
    monkeypatch.setattr(
        item_routes,
        "execute_approved_action",
        fake_execute_approved_action,
    )
    app.dependency_overrides[get_supabase_client] = lambda: supabase  # type: ignore[return-value]

    try:
        with TestClient(app) as client:
            pending = client.get("/api/items?status=pending")
            assert calls == []
            approved = client.post(f"/api/items/{ITEM_ID}/approve")
    finally:
        app.dependency_overrides.pop(get_supabase_client, None)

    assert pending.status_code == 200
    assert pending.json()[0]["status"] == "pending"
    assert approved.status_code == 200
    assert approved.json()["tracker_ref"] == "https://tracker.example/tasks/1"
    assert calls == [ITEM_ID]
    deadline = datetime.fromisoformat(str(supabase.rows["items"][0]["deadline"]))
    reminder = datetime.fromisoformat(str(supabase.rows["reminders"][0]["send_at"]))
    assert 115 <= (deadline - datetime.now(deadline.tzinfo)).total_seconds() <= 120
    assert abs((deadline - reminder).total_seconds()) < 2


def test_rejected_action_is_removed_without_tracker_call() -> None:
    """Rejecting an item persists its terminal status without an external action."""
    supabase = FakeSupabase()
    app.dependency_overrides[get_supabase_client] = lambda: supabase  # type: ignore[return-value]

    try:
        with TestClient(app) as client:
            response = client.post(f"/api/items/{ITEM_ID}/reject")
    finally:
        app.dependency_overrides.pop(get_supabase_client, None)

    assert response.status_code == 200
    assert response.json() == {"status": "rejected"}
    assert supabase.rows["items"][0]["status"] == "rejected"
