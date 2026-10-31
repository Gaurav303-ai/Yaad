"""List stored conflicts with both source-grounded decisions."""

from datetime import date
from typing import Literal
from uuid import UUID

import httpx
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, TypeAdapter
from postgrest.exceptions import APIError

from app.routers.meetings import SupabaseDependency

router = APIRouter(prefix="/conflicts", tags=["conflicts"])


class _ConflictRow(BaseModel):
    """Stored conflict and its source foreign keys."""

    id: UUID
    new_item_id: UUID
    old_decision_id: UUID
    label: Literal["contradiction", "update", "duplicate"]
    explanation: str
    resolution: str | None = None


class _NewDecisionRow(BaseModel):
    """Source item for the current side of a conflict."""

    id: UUID
    meeting_id: UUID
    topic: str
    text: str
    speaker: str | None
    source_quote: str


class _OldDecisionRow(BaseModel):
    """Prior decision for the memory side of a conflict."""

    id: UUID
    topic: str
    statement: str
    speaker: str
    source_quote: str
    meeting_date: date


class ConflictSource(BaseModel):
    """Decision details displayed in the side-by-side conflict view."""

    topic: str
    statement: str
    speaker: str | None
    source_quote: str
    meeting_date: date


class ConflictResponse(BaseModel):
    """Conflict record with both dated source excerpts."""

    id: UUID
    label: Literal["contradiction", "update", "duplicate"]
    explanation: str
    resolution: str | None
    new: ConflictSource
    old: ConflictSource


class ConflictResolutionRequest(BaseModel):
    """Human choice recorded for a conflict pair."""

    resolution: Literal["keep_new", "keep_old", "merge"]


class ConflictResolutionResponse(BaseModel):
    """Confirmation that a human conflict choice was stored."""

    id: UUID
    resolution: Literal["keep_new", "keep_old", "merge"]


class _MeetingDateRow(BaseModel):
    """Meeting date required for a new item source."""

    id: UUID
    meeting_date: date


conflict_rows = TypeAdapter(list[_ConflictRow])
new_item_rows = TypeAdapter(list[_NewDecisionRow])
old_decision_rows = TypeAdapter(list[_OldDecisionRow])
meeting_date_rows = TypeAdapter(list[_MeetingDateRow])


@router.get("", response_model=list[ConflictResponse])
async def list_conflicts(supabase: SupabaseDependency) -> list[ConflictResponse]:
    """Return conflicts with their new and prior source details."""
    try:
        conflicts_response = await (
            supabase.table("conflicts")
            .select("id,new_item_id,old_decision_id,label,explanation,resolution")
            .order("created_at", desc=True)
            .execute()
        )
        conflicts = conflict_rows.validate_python(conflicts_response.data)
        if not conflicts:
            return []
        new_ids = list({str(conflict.new_item_id) for conflict in conflicts})
        old_ids = list({str(conflict.old_decision_id) for conflict in conflicts})
        new_response = await (
            supabase.table("items")
            .select("id,meeting_id,topic,text,speaker,source_quote")
            .in_("id", new_ids)
            .execute()
        )
        old_response = await (
            supabase.table("decisions")
            .select("id,topic,statement,speaker,source_quote,meeting_date")
            .in_("id", old_ids)
            .execute()
        )
        new_items = new_item_rows.validate_python(new_response.data)
        old_decisions = old_decision_rows.validate_python(old_response.data)
        if len(new_items) != len(new_ids) or len(old_decisions) != len(old_ids):
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="A conflict references a missing decision record.",
            )
        meeting_ids = list({str(item.meeting_id) for item in new_items})
        if not meeting_ids:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Conflicts do not have associated meetings.",
            )
        meetings_response = await (
            supabase.table("meetings")
            .select("id,meeting_date")
            .in_("id", meeting_ids)
            .execute()
        )
        meeting_dates = {
            row.id: row.meeting_date for row in meeting_date_rows.validate_python(meetings_response.data)
        }
    except APIError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Supabase could not load conflicts: {error.message}",
        ) from error
    except httpx.HTTPError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not connect to Supabase while loading conflicts.",
        ) from error

    new_by_id = {item.id: item for item in new_items}
    old_by_id = {decision.id: decision for decision in old_decisions}
    response: list[ConflictResponse] = []
    for conflict in conflicts:
        new = new_by_id.get(conflict.new_item_id)
        old = old_by_id.get(conflict.old_decision_id)
        if new is None or old is None or new.meeting_id not in meeting_dates:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="A conflict references a missing decision or meeting.",
            )
        response.append(
            ConflictResponse(
                id=conflict.id,
                label=conflict.label,
                explanation=conflict.explanation,
                resolution=conflict.resolution,
                new=ConflictSource(
                    topic=new.topic,
                    statement=new.text,
                    speaker=new.speaker,
                    source_quote=new.source_quote,
                    meeting_date=meeting_dates[new.meeting_id],
                ),
                old=ConflictSource(
                    topic=old.topic,
                    statement=old.statement,
                    speaker=old.speaker,
                    source_quote=old.source_quote,
                    meeting_date=old.meeting_date,
                ),
            )
        )
    return response


@router.patch("/{conflict_id}/resolution", response_model=ConflictResolutionResponse)
async def resolve_conflict(
    conflict_id: UUID,
    payload: ConflictResolutionRequest,
    supabase: SupabaseDependency,
) -> ConflictResolutionResponse:
    """Persist a human decision without triggering any external action."""
    try:
        response = await (
            supabase.table("conflicts")
            .update({"resolution": payload.resolution})
            .eq("id", str(conflict_id))
            .select("id,new_item_id,old_decision_id,label,explanation,resolution")
            .execute()
        )
    except APIError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Supabase could not save the conflict resolution: {error.message}",
        ) from error
    except httpx.HTTPError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not connect to Supabase while saving the conflict resolution.",
        ) from error
    rows = TypeAdapter(list[_ConflictRow]).validate_python(response.data)
    if len(rows) != 1:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conflict not found.",
        )
    return ConflictResolutionResponse(id=rows[0].id, resolution=payload.resolution)
