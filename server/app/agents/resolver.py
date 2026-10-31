"""Resolve team owners, classify soft intent, and interpret meeting-relative dates."""

import re
from datetime import date, datetime

from app.core.dates import INDIA_TIMEZONE, parse_relative_date
from app.core.schemas import CandidateItem, Item, TeamMember

_DAY_DEADLINE = re.compile(r"\b\d{1,2}(?:st|nd|rd|th)?\s*(?:tareekh|tarikh|date|ko)\b", re.IGNORECASE)


def _member_lookup(team: list[TeamMember]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for member in team:
        for alias in (member.name, *member.aliases):
            lookup[alias.casefold().strip()] = member.name
    return lookup


def resolve_items(
    candidates: list[CandidateItem],
    meeting_date: date,
    team: list[TeamMember],
) -> list[Item]:
    """Resolve names and dates into typed items anchored to the meeting date."""
    members = _member_lookup(team)
    assigned_owners = {
        candidate.topic.casefold().strip(): members[candidate.owner_name.casefold().strip()]
        for candidate in candidates
        if candidate.type == "action"
        and candidate.owner_name
        and candidate.owner_name.casefold().strip() in members
    }
    reference = datetime.combine(meeting_date, datetime.min.time(), tzinfo=INDIA_TIMEZONE)
    resolved: list[Item] = []
    for candidate in candidates:
        owner_name = None
        if candidate.owner_name:
            owner_name = members.get(candidate.owner_name.casefold().strip())
        if candidate.type == "decision":
            owner_name = assigned_owners.get(candidate.topic.casefold().strip(), owner_name)
        if owner_name is None and candidate.type in {"decision", "intent"}:
            owner_name = members.get(candidate.speaker.casefold().strip())
        deadline_expression = candidate.deadline_expression
        if deadline_expression is None:
            explicit_day = _DAY_DEADLINE.search(candidate.source_quote)
            deadline_expression = explicit_day.group(0) if explicit_day else None
        deadline = parse_relative_date(deadline_expression, reference) if deadline_expression else None
        resolved.append(
            Item(
                type=candidate.type,
                topic=candidate.topic.strip(),
                text=candidate.text.strip(),
                owner_name=owner_name,
                deadline_expression=deadline_expression,
                deadline=deadline,
                recurring=candidate.recurring,
                confidence=candidate.confidence,
                source_quote=candidate.source_quote,
                speaker=candidate.speaker.strip(),
            )
        )
    return resolved
