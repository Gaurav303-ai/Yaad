"""Meeting creation and listing API routes."""

from datetime import date, datetime
from typing import Annotated
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter
from postgrest.exceptions import APIError
from supabase import AsyncClient

router = APIRouter(prefix="/meetings", tags=["meetings"])


class MeetingCreate(BaseModel):
    """Payload for recording a labelled meeting transcript."""

    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=200)
    meeting_date: date
    attendees: list[str] = Field(default_factory=list)
    raw_transcript: str = Field(min_length=1)


class MeetingResponse(BaseModel):
    """Meeting representation returned to the client."""

    id: UUID
    title: str
    meeting_date: date
    attendees: list[str]
    raw_transcript: str
    status: str
    created_at: datetime


class _MemberRow(BaseModel):
    """Subset of member data needed to resolve attendee names."""

    id: UUID
    name: str


class _MeetingRow(BaseModel):
    """Database representation used by the meetings API."""

    id: UUID
    title: str
    meeting_date: date
    attendees: list[UUID]
    raw_transcript: str
    status: str
    created_at: datetime


def get_supabase_client(request: Request) -> AsyncClient:
    """Return the application-scoped admin client."""
    client = getattr(request.app.state, "supabase_admin", None)
    if not isinstance(client, AsyncClient):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase is not available yet. Check server startup configuration.",
        )
    return client


SupabaseDependency = Annotated[AsyncClient, Depends(get_supabase_client)]
member_rows = TypeAdapter(list[_MemberRow])
meeting_rows = TypeAdapter(list[_MeetingRow])


def _meeting_response(row: _MeetingRow, member_names: dict[UUID, str]) -> MeetingResponse:
    unknown_member_ids = [member_id for member_id in row.attendees if member_id not in member_names]
    if unknown_member_ids:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="A meeting references attendees missing from the team roster.",
        )
    return MeetingResponse(
        id=row.id,
        title=row.title,
        meeting_date=row.meeting_date,
        attendees=[member_names[member_id] for member_id in row.attendees],
        raw_transcript=row.raw_transcript,
        status=row.status,
        created_at=row.created_at,
    )


@router.get("", response_model=list[MeetingResponse])
async def list_meetings(supabase: SupabaseDependency) -> list[MeetingResponse]:
    """Return meetings ordered by meeting date, newest first."""
    try:
        meetings_response = await (
            supabase.table("meetings")
            .select("id,title,meeting_date,attendees,raw_transcript,status,created_at")
            .order("meeting_date", desc=True)
            .execute()
        )
        members_response = await supabase.table("members").select("id,name").execute()
    except APIError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Supabase could not load meetings: {error.message}",
        ) from error
    except httpx.HTTPError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not connect to Supabase. Verify SUPABASE_URL and network access.",
        ) from error

    meetings = meeting_rows.validate_python(meetings_response.data)
    members = member_rows.validate_python(members_response.data)
    member_names = {member.id: member.name for member in members}
    return [_meeting_response(meeting, member_names) for meeting in meetings]


@router.post("", response_model=MeetingResponse, status_code=status.HTTP_201_CREATED)
async def create_meeting(
    payload: MeetingCreate,
    supabase: SupabaseDependency,
) -> MeetingResponse:
    """Store a meeting and resolve its attendee names against the seeded team."""
    try:
        members_response = await supabase.table("members").select("id,name").execute()
        members = member_rows.validate_python(members_response.data)
        members_by_name = {member.name.casefold(): member for member in members}

        attendee_names = list(dict.fromkeys(name.strip() for name in payload.attendees))
        unknown_names = [name for name in attendee_names if name.casefold() not in members_by_name]
        if unknown_names:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Unknown attendees: {', '.join(unknown_names)}.",
            )

        attendee_members = [members_by_name[name.casefold()] for name in attendee_names]
        inserted = await (
            supabase.table("meetings")
            .insert(
                {
                    "title": payload.title,
                    "meeting_date": payload.meeting_date.isoformat(),
                    "attendees": [str(member.id) for member in attendee_members],
                    "raw_transcript": payload.raw_transcript,
                }
            )
            .execute()
        )
    except APIError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Supabase could not save the meeting: {error.message}",
        ) from error
    except httpx.HTTPError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not connect to Supabase. Verify SUPABASE_URL and network access.",
        ) from error

    inserted_rows = meeting_rows.validate_python(inserted.data)
    if len(inserted_rows) != 1:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Supabase did not return the saved meeting.",
        )
    member_names = {member.id: member.name for member in attendee_members}
    return _meeting_response(inserted_rows[0], member_names)
