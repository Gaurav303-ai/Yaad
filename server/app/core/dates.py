"""Relative deadline parsing for English and common Hinglish phrases."""

import calendar
import re
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import dateparser

INDIA_TIMEZONE = ZoneInfo("Asia/Kolkata")
_WEEKDAYS = {
    "monday": 0,
    "mon": 0,
    "tuesday": 1,
    "tue": 1,
    "tues": 1,
    "wednesday": 2,
    "wed": 2,
    "thursday": 3,
    "thu": 3,
    "thur": 3,
    "thurs": 3,
    "friday": 4,
    "fri": 4,
    "saturday": 5,
    "sat": 5,
    "sunday": 6,
    "sun": 6,
}
_WEEKDAY_PATTERN = "|".join(sorted(_WEEKDAYS, key=len, reverse=True))
_DAY_OF_MONTH = re.compile(r"\b(?P<day>\d{1,2})(?:st|nd|rd|th)?\s*(?:tareekh|tarikh|date|ko)\b", re.IGNORECASE)


def _india_reference(reference: datetime) -> datetime:
    if reference.tzinfo is None:
        return reference.replace(tzinfo=INDIA_TIMEZONE)
    return reference.astimezone(INDIA_TIMEZONE)


def _next_month_end(reference: datetime) -> datetime:
    year = reference.year + (1 if reference.month == 12 else 0)
    month = 1 if reference.month == 12 else reference.month + 1
    last_day = calendar.monthrange(year, month)[1]
    return datetime.combine(datetime(year, month, last_day).date(), time.min, tzinfo=INDIA_TIMEZONE)


def _weekday_deadline(expression: str, reference: datetime) -> datetime | None:
    weekday_match = re.search(rf"\b(?P<weekday>{_WEEKDAY_PATTERN})\b", expression, re.IGNORECASE)
    if weekday_match is None:
        return None

    target_weekday = _WEEKDAYS[weekday_match.group("weekday").casefold()]
    if re.search(r"\b(?:next|agle)\b", expression, re.IGNORECASE):
        current_week_start = reference.date() - timedelta(days=reference.weekday())
        target_date = current_week_start + timedelta(days=7 + target_weekday)
    else:
        days_ahead = (target_weekday - reference.weekday()) % 7
        target_date = reference.date() + timedelta(days=days_ahead)

    return datetime.combine(target_date, time.min, tzinfo=INDIA_TIMEZONE)


def parse_relative_date(expression: str, reference: datetime) -> datetime | None:
    """Resolve common Hinglish and English relative deadlines against meeting time."""
    relative = expression.strip().casefold()
    if not relative or relative in {"none", "n/a", "recurring", "ongoing"}:
        return None

    base = _india_reference(reference)
    if re.search(r"\bparso\b", relative):
        return datetime.combine(base.date() + timedelta(days=2), time.min, tzinfo=INDIA_TIMEZONE)
    if re.search(r"\bkal\b", relative):
        return datetime.combine(base.date() + timedelta(days=1), time.min, tzinfo=INDIA_TIMEZONE)

    if re.search(r"\b(?:agle|next)\s+mahine?\b", relative) and re.search(
        r"\b(?:end|aakhir)\b", relative
    ):
        return _next_month_end(base)

    if re.search(r"\b(?:end of day|eod)\s+(?:tomorrow|kal)\b", relative):
        tomorrow = base.date() + timedelta(days=1)
        return datetime.combine(tomorrow, time(23, 59, 59), tzinfo=INDIA_TIMEZONE)

    day_match = _DAY_OF_MONTH.search(relative)
    if day_match is not None:
        day = int(day_match.group("day"))
        if day > 31:
            return None
        year, month = base.year, base.month
        if day < base.day:
            year += 1 if month == 12 else 0
            month = 1 if month == 12 else month + 1
        try:
            return datetime(year, month, day, tzinfo=INDIA_TIMEZONE)
        except ValueError:
            return None

    weekday = _weekday_deadline(relative, base)
    if weekday is not None:
        return weekday

    parsed = dateparser.parse(
        expression,
        settings={
            "RELATIVE_BASE": base,
            "TIMEZONE": "Asia/Kolkata",
            "RETURN_AS_TIMEZONE_AWARE": True,
            "PREFER_DATES_FROM": "future",
        },
    )
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=INDIA_TIMEZONE)
    return parsed.astimezone(INDIA_TIMEZONE)
