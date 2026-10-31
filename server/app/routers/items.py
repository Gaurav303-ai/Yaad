"""Review, read, and approve extracted meeting items."""

import logging
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

import httpx
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field, TypeAdapter
from postgrest.exceptions import APIError
from supabase import AsyncClient

from app.agents.action import create_tracker, execute_approved_action
from app.config import settings
from app.core.dates import INDIA_TIMEZONE
from app.routers.meetings import SupabaseDependency
from app.tracker.base import Tracker

router = APIRouter(prefix="/items", tags=["items"])
_ITEM_STATUSES = ("pending", "approved", "rejected", "done")
logger = logging.getLogger(__name__)


class ItemResponse(BaseModel):
    """Extracted item fields used by client list and review cards."""

    id: UUID
    meeting_id: UUID
    type: Literal["decision", "action", "intent"]
    topic: str
    text: str
    owner_name: str | None
    deadline: datetime | None
    confidence: float | None
    source_quote: str
    speaker: str | None
    status: str
    tracker_ref: str | None


class _ItemRow(BaseModel):
    """Database item row with the owner relation resolved separately."""

    id: UUID
    meeting_id: UUID
    type: Literal["decision", "action", "intent"]
    topic: str
    text: str
    owner_id: UUID | None
    deadline: datetime | None
    confidence: float | None
    source_quote: str
    speaker: str | None
    status: str
    tracker_ref: str | None = None


class _MemberRow(BaseModel):
    """Owner lookup record."""

    id: UUID
    name: str


class _ReviewRow(BaseModel):
    """Fields required to enforce the review state transition."""

    id: UUID
    type: Literal["decision", "action", "intent"]
    status: Literal["pending", "approved", "rejected", "done"]
    deadline: datetime | None
    tracker_ref: str | None = None


class ItemEditRequest(BaseModel):
    """Human edits to an item before approval."""

    text: str | None = Field(default=None, min_length=1, max_length=1000)
    owner_name: str | None = Field(default=None, max_length=120)
    deadline: datetime | None = None


class ApprovalResponse(BaseModel):
    """Result of approving a decision or action item."""

    item_id: UUID
    status: Literal["approved"]
    tracker_ref: str | None


item_rows = TypeAdapter(list[_ItemRow])
member_rows = TypeAdapter(list[_MemberRow])
review_rows = TypeAdapter(list[_ReviewRow])


@router.get("", response_model=list[ItemResponse])
async def list_items(
    supabase: SupabaseDependency,
    item_status: Literal["pending", "approved", "rejected", "done"] | None = Query(
        default=None,
        alias="status",
    ),
) -> list[ItemResponse]:
    """List extracted items, optionally filtered by their review status."""
    try:
        query = (
            supabase.table("items")
            .select(
                "id,meeting_id,type,topic,text,owner_id,deadline,confidence,source_quote,speaker,status,tracker_ref"
            )
            .order("created_at", desc=True)
        )
        if item_status == "pending":
            query = query.or_(
                "status.eq.pending,and(status.eq.approved,type.eq.action,tracker_ref.is.null)"
            )
        elif item_status in _ITEM_STATUSES:
            query = query.eq("status", item_status)
        item_response = await query.execute()
        members_response = await supabase.table("members").select("id,name").execute()
    except APIError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Supabase could not load extracted items: {error.message}",
        ) from error
    except httpx.HTTPError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not connect to Supabase while loading extracted items.",
        ) from error

    items = item_rows.validate_python(item_response.data)
    members = member_rows.validate_python(members_response.data)
    names = {member.id: member.name for member in members}
    return [
        ItemResponse(
            id=item.id,
            meeting_id=item.meeting_id,
            type=item.type,
            topic=item.topic,
            text=item.text,
            owner_name=names.get(item.owner_id) if item.owner_id else None,
            deadline=item.deadline,
            confidence=item.confidence,
            source_quote=item.source_quote,
            speaker=item.speaker,
            status=item.status,
            tracker_ref=item.tracker_ref,
        )
        for item in items
    ]


async def _load_review_row(supabase: AsyncClient, item_id: UUID) -> _ReviewRow:
    response = await (
        supabase.table("items")
        .select("id,type,status,deadline,tracker_ref")
        .eq("id", str(item_id))
        .execute()
    )
    rows = review_rows.validate_python(response.data)
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found.")
    return rows[0]


async def _schedule_reminders(
    supabase: AsyncClient,
    item_id: UUID,
    deadline: datetime | None,
    *,
    include_demo: bool,
) -> None:
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        if deadline is not None or (settings.demo_mode and include_demo):
            logger.warning(
                "Telegram reminders were not scheduled; configure TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID."
            )
        return
    now = datetime.now(INDIA_TIMEZONE)
    reminder_times: list[datetime] = []
    if deadline is not None:
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=INDIA_TIMEZONE)
        else:
            deadline = deadline.astimezone(INDIA_TIMEZONE)
        reminder_times.extend(
            (deadline - timedelta(hours=24), deadline - timedelta(hours=2))
        )
    if settings.demo_mode and include_demo:
        reminder_times.append(now + timedelta(minutes=2))

    existing_response = await (
        supabase.table("reminders")
        .select("send_at")
        .eq("item_id", str(item_id))
        .eq("channel", "telegram")
        .execute()
    )
    existing = {
        datetime.fromisoformat(str(row["send_at"])).astimezone(UTC)
        for row in existing_response.data
    }
    new_reminders = [
        {"item_id": str(item_id), "send_at": send_at.isoformat(), "channel": "telegram"}
        for send_at in reminder_times
        if send_at > now and send_at.astimezone(UTC) not in existing
    ]
    if new_reminders:
        await supabase.table("reminders").insert(new_reminders).execute()


async def _approve_item(supabase: AsyncClient, item_id: UUID) -> ApprovalResponse:
    item = await _load_review_row(supabase, item_id)
    if item.type == "intent":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Intent items are discussion only and cannot be approved as tasks.",
        )
    if item.status not in {"pending", "approved"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Item cannot be approved from status '{item.status}'.",
        )

    tracker: Tracker | None = None
    if item.type == "action" and item.tracker_ref is None:
        try:
            tracker = create_tracker()
        except RuntimeError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(error),
            ) from error

    approved_deadline = item.deadline
    demo_deadline = (
        item.status == "pending"
        and item.type == "action"
        and settings.demo_mode
        and approved_deadline is None
    )
    if demo_deadline:
        approved_deadline = datetime.now(INDIA_TIMEZONE) + timedelta(minutes=2)
    if item.status == "pending":
        updates: dict[str, str] = {"status": "approved"}
        if approved_deadline is not None and approved_deadline != item.deadline:
            updates["deadline"] = approved_deadline.isoformat()
        await (
            supabase.table("items")
            .update(updates)
            .eq("id", str(item_id))
            .execute()
        )
    if item.type == "decision":
        return ApprovalResponse(item_id=item_id, status="approved", tracker_ref=None)

    try:
        tracker_ref = await execute_approved_action(supabase, item_id, tracker)
        await _schedule_reminders(
            supabase,
            item_id,
            approved_deadline,
            include_demo=demo_deadline,
        )
    except RuntimeError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(error),
        ) from error
    except httpx.HTTPError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The configured tracker could not be reached.",
        ) from error
    return ApprovalResponse(item_id=item_id, status="approved", tracker_ref=tracker_ref)


@router.post("/{item_id}/approve", response_model=ApprovalResponse)
async def approve_item(item_id: UUID, supabase: SupabaseDependency) -> ApprovalResponse:
    """Record human approval before creating a tracker task."""
    try:
        return await _approve_item(supabase, item_id)
    except APIError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Supabase could not approve the item: {error.message}",
        ) from error
    except httpx.HTTPError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not connect to Supabase while approving the item.",
        ) from error


@router.post("/approve-all", response_model=list[ApprovalResponse])
async def approve_all_items(supabase: SupabaseDependency) -> list[ApprovalResponse]:
    """Approve pending action items one at a time; decisions and intents stay local."""
    try:
        response = await (
            supabase.table("items")
            .select("id,type,status,deadline,tracker_ref")
            .eq("type", "action")
            .or_("status.eq.pending,and(status.eq.approved,tracker_ref.is.null)")
            .execute()
        )
        actionable = review_rows.validate_python(response.data)
        item_ids = [
            item.id
            for item in actionable
            if item.status == "pending" or (item.status == "approved" and item.tracker_ref is None)
        ]
        return [await _approve_item(supabase, item_id) for item_id in item_ids]
    except APIError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Supabase could not approve the items: {error.message}",
        ) from error
    except httpx.HTTPError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not connect to Supabase while approving the items.",
        ) from error


@router.post("/{item_id}/reject")
async def reject_item(item_id: UUID, supabase: SupabaseDependency) -> dict[str, str]:
    """Permanently remove a pending item from the approval pipeline."""
    try:
        item = await _load_review_row(supabase, item_id)
        if item.status != "pending" and not (
            item.status == "approved" and item.tracker_ref is None
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Only pending or unposted approved items can be rejected.",
            )
        await (
            supabase.table("items")
            .update({"status": "rejected"})
            .eq("id", str(item_id))
            .execute()
        )
        return {"status": "rejected"}
    except APIError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Supabase could not reject the item: {error.message}",
        ) from error
    except httpx.HTTPError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not connect to Supabase while rejecting the item.",
        ) from error


@router.patch("/{item_id}", response_model=ItemResponse)
async def edit_item(
    item_id: UUID,
    payload: ItemEditRequest,
    supabase: SupabaseDependency,
) -> ItemResponse:
    """Edit a pending item's text, owner, or deadline before approval."""
    if not payload.model_fields_set:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Provide at least one editable field.",
        )
    try:
        item = await _load_review_row(supabase, item_id)
        if item.status != "pending":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Only pending items can be edited.",
            )
        updates: dict[str, object] = {}
        if "text" in payload.model_fields_set and payload.text is not None:
            updates["text"] = payload.text
        if "deadline" in payload.model_fields_set:
            deadline = payload.deadline
            if deadline is not None and deadline.tzinfo is None:
                deadline = deadline.replace(tzinfo=INDIA_TIMEZONE)
            updates["deadline"] = deadline.isoformat() if deadline else None
        if "owner_name" in payload.model_fields_set:
            if payload.owner_name is None:
                updates["owner_id"] = None
            else:
                members_response = await (
                    supabase.table("members")
                    .select("id,name")
                    .eq("name", payload.owner_name.strip())
                    .execute()
                )
                members = member_rows.validate_python(members_response.data)
                if not members:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                        detail="Owner must match a seeded team member.",
                    )
                updates["owner_id"] = str(members[0].id)
        result = await (
            supabase.table("items")
            .update(updates)
            .eq("id", str(item_id))
            .select(
                "id,meeting_id,type,topic,text,owner_id,deadline,confidence,source_quote,speaker,status,tracker_ref"
            )
            .execute()
        )
        edited_items = item_rows.validate_python(result.data)
        if not edited_items:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Supabase did not return the edited item.",
            )
        edited = edited_items[0]
        names_response = await supabase.table("members").select("id,name").execute()
        names = {member.id: member.name for member in member_rows.validate_python(names_response.data)}
        return ItemResponse(
            id=edited.id,
            meeting_id=edited.meeting_id,
            type=edited.type,
            topic=edited.topic,
            text=edited.text,
            owner_name=names.get(edited.owner_id) if edited.owner_id else None,
            deadline=edited.deadline,
            confidence=edited.confidence,
            source_quote=edited.source_quote,
            speaker=edited.speaker,
            status=edited.status,
            tracker_ref=edited.tracker_ref,
        )
    except APIError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Supabase could not edit the item: {error.message}",
        ) from error
    except httpx.HTTPError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not connect to Supabase while editing the item.",
        ) from error


@router.post("/{item_id}/complete")
async def complete_item(item_id: UUID, supabase: SupabaseDependency) -> dict[str, str]:
    """Mark a tracker-backed approved action complete and record its completion time."""
    try:
        item = await _load_review_row(supabase, item_id)
        if item.type != "action" or item.status != "approved" or not item.tracker_ref:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Only approved actions with a tracker task can be completed.",
            )
        await (
            supabase.table("items")
            .update(
                {
                    "status": "done",
                    "completed_at": datetime.now(INDIA_TIMEZONE).isoformat(),
                }
            )
            .eq("id", str(item_id))
            .execute()
        )
        return {"status": "done"}
    except APIError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Supabase could not complete the item: {error.message}",
        ) from error
    except httpx.HTTPError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not connect to Supabase while completing the item.",
        ) from error
