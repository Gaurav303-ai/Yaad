"""Parse speaker-labelled meeting transcripts into ordered segments."""

import re

from app.core.schemas import IngestResult, TranscriptSegment

_SPEAKER_LABEL = re.compile(
    r"(?<!\S)(?P<speaker>(?:[A-Z][a-z]+(?:[ '-][A-Z][a-z]+){0,3}|Speaker \d+|Meeting [A-Z]?\d+)):\s*"
)
_MEETING_HEADER = re.compile(r"^meeting\s+(?:[a-z]?\d+)\s*$", re.IGNORECASE)


def ingest_transcript(transcript: str) -> IngestResult:
    """Split labelled `Name: line` text while retaining speaker attribution."""
    matches = list(_SPEAKER_LABEL.finditer(transcript))
    segments: list[TranscriptSegment] = []
    for index, match in enumerate(matches):
        speaker = match.group("speaker").strip()
        if _MEETING_HEADER.fullmatch(speaker):
            continue
        end = matches[index + 1].start() if index + 1 < len(matches) else len(transcript)
        text = " ".join(transcript[match.end() : end].split()).strip()
        if text:
            segments.append(
                TranscriptSegment(
                    speaker=speaker,
                    text=text,
                    order=len(segments),
                )
            )
    if not segments:
        raise ValueError("Transcript must contain at least one labelled speaker line (Name: line).")
    return IngestResult(segments=segments)
