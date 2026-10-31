"""People profiles and commitment reliability summaries."""

import httpx
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, TypeAdapter
from postgrest.exceptions import APIError
from supabase import AsyncClient
from uuid import UUID

from app.routers.meetings import SupabaseDependency

router = APIRouter(prefix="/people", tags=["people"])


class _MemberRow(BaseModel):
    """Public profile fields from the team roster."""

    id: UUID
    name: str
    role: str


class _StatsRow(BaseModel):
    """Persisted completion statistics."""

    member_id: UUID
    total: int
    on_time: int
    avg_slip_days: float


class _OwnedItemRow(BaseModel):
    """Action fields shown in a person's profile."""

    id: UUID
    owner_id: UUID | None
    type: str
    topic: str
    text: str
    deadline: str | None
    status: str
    tracker_ref: str | None = None


class PersonSummary(BaseModel):
    """Reliability totals for one teammate."""

    member_id: UUID
    name: str
    role: str
    open_actions: int
    completed: int
    on_time_rate: float | None
    avg_slip_days: float | None
    reliability_score: float | None


class PersonDetail(BaseModel):
    """Profile with open actions and reliability data."""

    summary: PersonSummary
    open_items: list[_OwnedItemRow]


member_rows = TypeAdapter(list[_MemberRow])
stats_rows = TypeAdapter(list[_StatsRow])
owned_item_rows = TypeAdapter(list[_OwnedItemRow])


def _summary(member: _MemberRow, stats: _StatsRow | None, items: list[_OwnedItemRow]) -> PersonSummary:
    total = stats.total if stats else 0
    on_time_rate = (stats.on_time / total * 100) if stats and total else None
    slip = float(stats.avg_slip_days) if stats else None
    return PersonSummary(
        member_id=member.id,
        name=member.name,
        role=member.role,
        open_actions=sum(
            item.type == "action" and item.status in {"pending", "approved"}
            for item in items
        ),
        completed=total,
        on_time_rate=on_time_rate,
        avg_slip_days=slip,
        reliability_score=on_time_rate,
    )


async def _load_profiles(supabase: AsyncClient) -> tuple[list[_MemberRow], list[_StatsRow], list[_OwnedItemRow]]:
    members_response = await supabase.table("members").select("id,name,role").execute()
    stats_response = await supabase.table("commitment_stats").select(
        "member_id,total,on_time,avg_slip_days"
    ).execute()
    items_response = await supabase.table("items").select(
        "id,owner_id,type,topic,text,deadline,status,tracker_ref"
    ).execute()
    return (
        member_rows.validate_python(members_response.data),
        stats_rows.validate_python(stats_response.data),
        owned_item_rows.validate_python(items_response.data),
    )


@router.get("", response_model=list[PersonSummary])
async def list_people(supabase: SupabaseDependency) -> list[PersonSummary]:
    """List team members with open work and reliability statistics."""
    try:
        members, stats, items = await _load_profiles(supabase)
    except APIError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Supabase could not load team profiles: {error.message}",
        ) from error
    except httpx.HTTPError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not connect to Supabase while loading team profiles.",
        ) from error
    stats_by_member = {row.member_id: row for row in stats}
    return [
        _summary(
            member,
            stats_by_member.get(member.id),
            [item for item in items if item.owner_id == member.id],
        )
        for member in members
    ]


@router.get("/{member_id}", response_model=PersonDetail)
async def get_person(member_id: UUID, supabase: SupabaseDependency) -> PersonDetail:
    """Return one team profile with its open items and reliability history."""
    try:
        members, stats, items = await _load_profiles(supabase)
    except APIError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Supabase could not load the team profile: {error.message}",
        ) from error
    except httpx.HTTPError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not connect to Supabase while loading the team profile.",
        ) from error
    member = next((row for row in members if row.id == member_id), None)
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team member not found.")
    member_items = [
        item
        for item in items
        if item.owner_id == member_id
        and item.type == "action"
        and item.status in {"pending", "approved"}
    ]
    member_stats = next((row for row in stats if row.member_id == member_id), None)
    return PersonDetail(
        summary=_summary(member, member_stats, member_items),
        open_items=member_items,
    )
