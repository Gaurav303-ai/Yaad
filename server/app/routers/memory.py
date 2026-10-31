"""Search the structured decision timeline."""

from datetime import date, datetime
from uuid import UUID

import httpx
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, TypeAdapter
from postgrest.exceptions import APIError

from app.routers.meetings import SupabaseDependency

router = APIRouter(prefix="/memory", tags=["memory"])


class MemoryDecision(BaseModel):
    """Source-grounded decision timeline entry."""

    id: UUID
    meeting_id: UUID
    topic: str
    statement: str
    meeting_date: date
    deadline: datetime | None
    source_quote: str
    speaker: str
    status: str


decisions = TypeAdapter(list[MemoryDecision])


@router.get("", response_model=list[MemoryDecision])
async def search_memory(
    supabase: SupabaseDependency,
    query: str | None = Query(default=None, max_length=160),
) -> list[MemoryDecision]:
    """Search active structured decisions by topic, statement, speaker, or quote."""
    try:
        response = await (
            supabase.table("decisions")
            .select("id,meeting_id,topic,statement,meeting_date,deadline,source_quote,speaker,status")
            .eq("status", "active")
            .order("meeting_date", desc=True)
            .execute()
        )
    except APIError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Supabase could not load decision memory: {error.message}",
        ) from error
    except httpx.HTTPError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not connect to Supabase while loading decision memory.",
        ) from error

    rows = decisions.validate_python(response.data)
    if not query or not query.strip():
        return rows
    term = query.casefold().strip()
    return [
        decision
        for decision in rows
        if term
        in " ".join(
            (
                decision.topic,
                decision.statement,
                decision.speaker,
                decision.source_quote,
            )
        ).casefold()
    ]
