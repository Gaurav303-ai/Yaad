"""Verify extracted source quotes and speaker attribution against the transcript."""

import re
from dataclasses import dataclass

from app.core.schemas import CandidateItem, ExtractionResult, TranscriptSegment


def _normalize_quote(value: str) -> str:
    return " ".join(value.casefold().split())


def _has_soft_intent(item: CandidateItem) -> bool:
    text = f"{item.topic} {item.text} {item.source_quote}".casefold().replace("�", "'").replace("’", "'")
    soft_phrases = (
        "dekhte hain",
        "dekhenge",
        "i'll think about it",
        "i will think about it",
        "think about it",
    )
    if any(phrase in text for phrase in soft_phrases):
        return True
    has_explicit_date = bool(
        re.search(r"\b\d{1,2}(?:st|nd|rd|th)?\s*(?:tareekh|tarikh|date|ko)\b", text)
    )
    return "ho jayega" in text and not item.deadline_expression and not has_explicit_date


@dataclass(frozen=True)
class CriticResult:
    """Verified candidates and the number removed as unsupported."""

    items: list[CandidateItem]
    dropped_count: int


def critique_items(result: ExtractionResult, segments: list[TranscriptSegment]) -> CriticResult:
    """Drop items whose quote is absent, whose speaker is wrong, or which are soft intent."""
    verified: list[CandidateItem] = []
    for item in result.items:
        quote = _normalize_quote(item.source_quote)
        if not quote:
            continue
        matching_speaker_quote = any(
            segment.speaker.casefold() == item.speaker.casefold()
            and quote in _normalize_quote(segment.text)
            for segment in segments
        )
        if not matching_speaker_quote:
            continue
        if _has_soft_intent(item):
            updates = {"deadline_expression": None}
            if item.type != "intent":
                updates["type"] = "intent"
            item = item.model_copy(update=updates)
        verified.append(item)
    return CriticResult(items=verified, dropped_count=len(result.items) - len(verified))
