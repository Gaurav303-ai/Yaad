"""Tests for structured decision-memory matching and embedding fallback."""

import asyncio

import pytest

from app.agents.memory import topics_related
from app.core import embeddings


@pytest.mark.parametrize(
    ("first", "second", "expected"),
    [
        ("Vendor installment 2", "Vendor installment 2 payment", True),
        ("Weekly demo schedule", "Weekly demo to Thursdays at 4 pm", True),
        ("Launch date", "Launch schedule", True),
        ("Vendor installment 1", "Vendor installment 2", False),
        ("Press note", "Login bug", False),
    ],
)
def test_structured_topic_filter(first: str, second: str, expected: bool) -> None:
    """Topic filtering retains cross-meeting concepts but separates distinct commitments."""
    assert topics_related(first, second) is expected


def test_embedding_lookup_falls_back_when_voyage_key_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing optional Voyage credentials select structured topic matching."""
    monkeypatch.setattr(embeddings.settings, "embeddings_provider", "voyage")
    monkeypatch.setattr(embeddings.settings, "voyage_api_key", None)

    assert asyncio.run(embeddings.embed_text("Weekly demo schedule")) is None


def test_memory_topic_filter_does_not_infer_conflicts_from_shared_generic_words() -> None:
    """A generic shared term alone is not sufficient to compare two decisions."""
    assert not topics_related("Paid ads policy", "Ads launch timing")
