"""Tests for labelled ingestion, quote criticism, and Hinglish date resolution."""

from datetime import date, datetime
from pathlib import Path

import pytest

from app.agents.critic import critique_items
from app.agents.extractor import _include_soft_intents
from app.agents.ingest import ingest_transcript
from app.agents.resolver import resolve_items
from app.core.dates import INDIA_TIMEZONE, parse_relative_date
from app.core.schemas import CandidateItem, ExtractionResult, TeamMember

DATA_DIRECTORY = Path(__file__).resolve().parents[2] / "data"


@pytest.mark.parametrize(
    ("filename", "expected_speakers"),
    [
        ("meeting1.txt", {"Priya", "Rahul", "Amit", "Neha"}),
        ("meeting2.txt", {"Priya", "Rahul", "Amit", "Neha"}),
        ("meeting3.txt", {"Priya", "Rahul", "Amit", "Neha"}),
        ("meetingE1.txt", {"Priya", "Rahul", "Amit", "Neha"}),
    ],
)
def test_ingest_preserves_speakers_and_ignores_meeting_heading(
    filename: str,
    expected_speakers: set[str],
) -> None:
    """All supplied demos parse to speaker-labelled turns without heading artefacts."""
    transcript = (DATA_DIRECTORY / filename).read_text(encoding="utf-8")
    result = ingest_transcript(transcript)

    assert {segment.speaker for segment in result.segments} == expected_speakers
    assert all(not segment.speaker.casefold().startswith("meeting") for segment in result.segments)
    assert [segment.order for segment in result.segments] == list(range(len(result.segments)))


@pytest.mark.parametrize(
    ("expression", "meeting_date", "expected_date"),
    [
        ("kal tak", date(2026, 10, 26), date(2026, 10, 27)),
        ("parso", date(2026, 10, 12), date(2026, 10, 14)),
        ("is Friday tak", date(2026, 10, 12), date(2026, 10, 16)),
        ("agle Monday tak", date(2026, 10, 19), date(2026, 10, 26)),
        ("agle mahine ke end mein", date(2026, 10, 26), date(2026, 11, 30)),
        ("next Wednesday", date(2026, 10, 27), date(2026, 11, 4)),
        ("end of day tomorrow", date(2026, 10, 27), date(2026, 10, 28)),
        ("15 tareekh ko", date(2026, 10, 12), date(2026, 10, 15)),
        ("30 tareekh ko", date(2026, 10, 26), date(2026, 10, 30)),
    ],
)
def test_relative_deadlines_resolve_in_india_timezone(
    expression: str,
    meeting_date: date,
    expected_date: date,
) -> None:
    """Relative Hinglish and English deadline expressions use meeting date."""
    reference = datetime.combine(meeting_date, datetime.min.time(), tzinfo=INDIA_TIMEZONE)

    resolved = parse_relative_date(expression, reference)

    assert resolved is not None
    assert resolved.date() == expected_date
    assert resolved.tzinfo == INDIA_TIMEZONE


def test_critic_drops_unsupported_quote_and_soft_intent_is_not_task() -> None:
    """Critic requires exact attribution and prevents soft ads intent becoming a task."""
    transcript = "Ads ke baare mein dekhte hain, abhi budget clear nahi hai."
    segment_result = ingest_transcript(f"Neha: {transcript}")
    result = ExtractionResult(
        items=[
            CandidateItem(
                type="action",
                topic="Ads",
                text="Decide the ads budget",
                owner_name="Neha",
                confidence=0.9,
                source_quote=transcript,
                speaker="Neha",
            ),
            CandidateItem(
                type="action",
                topic="Unsupported task",
                text="Do an unrelated task",
                owner_name="Neha",
                confidence=0.9,
                source_quote="This quote is not in the meeting.",
                speaker="Neha",
            ),
        ]
    )

    criticized = critique_items(result, segment_result.segments)

    assert criticized.dropped_count == 1
    assert len(criticized.items) == 1
    assert criticized.items[0].type == "intent"
    assert criticized.items[0].owner_name == "Neha"


def test_critic_keeps_soft_intent_without_a_deadline() -> None:
    """Tentative next-week discussion remains an owner-attributed, undated intent."""
    quote = "Press note ke baare mein dekhte hain agle hafte."
    segment_result = ingest_transcript(f"Neha: {quote}")
    candidate = CandidateItem(
        type="action",
        topic="Press note",
        text="Prepare the press note",
        owner_name="Neha",
        deadline_expression="agle hafte",
        confidence=0.9,
        source_quote=quote,
        speaker="Neha",
    )

    criticized = critique_items(ExtractionResult(items=[candidate]), segment_result.segments)

    assert len(criticized.items) == 1
    assert criticized.items[0].type == "intent"
    assert criticized.items[0].owner_name == "Neha"
    assert criticized.items[0].deadline_expression is None


def test_critic_recognizes_replacement_character_in_soft_phrase() -> None:
    """A damaged apostrophe in a transcript does not turn tentative speech into a task."""
    quote = "I�ll think about it."
    segment_result = ingest_transcript(f"Rahul: {quote}")
    candidate = CandidateItem(
        type="action",
        topic="Second vendor backup",
        text="Find a second vendor",
        owner_name="Rahul",
        confidence=0.9,
        source_quote=quote,
        speaker="Rahul",
    )

    criticized = critique_items(ExtractionResult(items=[candidate]), segment_result.segments)

    assert len(criticized.items) == 1
    assert criticized.items[0].type == "intent"
    assert criticized.items[0].owner_name == "Rahul"


def test_critic_and_resolver_keep_dated_ho_jayega_as_action() -> None:
    """A date in the quote makes `ho jayega` a concrete commitment, not an intent."""
    quote = "Done, 15 ko pehla ho jayega."
    segment_result = ingest_transcript(f"Rahul: {quote}")
    candidate = CandidateItem(
        type="action",
        topic="Vendor installment 1",
        text="Pay the first installment",
        owner_name="Rahul",
        confidence=0.9,
        source_quote=quote,
        speaker="Rahul",
    )
    criticized = critique_items(ExtractionResult(items=[candidate]), segment_result.segments)

    resolved = resolve_items(criticized.items, date(2026, 10, 12), [TeamMember(name="Rahul")])

    assert len(resolved) == 1
    assert resolved[0].type == "action"
    assert resolved[0].deadline is not None
    assert resolved[0].deadline.date() == date(2026, 10, 15)


def test_extractor_retains_omitted_soft_intent_with_prior_topic_context() -> None:
    """A terse tentative reply keeps the topic from the preceding labelled turn."""
    segments = [
        ingest_transcript("Priya: Ads wala kya hua?").segments[0],
        ingest_transcript("Neha: Dekhte hain, ho jayega.").segments[0].model_copy(update={"order": 1}),
    ]

    result = _include_soft_intents(
        ExtractionResult(items=[]),
        segments,
        [TeamMember(name="Neha")],
    )

    assert len(result.items) == 1
    assert result.items[0].type == "intent"
    assert "ads" in result.items[0].topic.casefold()
    assert result.items[0].owner_name == "Neha"
    assert result.items[0].source_quote == "Dekhte hain, ho jayega."


def test_resolver_carries_assigned_owner_from_paired_action_to_decision() -> None:
    """A paired commitment and action share the explicitly assigned owner."""
    candidates = [
        CandidateItem(
            type="decision",
            topic="Vendor installment 2",
            text="Move payment to next month end",
            owner_name="Priya",
            deadline_expression="agle mahine ke end mein",
            confidence=0.9,
            source_quote="Payment agle mahine ke end mein karte hain.",
            speaker="Priya",
        ),
        CandidateItem(
            type="action",
            topic="Vendor installment 2",
            text="Notify the vendor",
            owner_name="Rahul",
            confidence=0.9,
            source_quote="Rahul, vendor ko bata dena.",
            speaker="Priya",
        ),
    ]

    resolved = resolve_items(candidates, date(2026, 10, 26), [TeamMember(name="Priya"), TeamMember(name="Rahul")])

    assert resolved[0].owner_name == "Rahul"
    assert resolved[1].owner_name == "Rahul"


def test_resolver_uses_team_owner_and_meeting_relative_deadline() -> None:
    """Known owner and deadline are normalized without changing source trace."""
    candidate = CandidateItem(
        type="action",
        topic="Production deploy",
        text="Complete the production deploy",
        owner_name="amit",
        deadline_expression="parso tak",
        confidence=0.95,
        source_quote="Production deploy parso tak kar dunga.",
        speaker="Amit",
    )

    resolved = resolve_items(
        [candidate],
        date(2026, 10, 26),
        [TeamMember(name="Amit")],
    )[0]

    assert resolved.owner_name == "Amit"
    assert resolved.deadline is not None
    assert resolved.deadline.date() == date(2026, 10, 28)
    assert resolved.source_quote == candidate.source_quote
