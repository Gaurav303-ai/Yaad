"""Meeting API tests using an in-memory Supabase table stub."""

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.routers.meetings import get_supabase_client

PRIYA_ID = UUID("00000000-0000-0000-0000-000000000001")
RAHUL_ID = UUID("00000000-0000-0000-0000-000000000002")


class FakeQuery:
    """Small async query builder for the meetings endpoint tests."""

    def __init__(self, client: "FakeSupabase", table_name: str) -> None:
        self.client = client
        self.table_name = table_name
        self.inserted_values: dict[str, object] | None = None
        self.sort_descending = False

    def select(self, _: str) -> "FakeQuery":
        return self

    def order(self, _: str, *, desc: bool) -> "FakeQuery":
        self.sort_descending = desc
        return self

    def insert(self, values: dict[str, object]) -> "FakeQuery":
        self.inserted_values = values
        return self

    async def execute(self) -> SimpleNamespace:
        if self.table_name == "members":
            return SimpleNamespace(data=self.client.members)
        if self.table_name != "meetings":
            raise AssertionError(f"Unexpected table: {self.table_name}")
        if self.inserted_values is not None:
            meeting = {
                **self.inserted_values,
                "id": str(uuid4()),
                "status": "ingested",
                "created_at": datetime.now(UTC).isoformat(),
            }
            self.client.meetings.append(meeting)
            return SimpleNamespace(data=[meeting])
        meetings = sorted(
            self.client.meetings,
            key=lambda row: str(row["meeting_date"]),
            reverse=self.sort_descending,
        )
        return SimpleNamespace(data=meetings)


class FakeSupabase:
    """In-memory test double matching the subset of Supabase used by the API."""

    def __init__(self) -> None:
        self.members = [
            {"id": str(PRIYA_ID), "name": "Priya"},
            {"id": str(RAHUL_ID), "name": "Rahul"},
        ]
        self.meetings: list[dict[str, object]] = []

    def table(self, table_name: str) -> FakeQuery:
        return FakeQuery(self, table_name)


def test_create_and_list_meeting() -> None:
    """POST persists a transcript and GET returns the saved meeting."""
    supabase = FakeSupabase()
    app.dependency_overrides[get_supabase_client] = lambda: supabase  # type: ignore[return-value]

    try:
        with TestClient(app) as client:
            created = client.post(
                "/api/meetings",
                json={
                    "title": "Weekly sync",
                    "meeting_date": "2026-10-12",
                    "attendees": ["priya", "Rahul"],
                    "raw_transcript": "Priya: Namaste.\nRahul: Update share karta hoon.",
                },
            )
            listed = client.get("/api/meetings")
    finally:
        app.dependency_overrides.pop(get_supabase_client, None)

    assert created.status_code == 201
    assert created.json()["attendees"] == ["Priya", "Rahul"]
    assert created.json()["raw_transcript"].startswith("Priya:")
    assert listed.status_code == 200
    assert listed.json()[0]["id"] == created.json()["id"]


def test_create_meeting_rejects_unknown_attendee() -> None:
    """Unknown attendee names are rejected instead of silently dropped."""
    app.dependency_overrides[get_supabase_client] = lambda: FakeSupabase()  # type: ignore[return-value]

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/meetings",
                json={
                    "title": "Weekly sync",
                    "meeting_date": "2026-10-12",
                    "attendees": ["Unknown"],
                    "raw_transcript": "Unknown: Hello.",
                },
            )
    finally:
        app.dependency_overrides.pop(get_supabase_client, None)

    assert response.status_code == 422
    assert "Unknown attendees" in response.json()["detail"]


def test_api_allows_configured_client_cors_origin() -> None:
    """Configured Vite and alternate local development ports pass preflight."""
    with TestClient(app) as client:
        responses = [
            client.options(
                "/api/meetings",
                headers={
                    "Origin": origin,
                    "Access-Control-Request-Method": "POST",
                },
            )
            for origin in ("http://localhost:5173", "http://localhost:5174", "http://localhost:5175")
        ]

    for response, origin in zip(
        responses,
        ("http://localhost:5173", "http://localhost:5174", "http://localhost:5175"),
        strict=True,
    ):
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == origin
