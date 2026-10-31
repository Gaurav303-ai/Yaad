"""Meeting creation and listing API routes."""

import asyncio
import json
from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter
from postgrest.exceptions import APIError
from supabase import AsyncClient
from starlette.responses import StreamingResponse

from app.agents.conflict import detect_conflicts
from app.agents.ingest import ingest_transcript
from app.agents.orchestrator import orchestrate
from app.core.schemas import Conflict, Decision, TeamMember, TranscriptSegment

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
    aliases: list[str] = Field(default_factory=list)


class _MeetingRow(BaseModel):
    """Database representation used by the meetings API."""

    id: UUID
    title: str
    meeting_date: date
    attendees: list[UUID]
    raw_transcript: str
    status: str
    created_at: datetime


class _StoredMeeting(BaseModel):
    """Meeting fields required by the extraction and memory pipeline."""

    id: UUID
    meeting_date: date
    raw_transcript: str
    status: str


class _InsertedItem(BaseModel):
    """Generated database identifier for a persisted extracted item."""

    id: UUID


class MeetingItemResponse(BaseModel):
    """Persisted extraction item with its resolved owner."""

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


class MeetingProcessResponse(BaseModel):
    """Extraction output and new conflicts persisted for a meeting."""

    meeting_id: UUID
    meeting_date: date
    segments: list[TranscriptSegment]
    items: list[MeetingItemResponse]
    conflicts: list[Conflict]


class MeetingDetailResponse(BaseModel):
    """Meeting record plus its stored transcript segments and items."""

    meeting: MeetingResponse
    segments: list[TranscriptSegment]
    items: list[MeetingItemResponse]


class _StoredSegment(BaseModel):
    """Database transcript segment."""

    speaker: str
    text: str
    segment_order: int


class _StoredItem(BaseModel):
    """Database extraction item used in meeting details."""

    id: UUID
    type: Literal["decision", "action", "intent"]
    topic: str
    text: str
    owner_id: UUID | None
    deadline: datetime | None
    confidence: float | None
    source_quote: str
    speaker: str | None
    status: str


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
stored_meeting_rows = TypeAdapter(list[_StoredMeeting])
inserted_item_rows = TypeAdapter(list[_InsertedItem])
stored_segments = TypeAdapter(list[_StoredSegment])
stored_items = TypeAdapter(list[_StoredItem])


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


@router.get("/{meeting_id}", response_model=MeetingDetailResponse)
async def get_meeting(
    meeting_id: UUID,
    supabase: SupabaseDependency,
) -> MeetingDetailResponse:
    """Return one meeting with its saved segments and extraction items."""
    try:
        meeting_response = await (
            supabase.table("meetings")
            .select("id,title,meeting_date,attendees,raw_transcript,status,created_at")
            .eq("id", str(meeting_id))
            .execute()
        )
        meetings = meeting_rows.validate_python(meeting_response.data)
        if not meetings:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Meeting not found.",
            )
        meeting = meetings[0]
        segment_response = await (
            supabase.table("segments")
            .select("speaker,text,segment_order")
            .eq("meeting_id", str(meeting_id))
            .order("segment_order")
            .execute()
        )
        item_response = await (
            supabase.table("items")
            .select("id,type,topic,text,owner_id,deadline,confidence,source_quote,speaker,status")
            .eq("meeting_id", str(meeting_id))
            .order("created_at")
            .execute()
        )
        members_response = await supabase.table("members").select("id,name").execute()
    except APIError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Supabase could not load meeting details: {error.message}",
        ) from error
    except httpx.HTTPError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not connect to Supabase while loading meeting details.",
        ) from error

    members = member_rows.validate_python(members_response.data)
    member_names = {member.id: member.name for member in members}
    segments = stored_segments.validate_python(segment_response.data)
    items = stored_items.validate_python(item_response.data)
    return MeetingDetailResponse(
        meeting=_meeting_response(meeting, member_names),
        segments=[
            TranscriptSegment(speaker=row.speaker, text=row.text, order=row.segment_order)
            for row in segments
        ],
        items=[
            MeetingItemResponse(
                id=item.id,
                meeting_id=meeting_id,
                type=item.type,
                topic=item.topic,
                text=item.text,
                owner_name=member_names.get(item.owner_id) if item.owner_id else None,
                deadline=item.deadline,
                confidence=item.confidence,
                source_quote=item.source_quote,
                speaker=item.speaker,
                status=item.status,
            )
            for item in items
        ],
    )


@router.post("/{meeting_id}/process", response_model=MeetingProcessResponse)
async def process_meeting(
    meeting_id: UUID,
    supabase: SupabaseDependency,
) -> MeetingProcessResponse:
    """Extract a saved transcript, compare decisions with memory, and persist the results."""
    try:
        meeting_response = await (
            supabase.table("meetings")
            .select("id,meeting_date,raw_transcript,status")
            .eq("id", str(meeting_id))
            .execute()
        )
        stored_meetings = stored_meeting_rows.validate_python(meeting_response.data)
        if not stored_meetings:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Meeting not found.",
            )
        meeting = stored_meetings[0]
        if meeting.status != "ingested":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Meeting cannot be processed from status '{meeting.status}'.",
            )
        member_response = await supabase.table("members").select("id,name,aliases").execute()
        members = member_rows.validate_python(member_response.data)
    except APIError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Supabase could not load the meeting for processing: {error.message}",
        ) from error
    except httpx.HTTPError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not connect to Supabase while loading the meeting.",
        ) from error

    team = [TeamMember(name=member.name, aliases=member.aliases) for member in members]
    extraction = await orchestrate(meeting.raw_transcript, meeting.meeting_date, team)
    member_ids = {member.name.casefold(): member.id for member in members}

    try:
        if extraction.segments:
            await supabase.table("segments").insert(
                [
                    {
                        "meeting_id": str(meeting.id),
                        "speaker": segment.speaker,
                        "text": segment.text,
                        "segment_order": segment.order,
                    }
                    for segment in extraction.segments
                ]
            ).execute()

        item_payloads = [
            {
                "meeting_id": str(meeting.id),
                "type": item.type,
                "topic": item.topic,
                "text": item.text,
                "owner_id": str(member_ids[item.owner_name.casefold()])
                if item.owner_name and item.owner_name.casefold() in member_ids
                else None,
                "deadline": item.deadline.isoformat() if item.deadline else None,
                "confidence": item.confidence,
                "source_quote": item.source_quote,
                "speaker": item.speaker,
            }
            for item in extraction.items
        ]
        if item_payloads:
            inserted_items_response = await supabase.table("items").insert(item_payloads).execute()
            inserted_items = inserted_item_rows.validate_python(inserted_items_response.data)
        else:
            inserted_items = []
        if len(inserted_items) != len(extraction.items):
            raise RuntimeError("Supabase did not return every saved extraction item.")

        persisted_items = [
            item.model_copy(update={"id": inserted.id})
            for item, inserted in zip(extraction.items, inserted_items, strict=True)
        ]
        conflicts: list[Conflict] = []
        for item in persisted_items:
            if item.type != "decision" or item.id is None:
                continue
            decision = Decision(
                topic=item.topic,
                statement=item.text,
                meeting_id=meeting.id,
                meeting_date=meeting.meeting_date,
                deadline=item.deadline,
                source_quote=item.source_quote,
                speaker=item.speaker,
            )
            conflicts.extend(await detect_conflicts(supabase, item.id, decision))

        await (
            supabase.table("meetings")
            .update({"status": "review"})
            .eq("id", str(meeting.id))
            .execute()
        )
        response_items: list[MeetingItemResponse] = []
        for item in persisted_items:
            if item.id is None:
                raise RuntimeError("A persisted meeting item is missing its generated ID.")
            response_items.append(
                MeetingItemResponse(
                    id=item.id,
                    meeting_id=meeting.id,
                    type=item.type,
                    topic=item.topic,
                    text=item.text,
                    owner_name=item.owner_name,
                    deadline=item.deadline,
                    confidence=item.confidence,
                    source_quote=item.source_quote,
                    speaker=item.speaker,
                    status="pending",
                )
            )
    except APIError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Supabase could not save meeting processing results: {error.message}",
        ) from error
    except httpx.HTTPError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not connect to Supabase while saving meeting processing results.",
        ) from error

    return MeetingProcessResponse(
        meeting_id=meeting.id,
        meeting_date=meeting.meeting_date,
        segments=extraction.segments,
        items=response_items,
        conflicts=conflicts,
    )


@router.get("/{meeting_id}/replay")
async def replay_meeting(
    meeting_id: UUID,
    supabase: SupabaseDependency,
) -> StreamingResponse:
    """Replay labelled transcript turns and then stream persisted extraction cards."""
    detail = await get_meeting(meeting_id, supabase)
    segments = detail.segments or ingest_transcript(detail.meeting.raw_transcript).segments

    async def stream_events():
        yield _sse_event("agent", {"message": "Reading speaker-labelled transcript"})
        for segment in segments:
            yield _sse_event("segment", segment.model_dump(mode="json"))
            await asyncio.sleep(0.12)

        if detail.meeting.status == "ingested":
            yield _sse_event("agent", {"message": "Extracting items and checking decision memory"})
            try:
                processed = await process_meeting(meeting_id, supabase)
            except HTTPException as error:
                yield _sse_event("error", {"message": str(error.detail)})
                return
            items = processed.items
            yield _sse_event("conflicts", [conflict.model_dump(mode="json") for conflict in processed.conflicts])
        else:
            items = detail.items
            yield _sse_event("conflicts", [])

        for item in items:
            yield _sse_event("item", item.model_dump(mode="json"))
            await asyncio.sleep(0.08)
        yield _sse_event("complete", {"meeting_id": str(meeting_id), "item_count": len(items)})

    return StreamingResponse(
        stream_events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _sse_event(event: str, data: object) -> str:
    """Encode one server-sent event frame."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
