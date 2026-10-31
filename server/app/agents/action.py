"""Approval-gated task creation in the configured tracker."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, TypeAdapter
from supabase import AsyncClient

from app.config import settings
from app.core.dates import INDIA_TIMEZONE
from app.tracker.base import Tracker
from app.tracker.github import GitHubTracker
from app.tracker.trello import TrelloTracker


class _ActionRow(BaseModel):
    """Fields required to post a human-approved action."""

    id: UUID
    type: Literal["action"]
    text: str
    owner_id: UUID | None
    deadline: datetime | None
    source_quote: str
    speaker: str | None
    status: Literal["pending", "approved", "rejected", "done"]
    tracker_ref: str | None


class _OwnerRow(BaseModel):
    """Resolved task owner."""

    id: UUID
    name: str


action_rows = TypeAdapter(list[_ActionRow])
owner_rows = TypeAdapter(list[_OwnerRow])


def create_tracker() -> Tracker:
    """Create the configured tracker adapter without exposing credentials."""
    if settings.tracker == "trello":
        if not settings.trello_key or not settings.trello_token or not settings.trello_list_id:
            raise RuntimeError("Set TRELLO_KEY, TRELLO_TOKEN, and TRELLO_LIST_ID to enable Trello.")
        return TrelloTracker(settings.trello_key, settings.trello_token, settings.trello_list_id)
    if settings.tracker == "github":
        if not settings.github_token or not settings.github_repo:
            raise RuntimeError("Set GITHUB_TOKEN and GITHUB_REPO to enable GitHub Issues.")
        return GitHubTracker(settings.github_token, settings.github_repo)
    raise RuntimeError("Set TRACKER to either 'trello' or 'github'.")


async def execute_approved_action(
    supabase: AsyncClient,
    item_id: UUID,
    tracker: Tracker | None = None,
) -> str:
    """Post one action only after its database status records human approval."""
    response = await (
        supabase.table("items")
        .select("id,type,text,owner_id,deadline,source_quote,speaker,status,tracker_ref")
        .eq("id", str(item_id))
        .execute()
    )
    rows = action_rows.validate_python(response.data)
    if not rows:
        raise ValueError("Action item was not found.")
    item = rows[0]
    if item.status != "approved":
        raise ValueError("Action item must be approved before it can be posted.")
    if item.tracker_ref:
        return item.tracker_ref

    description = item.text
    if item.owner_id:
        owner_response = await (
            supabase.table("members")
            .select("id,name")
            .eq("id", str(item.owner_id))
            .execute()
        )
        owners = owner_rows.validate_python(owner_response.data)
        if owners:
            description += f"\n\nOwner: {owners[0].name}"
    if item.deadline:
        local_deadline = item.deadline.astimezone(INDIA_TIMEZONE)
        description += f"\nDeadline: {local_deadline.strftime('%a, %d %b %Y %H:%M IST')}"
    description += f"\n\nSource: “{item.source_quote}”"
    if item.speaker:
        description += f"\nSpeaker: {item.speaker}"
    tracker_ref = await (tracker or create_tracker()).create_task(item.text[:250], description)
    await (
        supabase.table("items")
        .update({"tracker_ref": tracker_ref})
        .eq("id", str(item.id))
        .execute()
    )
    return tracker_ref
