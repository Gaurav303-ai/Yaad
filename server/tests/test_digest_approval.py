"""Tests that digest email delivery requires explicit human approval."""

from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest

from app.main import app
from app.routers import digests as digest_routes
from app.routers.meetings import get_supabase_client

MEMBER_ID = "00000000-0000-0000-0000-000000000001"
DIGEST_ID = "00000000-0000-0000-0000-000000000060"


class FakeQuery:
    """Minimal digest and member query double."""

    def __init__(self, client: "FakeSupabase", table_name: str) -> None:
        self.client = client
        self.table_name = table_name
        self.filters: dict[str, str] = {}
        self.updated_values: dict[str, object] | None = None

    def select(self, _: str) -> "FakeQuery":
        return self

    def order(self, _: str, *, desc: bool = False) -> "FakeQuery":
        del desc
        return self

    def eq(self, column: str, value: str) -> "FakeQuery":
        self.filters[column] = value
        return self

    def update(self, values: dict[str, object]) -> "FakeQuery":
        self.updated_values = values
        return self

    async def execute(self) -> SimpleNamespace:
        rows = self.client.rows[self.table_name]
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
    """Pending digest plus its configured recipient."""

    def __init__(self) -> None:
        self.rows: dict[str, list[dict[str, object]]] = {
            "digests": [
                {
                    "id": DIGEST_ID,
                    "member_id": MEMBER_ID,
                    "week_start": "2026-10-19",
                    "subject": "Yaad weekly digest",
                    "body": "Hi Priya, here is your personal update.",
                    "status": "pending",
                    "sent_at": None,
                    "created_at": datetime.now(UTC).isoformat(),
                }
            ],
            "members": [{"id": MEMBER_ID, "name": "Priya", "email": "priya@example.test"}],
        }

    def table(self, table_name: str) -> FakeQuery:
        return FakeQuery(self, table_name)


def test_digest_is_not_emailed_until_approved(monkeypatch: pytest.MonkeyPatch) -> None:
    """Listing a pending digest does not send mail; approval does."""
    supabase = FakeSupabase()
    sent: list[str] = []

    async def fake_send_email(recipient: str, subject: str, body: str) -> str:
        del subject, body
        sent.append(recipient)
        return "provider-message-id"

    monkeypatch.setattr(digest_routes, "send_email", fake_send_email)
    app.dependency_overrides[get_supabase_client] = lambda: supabase  # type: ignore[return-value]

    try:
        with TestClient(app) as client:
            preview = client.get("/api/digests")
            assert sent == []
            approved = client.post(f"/api/digests/{DIGEST_ID}/approve")
    finally:
        app.dependency_overrides.pop(get_supabase_client, None)

    assert preview.status_code == 200
    assert preview.json()[0]["member_name"] == "Priya"
    assert approved.status_code == 200
    assert approved.json()["status"] == "sent"
    assert sent == ["priya@example.test"]
