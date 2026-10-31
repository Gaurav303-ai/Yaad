"""Structured decision-memory retrieval and persistence."""

import re
from uuid import UUID

from pydantic import TypeAdapter
from supabase import AsyncClient

from app.core.embeddings import embed_text
from app.core.schemas import Decision, Item

_TOPIC_STOP_WORDS = {
    "a",
    "about",
    "and",
    "as",
    "by",
    "date",
    "decision",
    "for",
    "from",
    "in",
    "of",
    "on",
    "payment",
    "schedule",
    "the",
    "to",
    "vendor",
}
_DECISIONS = TypeAdapter(list[Decision])


def _topic_tokens(topic: str) -> set[str]:
    """Normalize a topic while retaining distinguishing words and ordinals."""
    words = re.sub(r"[^a-z0-9]+", " ", topic.casefold()).split()
    return {word for word in words if word not in _TOPIC_STOP_WORDS}


def topics_related(first: str, second: str) -> bool:
    """Match topics when one contains the other's key terms or has strong overlap."""
    first_tokens = _topic_tokens(first)
    second_tokens = _topic_tokens(second)
    if not first_tokens or not second_tokens:
        return False
    overlap = len(first_tokens & second_tokens)
    return overlap / min(len(first_tokens), len(second_tokens)) >= 0.6


async def find_related_decisions(
    supabase: AsyncClient,
    decision: Decision,
) -> list[Decision]:
    """Retrieve earlier active decisions using topics and optional pgvector similarity."""
    query = (
        supabase.table("decisions")
        .select("id,topic,statement,meeting_id,meeting_date,deadline,source_quote,speaker")
        .eq("status", "active")
        .lt("meeting_date", decision.meeting_date.isoformat())
    )
    if decision.meeting_id is not None:
        query = query.neq("meeting_id", str(decision.meeting_id))
    response = await query.execute()
    structured = _DECISIONS.validate_python(response.data)
    if not structured:
        return []
    related = {
        row.id: row
        for row in structured
        if row.id is not None and topics_related(decision.topic, row.topic)
    }

    embedding = await embed_text(
        f"{decision.topic}\n{decision.statement}",
        input_type="query",
    )
    if embedding is not None:
        semantic_response = await supabase.rpc(
            "match_decisions",
            {
                "query_embedding": embedding,
                "before_date": decision.meeting_date.isoformat(),
                "match_count": 10,
                "exclude_meeting_id": str(decision.meeting_id) if decision.meeting_id else None,
            },
        ).execute()
        for row in _DECISIONS.validate_python(semantic_response.data):
            if row.id is not None:
                related[row.id] = row
    return sorted(related.values(), key=lambda row: row.meeting_date, reverse=True)


async def update_memory(
    supabase: AsyncClient,
    decision: Decision,
) -> Decision:
    """Persist a decision and its optional embedding in the decision ledger."""
    if decision.meeting_id is None:
        raise ValueError("A meeting ID is required before a decision can enter memory.")
    embedding = decision.embedding or await embed_text(
        f"{decision.topic}\n{decision.statement}",
        input_type="document",
    )
    values: dict[str, str | list[float] | None] = {
        "topic": decision.topic,
        "statement": decision.statement,
        "meeting_id": str(decision.meeting_id),
        "meeting_date": decision.meeting_date.isoformat(),
        "deadline": decision.deadline.isoformat() if decision.deadline else None,
        "source_quote": decision.source_quote,
        "speaker": decision.speaker,
    }
    if embedding is not None:
        values["embedding"] = embedding
    response = await supabase.table("decisions").insert(values).execute()
    inserted = _DECISIONS.validate_python(response.data)
    if len(inserted) != 1:
        raise RuntimeError("Supabase did not return the saved decision.")
    return inserted[0]
