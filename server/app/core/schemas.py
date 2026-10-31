"""Shared Pydantic schema placeholders."""

from pydantic import BaseModel


class Item(BaseModel):
    """TODO: Define the item schema."""


class Decision(BaseModel):
    """TODO: Define the decision schema."""


class Conflict(BaseModel):
    """TODO: Define the conflict schema."""


class ExtractionResult(BaseModel):
    """TODO: Define the extraction result schema."""
