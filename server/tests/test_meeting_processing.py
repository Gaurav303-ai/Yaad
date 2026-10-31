"""Tests for persisted extraction and conflict processing."""

from datetime import UTC, date, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
import pytest

from app.core.schemas import Conflict, Item, MeetingExtraction, TranscriptSegment
from app.main import app
from app.routers import meetings as meeting_routes
from app.routers.meetings import get_supabase_client

MEETING_ID = UUID("00000000-0000-0000-0000-000000000010")
PRIYA_ID = UUID("00000000-0000-0000-0000-000000000001")
RAHUL_ID = UUID("00000000-0000-0000-0000-000000000002")


class FakeQuery:
    """Subset of the Supabase query builder used by meeting processing."""

    def __init__(self, client: "FakeSupabase", table_name: str) -> None:
        self.client = client
        self.table_name = table_name
        self.filters: dict[str, str] = {}
        self.inserted_values: list[dict[str, object]] | None = None
        self.updated_values: dict[str, object] | None = None

    def select(self, _: str) -> "FakeQuery":
        return self

    def order(self, _: str, *, desc: bool = False) -> "FakeQuery":
        return self

    def eq(self, column: str, value: str) -> "FakeQuery":
        self.filters[column] = value
        return self

    def insert(self, values: list[dict[str, object]]) -> "FakeQuery":
        self.inserted_values = values
        return self

    def update(self, values: dict[str, object]) -> "FakeQuery":
        self.updated_values = values
        return self

    async def execute(self) -> SimpleNamespace:
        if self.table_name == "members":
            return SimpleNamespace(data=self.client.members)
        if self.table_name == "meetings":
            if self.updated_values is not None:
                for meeting in self.client.meetings:
                    if meeting["id"] == self.filters.get("id"):
                        meeting.update(self.updated_values)
                return SimpleNamespace(data=[])
            return SimpleNamespace(
                data=[meeting for meeting in self.client.meetings if meeting["id"] == self.filters.get("id")]
            )
        if self.table_name not in {"segments", "items"}:
            raise AssertionError(f"Unexpected table: {self.table_name}")
        if self.inserted_values is None:
            values = [
                row
                for row in self.client.saved_rows[self.table_name]
                if row.get("meeting_id") == self.filters.get("meeting_id")
            ]
            return SimpleNamespace(data=values)
        values = self.inserted_values
        if self.table_name == "items":
            values = [
                {**value, "id": str(uuid4()), "status": "pending"}
                for value in values
            ]
        self.client.saved_rows[self.table_name].extend(values)
        return SimpleNamespace(data=values)


class FakeSupabase:
    """In-memory database test double for the meeting processing endpoint."""

    def __init__(self) -> None:
        self.members = [
            {"id": str(PRIYA_ID), "name": "Priya", "aliases": ["Priya"]},
            {"id": str(RAHUL_ID), "name": "Rahul", "aliases": ["Rahul"]},
        ]
        self.meetings: list[dict[str, object]] = [
            {
                "id": str(MEETING_ID),
                "title": "Weekly plan",
                "meeting_date": "2026-10-12",
                "attendees": [str(PRIYA_ID), str(RAHUL_ID)],
                "raw_transcript": "Priya: We will launch on 30 November.",
                "status": "ingested",
                "created_at": datetime.now(UTC).isoformat(),
            }
        ]
        self.saved_rows: dict[str, list[dict[str, object]]] = {"segments": [], "items": []}

    def table(self, table_name: str) -> FakeQuery:
        return FakeQuery(self, table_name)


def test_process_meeting_persists_segments_items_and_detected_conflicts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The processing endpoint links extraction records and returns conflict results."""
    supabase = FakeSupabase()
    extraction = MeetingExtraction(
        meeting_date=date(2026, 10, 12),
        segments=[TranscriptSegment(speaker="Priya", text="We will launch on 30 November.", order=0)],
        items=[
            Item(
                type="decision",
                topic="Launch date",
                text="Launch on 30 November.",
                owner_name="Priya",
                deadline_expression="30 November",
                deadline=datetime(2026, 11, 30, tzinfo=UTC),
                confidence=0.95,
                source_quote="We will launch on 30 November.",
                speaker="Priya",
            ),
            Item(
                type="intent",
                topic="Second vendor",
                text="Consider a second vendor.",
                owner_name="Rahul",
                confidence=0.8,
                source_quote="Maybe we should look at a second vendor.",
                speaker="Rahul",
            ),
        ],
    )
    async def fake_orchestrate(*_: object) -> MeetingExtraction:
        return extraction

    async def fake_detect_conflicts(*_: object) -> list[Conflict]:
        return []

    monkeypatch.setattr(meeting_routes, "orchestrate", fake_orchestrate)
    monkeypatch.setattr(meeting_routes, "detect_conflicts", fake_detect_conflicts)
    app.dependency_overrides[get_supabase_client] = lambda: supabase  # type: ignore[return-value]

    try:
        with TestClient(app) as client:
            response = client.post(f"/api/meetings/{MEETING_ID}/process")
            details = client.get(f"/api/meetings/{MEETING_ID}")
    finally:
        app.dependency_overrides.pop(get_supabase_client, None)

    assert response.status_code == 200
    result = response.json()
    assert result["meeting_id"] == str(MEETING_ID)
    assert len(result["segments"]) == 1
    assert len(result["items"]) == 2
    assert result["items"][0]["id"]
    assert result["items"][0]["type"] == "decision"
    assert result["items"][1]["type"] == "intent"
    assert supabase.saved_rows["segments"][0]["meeting_id"] == str(MEETING_ID)
    assert supabase.saved_rows["items"][0]["owner_id"] == str(PRIYA_ID)
    assert supabase.saved_rows["items"][0]["topic"] == "Launch date"
    assert supabase.saved_rows["items"][1]["owner_id"] == str(RAHUL_ID)
    assert supabase.meetings[0]["status"] == "review"
    assert details.status_code == 200
    assert details.json()["meeting"]["title"] == "Weekly plan"
    assert len(details.json()["segments"]) == 1
    assert len(details.json()["items"]) == 2
