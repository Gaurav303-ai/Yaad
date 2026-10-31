"""Read extracted meeting items for the review and dashboard screens."""

from datetime import datetime
from typing import Literal
from uuid import UUID

import httpx
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, TypeAdapter
from postgrest.exceptions import APIError

from app.routers.meetings import SupabaseDependency

router = APIRouter(prefix="/items", tags=["items"])
_ITEM_STATUSES = ("pending", "approved", "rejected", "done")


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


item_rows = TypeAdapter(list[_ItemRow])
member_rows = TypeAdapter(list[_MemberRow])


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
        if item_status in _ITEM_STATUSES:
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
