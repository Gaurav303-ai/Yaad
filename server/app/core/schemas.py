"""Strict schemas shared by the meeting extraction pipeline."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

ItemType = Literal["decision", "action", "intent"]


class TranscriptSegment(BaseModel):
    """A transcript excerpt attributed to its labelled speaker."""

    model_config = ConfigDict(extra="forbid")

    speaker: str = Field(min_length=1)
    text: str = Field(min_length=1)
    order: int = Field(ge=0)


class IngestResult(BaseModel):
    """Labelled transcript segments ready for extraction."""

    segments: list[TranscriptSegment]


class Item(BaseModel):
    """An extracted, attributable meeting decision, action, or intent."""

    model_config = ConfigDict(extra="forbid")

    type: ItemType
    topic: str = Field(min_length=1, max_length=160)
    text: str = Field(min_length=1, max_length=1000)
    owner_name: str | None = None
    deadline_expression: str | None = None
    deadline: datetime | None = None
    recurring: bool = False
    confidence: float = Field(ge=0, le=1)
    source_quote: str = Field(min_length=1)
    speaker: str = Field(min_length=1)


class CandidateItem(BaseModel):
    """LLM extraction candidate before date resolution and quote criticism."""

    model_config = ConfigDict(extra="forbid")

    type: ItemType
    topic: str = Field(min_length=1, max_length=160)
    text: str = Field(min_length=1, max_length=1000)
    owner_name: str | None = None
    deadline_expression: str | None = None
    recurring: bool = False
    confidence: float = Field(ge=0, le=1)
    source_quote: str = Field(min_length=1)
    speaker: str = Field(min_length=1)


class ExtractionResult(BaseModel):
    """Validated list of structured extraction candidates."""

    model_config = ConfigDict(extra="forbid")

    items: list[CandidateItem]


class TeamMember(BaseModel):
    """A known team member used for owner resolution."""

    model_config = ConfigDict(extra="forbid")

    name: str
    aliases: list[str] = Field(default_factory=list)


class Decision(BaseModel):
    """A normalized decision ready for the decision ledger."""

    topic: str
    statement: str
    meeting_id: UUID | None = None
    meeting_date: date
    source_quote: str
    speaker: str


class Conflict(BaseModel):
    """A comparison between two decisions."""

    new_item_id: UUID | None = None
    old_decision_id: UUID | None = None
    label: Literal["contradiction", "update", "duplicate"]
    explanation: str = Field(min_length=1)
    resolution: str | None = None


class MeetingExtraction(BaseModel):
    """Extraction output grouped under its meeting context."""

    meeting_date: date
    segments: list[TranscriptSegment]
    items: list[Item]
