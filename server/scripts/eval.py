"""Run the extraction pipeline against the four supplied ground-truth meetings."""

import argparse
import asyncio
import json
import re
from collections.abc import Sequence
from datetime import date
from pathlib import Path
import sys
from uuid import uuid4

from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[2]
SERVER_DIRECTORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVER_DIRECTORY))

from app.agents.conflict import compare_decisions
from app.agents.memory import topics_related
from app.agents.orchestrator import orchestrate
from app.core.schemas import Decision, Item, MeetingExtraction, TeamMember


ExpectedItem = tuple[str, str, str, str | None, str | None, str]


class ExpectedMember(BaseModel):
    """Ground-truth team member entry."""

    name: str
    role: str


class ExpectedConflict(BaseModel):
    """Expected cross-meeting decision relationship."""

    new_meeting: str
    prior_meeting: str
    topic: str
    label: str


class EvaluationCriteria(BaseModel):
    """M2 and M3 acceptance criteria from the supplied ground truth."""

    exact_conflict_count: int
    conflicts: list[ExpectedConflict]
    no_false_conflict: dict[str, str]


class ExpectedData(BaseModel):
    """Typed evaluation fixture."""

    meeting_dates: dict[str, date]
    team: list[ExpectedMember]
    items: list[ExpectedItem]
    pass_criteria: EvaluationCriteria


MEETING_FILES = {
    "M1": "meeting1.txt",
    "M2": "meeting2.txt",
    "M3": "meeting3.txt",
    "E1": "meetingE1.txt",
}


def _topic_matches(expected_topic: str, item: Item) -> bool:
    text = f"{item.topic} {item.text} {item.source_quote}".casefold()
    compact = re.sub(r"[^a-z0-9]+", " ", text)
    if "installment 1" in expected_topic.casefold():
        return "installment" in compact and bool(re.search(r"\b(?:1|first|pehla)\b", compact))
    if "installment 2" in expected_topic.casefold():
        return "installment" in compact and bool(re.search(r"\b(?:2|second|doosra)\b", compact))
    if "launch" in expected_topic.casefold():
        return "launch" in compact
    if "staging" in expected_topic.casefold():
        return "staging" in compact
    if "landing page" in expected_topic.casefold():
        qualifier = "final" if "final" in expected_topic.casefold() else "draft"
        return "landing" in compact and "page" in compact and qualifier in compact
    if "ads" in expected_topic.casefold():
        return "ad" in compact or "ads" in compact
    if "contract renewal" in expected_topic.casefold():
        return "contract" in compact and "renewal" in compact and bool(
            re.search(r"\b(?:docs?|documents?)\b", compact)
        )
    if "weekly demo" in expected_topic.casefold():
        return "weekly" in compact and "demo" in compact
    if "production deploy" in expected_topic.casefold():
        return "production" in compact and "deploy" in compact
    if "press note" in expected_topic.casefold():
        return "press" in compact and "note" in compact
    if "login bug" in expected_topic.casefold():
        return "login" in compact and "bug" in compact
    if "vendor as backup" in expected_topic.casefold():
        return "vendor" in compact and bool(re.search(r"\b(?:second|backup)\b", compact))
    return False


async def evaluate_conflicts(
    expected_data: ExpectedData,
    meetings: dict[str, tuple[date, list[Item]]],
) -> bool:
    """Evaluate cross-meeting decisions against the expected conflict set."""
    history: list[tuple[str, date, Decision]] = []
    found: list[tuple[str, str, str, str]] = []
    meeting_ids = {meeting_id: uuid4() for meeting_id in meetings}

    for meeting_id, (meeting_date, items) in sorted(meetings.items(), key=lambda row: row[1][0]):
        for item in items:
            if item.type != "decision":
                continue
            decision = Decision(
                topic=item.topic,
                statement=item.text,
                meeting_id=meeting_ids[meeting_id],
                meeting_date=meeting_date,
                deadline=item.deadline,
                source_quote=item.source_quote,
                speaker=item.speaker,
            )
            for old_meeting, old_date, old_decision in history:
                if old_date >= meeting_date or not topics_related(decision.topic, old_decision.topic):
                    continue
                assessment = await compare_decisions(decision, old_decision)
                if assessment.label != "none":
                    found.append((meeting_id, old_meeting, item.topic, assessment.label))
            history.append((meeting_id, meeting_date, decision))

    expected_conflicts = expected_data.pass_criteria.conflicts
    expected_matches = 0
    for expected in expected_conflicts:
        match = next(
            (
                conflict
                for conflict in found
                if conflict[0] == expected.new_meeting
                and conflict[1] == expected.prior_meeting
                and topics_related(conflict[2], expected.topic)
            ),
            None,
        )
        matched = match is not None and (
            expected.label == "conflict" or match[3] == expected.label
        )
        expected_matches += int(matched)
        print(
            f"{expected.new_meeting} vs {expected.prior_meeting} | {expected.topic} | "
            f"{'PASS' if matched else 'FAIL'}",
            flush=True,
        )

    no_false_topic = expected_data.pass_criteria.no_false_conflict["topic"]
    false_conflicts = [conflict for conflict in found if topics_related(conflict[2], no_false_topic)]
    exact_count = len(found) == expected_data.pass_criteria.exact_conflict_count
    no_false_conflict = not false_conflicts
    print(
        f"Conflict evaluation: {len(found)}/{expected_data.pass_criteria.exact_conflict_count} conflicts; "
        f"no-false-conflict check {'PASS' if no_false_conflict else 'FAIL'}.",
        flush=True,
    )
    return (
        expected_matches == len(expected_conflicts)
        and exact_count
        and no_false_conflict
    )


def _expected_types(expected_type: str) -> set[str]:
    if expected_type == "decision_action":
        return {"decision", "action"}
    if expected_type == "intent_only":
        return {"intent"}
    return {expected_type}


def _candidate_matches(candidates: Sequence[Item], expected: ExpectedItem) -> bool:
    _, topic, expected_type, owner, deadline, _ = expected
    matching = [
        item
        for item in candidates
        if _topic_matches(topic, item)
        and (owner is None or item.owner_name == owner)
        and bool(item.source_quote.strip())
        and bool(item.speaker.strip())
    ]
    expected_kinds = _expected_types(expected_type)
    if deadline == "recurring":
        matching = [item for item in matching if item.recurring]
    elif deadline is None:
        matching = [item for item in matching if item.deadline is None]
    else:
        matching = [
            item
            for item in matching
            if item.deadline is not None and item.deadline.date().isoformat() == deadline
        ]
    if expected_type == "intent_only":
        return bool(matching) and all(item.type == "intent" for item in matching)
    return expected_kinds.issubset({item.type for item in matching})


async def evaluate(*, check_conflicts: bool = False) -> int:
    """Run extraction checks and optionally evaluate cross-meeting conflicts."""
    expected_path = ROOT / "data" / "expected.json"
    expected_data = ExpectedData.model_validate(json.loads(expected_path.read_text(encoding="utf-8")))
    team = [TeamMember(name=member.name) for member in expected_data.team]
    meeting_inputs: list[tuple[str, str, date]] = []

    for meeting_id, filename in MEETING_FILES.items():
        transcript_path = ROOT / "data" / filename
        meeting_date = expected_data.meeting_dates[meeting_id]
        transcript = transcript_path.read_text(encoding="utf-8")
        meeting_inputs.append((meeting_id, transcript, meeting_date))

    semaphore = asyncio.Semaphore(2)

    async def run_meeting(transcript: str, meeting_date: date) -> MeetingExtraction:
        async with semaphore:
            return await orchestrate(transcript, meeting_date, team)

    results = await asyncio.gather(
        *(run_meeting(transcript, meeting_date) for _, transcript, meeting_date in meeting_inputs),
        return_exceptions=True,
    )
    transcripts: dict[str, tuple[str, date, list[Item]]] = {}
    for (meeting_id, transcript, meeting_date), result in zip(meeting_inputs, results, strict=True):
        if isinstance(result, BaseException):
            provider_code = getattr(result, "code", None)
            code_text = f", provider code {provider_code}" if provider_code is not None else ""
            print(f"{meeting_id}: FAIL extraction ({type(result).__name__}{code_text})", flush=True)
            transcripts[meeting_id] = (transcript, meeting_date, [])
            continue
        transcripts[meeting_id] = (transcript, meeting_date, result.items)
        print(
            f"{meeting_id}: extracted {len(result.items)} quote-verified items from {len(result.segments)} segments",
            flush=True,
        )

    passed = 0
    total = len(expected_data.items)
    for expected in expected_data.items:
        meeting_id, topic, _, _, _, _ = expected
        transcript, _, items = transcripts[meeting_id]
        source_text = " ".join(transcript.casefold().split())
        traceable_items = [
            item
            for item in items
            if _topic_matches(topic, item)
            and " ".join(item.source_quote.casefold().split()) in source_text
        ]
        item_passed = _candidate_matches(items, expected) and bool(traceable_items)
        if item_passed:
            passed += 1
        print(f"{meeting_id} | {topic} | {'PASS' if item_passed else 'FAIL'}", flush=True)

    print(f"Extraction evaluation: {passed}/{total} expected items passed.", flush=True)
    if passed != total:
        return 1
    if check_conflicts:
        meetings = {
            meeting_id: (meeting_date, items)
            for meeting_id, (_, meeting_date, items) in transcripts.items()
        }
        return 0 if await evaluate_conflicts(expected_data, meetings) else 1
    return 0


def main() -> None:
    """Run the asynchronous evaluation CLI."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--conflicts",
        action="store_true",
        help="also check cross-meeting conflict count, labels, and false positives",
    )
    args = parser.parse_args()
    raise SystemExit(asyncio.run(evaluate(check_conflicts=args.conflicts)))


if __name__ == "__main__":
    main()
