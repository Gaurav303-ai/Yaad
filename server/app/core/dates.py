"""Relative date helper placeholders for Asia/Kolkata."""

from datetime import datetime
from zoneinfo import ZoneInfo

INDIA_TIMEZONE = ZoneInfo("Asia/Kolkata")


def parse_relative_date(expression: str, reference: datetime) -> datetime | None:
    """TODO: Parse kal, parso, is Friday tak, agle Monday, agle mahine ke end, and next Wednesday."""
    ...
