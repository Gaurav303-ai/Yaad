"""Tests for item, conflict, and decision-memory read APIs."""

from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app
from app.routers.meetings import get_supabase_client

MEETING_ID = "00000000-0000-0000-0000-000000000010"
ITEM_ID = "00000000-0000-0000-0000-000000000020"
DECISION_ID = "00000000-0000-0000-0000-000000000030"
CONFLICT_ID = "00000000-0000-0000-0000-000000000040"
PRIYA_ID = "00000000-0000-0000-0000-000000000001"


class FakeQuery:
    """Query builder for the read APIs' required Supabase operations."""

    def __init__(self, client: "FakeSupabase", table_name: str) -> None:
        self.client = client
        self.table_name = table_name
        self.filters: dict[str, str] = {}
        self.in_filters: dict[str, list[str]] = {}
        self.updated_values: dict[str, object] | None = None

    def select(self, _: str) -> "FakeQuery":
        return self

    def order(self, _: str, *, desc: bool = False) -> "FakeQuery":
        return self

    def eq(self, column: str, value: str) -> "FakeQuery":
        self.filters[column] = value
        return self

    def in_(self, column: str, values: list[str]) -> "FakeQuery":
        self.in_filters[column] = values
        return self

    def or_(self, _: str) -> "FakeQuery":
        return self

    def update(self, values: dict[str, object]) -> "FakeQuery":
        self.updated_values = values
        return self

    async def execute(self) -> SimpleNamespace:
        rows = self.client.rows[self.table_name]
        if self.updated_values is not None:
            for row in rows:
                if row["id"] == self.filters.get("id"):
                    row.update(self.updated_values)
            rows = [row for row in rows if row["id"] == self.filters.get("id")]
        for column, value in self.filters.items():
            rows = [row for row in rows if str(row.get(column)) == value]
        for column, values in self.in_filters.items():
            rows = [row for row in rows if str(row.get(column)) in values]
        return SimpleNamespace(data=rows)


class FakeSupabase:
    """Static Supabase rows for M4 read route coverage."""

    def __init__(self) -> None:
        self.rows: dict[str, list[dict[str, object]]] = {
            "members": [{"id": PRIYA_ID, "name": "Priya"}],
            "items": [
                {
                    "id": ITEM_ID,
                    "meeting_id": MEETING_ID,
                    "type": "decision",
                    "topic": "Launch date",
                    "text": "Launch on 30 November.",
                    "owner_id": PRIYA_ID,
                    "deadline": "2026-11-30T00:00:00+05:30",
                    "confidence": 0.96,
                    "source_quote": "Launch 30 November ko hoga.",
                    "speaker": "Priya",
                    "status": "pending",
                    "tracker_ref": None,
                    "created_at": datetime.now(UTC).isoformat(),
                }
            ],
            "decisions": [
                {
                    "id": DECISION_ID,
                    "topic": "Launch date",
                    "statement": "Launch on 30 November.",
                    "meeting_id": MEETING_ID,
                    "meeting_date": "2026-10-12",
                    "deadline": "2026-11-30T00:00:00+05:30",
                    "source_quote": "Launch 30 November ko hoga.",
                    "speaker": "Priya",
                    "status": "active",
                }
            ],
            "conflicts": [
                {
                    "id": CONFLICT_ID,
                    "new_item_id": ITEM_ID,
                    "old_decision_id": DECISION_ID,
                    "label": "update",
                    "explanation": "The launch date changed.",
                    "resolution": None,
                    "created_at": datetime.now(UTC).isoformat(),
                }
            ],
            "meetings": [{"id": MEETING_ID, "meeting_date": "2026-10-26"}],
        }

    def table(self, table_name: str) -> FakeQuery:
        return FakeQuery(self, table_name)


def test_items_conflicts_and_memory_routes_return_source_context() -> None:
    """Read APIs resolve item owners and provide both conflict source excerpts."""
    supabase = FakeSupabase()
    app.dependency_overrides[get_supabase_client] = lambda: supabase  # type: ignore[return-value]

    try:
        with TestClient(app) as client:
            items = client.get("/api/items?status=pending")
            conflicts = client.get("/api/conflicts")
            memory = client.get("/api/memory?query=launch")
            unmatched_memory = client.get("/api/memory?query=not-a-topic")
            resolution = client.patch(
                f"/api/conflicts/{CONFLICT_ID}/resolution",
                json={"resolution": "keep_new"},
            )
    finally:
        app.dependency_overrides.pop(get_supabase_client, None)

    assert items.status_code == 200
    assert items.json()[0]["owner_name"] == "Priya"
    assert conflicts.status_code == 200
    assert conflicts.json()[0]["new"]["meeting_date"] == "2026-10-26"
    assert conflicts.json()[0]["old"]["source_quote"] == "Launch 30 November ko hoga."
    assert memory.status_code == 200
    assert len(memory.json()) == 1
    assert unmatched_memory.status_code == 200
    assert unmatched_memory.json() == []
    assert resolution.status_code == 200
    assert resolution.json()["resolution"] == "keep_new"
