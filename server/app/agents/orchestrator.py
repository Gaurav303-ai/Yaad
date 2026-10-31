"""Coordinate the M2 transcript extraction pipeline."""

from datetime import date

from app.agents.critic import critique_items
from app.agents.extractor import extract_items
from app.agents.ingest import ingest_transcript
from app.agents.resolver import resolve_items
from app.core.schemas import MeetingExtraction, TeamMember


async def orchestrate(
    transcript: str,
    meeting_date: date,
    team: list[TeamMember],
) -> MeetingExtraction:
    """Run ingest, structured extraction, source criticism, and date resolution."""
    ingested = ingest_transcript(transcript)
    extracted = await extract_items(ingested.segments, meeting_date, team)
    criticized = critique_items(extracted, ingested.segments)
    items = resolve_items(criticized.items, meeting_date, team)
    return MeetingExtraction(
        meeting_date=meeting_date,
        segments=ingested.segments,
        items=items,
    )
