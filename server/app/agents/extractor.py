"""Extract attributable decisions, actions, and intents from meeting segments."""

import json
import re
from datetime import date

from app.core.llm import request_json
from app.core.schemas import CandidateItem, ExtractionResult, TranscriptSegment, TeamMember

_SOFT_MARKERS = (
    "dekhte hain",
    "dekhenge",
    "i'll think about it",
    "i will think about it",
    "think about it",
)
_EXPLICIT_DAY = re.compile(r"\b\d{1,2}(?:st|nd|rd|th)?\s*(?:tareekh|tarikh|date|ko)\b", re.IGNORECASE)


def _include_soft_intents(
    result: ExtractionResult,
    segments: list[TranscriptSegment],
    team: list[TeamMember],
) -> ExtractionResult:
    """Keep obvious tentative turns as traceable intents even if the model omits them."""
    team_names = {
        alias.casefold().strip(): member.name
        for member in team
        for alias in (member.name, *member.aliases)
    }
    items = list(result.items)
    for index, segment in enumerate(segments):
        normalized = segment.text.casefold().replace("�", "'").replace("’", "'")
        marker_index = min(
            (normalized.find(marker) for marker in _SOFT_MARKERS if marker in normalized),
            default=-1,
        )
        if marker_index < 0 and "ho jayega" in normalized and not _EXPLICIT_DAY.search(normalized):
            marker_index = normalized.find("ho jayega")
        if marker_index < 0:
            continue

        quote = " ".join(segment.text.split())
        normalized_quote = " ".join(quote.casefold().split())
        already_covered = any(
            " ".join(item.source_quote.casefold().split()) in normalized_quote
            for item in items
        )
        if already_covered:
            continue

        topic = segment.text[:marker_index].strip(" \t,.;:-")
        if len(topic) < 3 and index > 0:
            topic = segments[index - 1].text
        if len(topic) < 3:
            topic = "Tentative discussion"
        items.append(
            CandidateItem(
                type="intent",
                topic=topic[:160],
                text=quote,
                owner_name=team_names.get(segment.speaker.casefold().strip()),
                confidence=0.75,
                source_quote=quote,
                speaker=segment.speaker,
            )
        )
    return ExtractionResult(items=items)


async def extract_items(
    segments: list[TranscriptSegment],
    meeting_date: date,
    team: list[TeamMember],
) -> ExtractionResult:
    """Ask Gemini for source-grounded structured items from a labelled transcript."""
    transcript = "\n".join(f"{segment.speaker}: {segment.text}" for segment in segments)
    prompt = f"""
Extract explicit decisions, actionable commitments, and soft intents from this meeting.
Meeting date: {meeting_date.isoformat()} (Asia/Kolkata)
Known team members and aliases: {json.dumps([member.model_dump() for member in team], ensure_ascii=False)}

Return a JSON object with an `items` array matching the response schema.
JSON schema:
{json.dumps(ExtractionResult.model_json_schema(), ensure_ascii=False)}

Rules:
- Emit type `decision` for a clear choice/policy/schedule, `action` for a concrete task, `intent` for tentative discussion.
- Do not omit a tentative suggestion or soft commitment: emit it as an `intent`, with its speaker/owner and no deadline unless a concrete deadline was actually committed.
- If one utterance both decides a commitment and assigns an action, emit both records.
- For landing page work, preserve the distinction between the `Landing page draft` and `Landing page final` topics.
- Split every separately numbered or dated commitment into its own record; never combine multiple installment deadlines into one generic payment topic.
- For each vendor installment, emit a decision and a separate action when a person is assigned to handle it. Keep the installment number, owner and its own deadline on both records.
- If an installment's date and assignment occur in the same speaker turn, use one contiguous quote that includes both. Use distinct topics `Vendor installment 1`, `Vendor installment 2`, etc.
- When a decision and its follow-up action are assigned to the same person in the quote, set that person as owner on both records.
- Use adjacent turns to resolve the topic of a follow-up decision (for example, "payment" after a question about the second installment is still about installment 2); quote only text actually spoken by that item's speaker.
- Never turn "dekhte hain", "I'll think about it", or an undated "ho jayega" into an action or decision.
- Every record needs the exact verbatim source_quote and the speaker who said that quote.
- owner_name is the person responsible, not necessarily the speaker; use only known team names. For a decision or intent with no other responsible person stated, use its speaker as owner.
- Preserve the relative deadline phrase in deadline_expression; use null when no deadline was stated.
- Mark weekly recurring schedules or changes to a recurring schedule with recurring=true and deadline_expression=null.
- Split distinct decisions and tasks into separate records. Do not invent dates, owners, or commitments.
- A changed recurring meeting time is still a recurring decision. Preserve the affected weekday/time in its topic and text.
- Keep the numbered installment or schedule qualifier in the topic, including when a later meeting changes it.
- Keep each text concise and Hinglish/English faithful.

Labelled transcript:
{transcript}
""".strip()
    result = await request_json(ExtractionResult, prompt)
    return _include_soft_intents(result, segments, team)
