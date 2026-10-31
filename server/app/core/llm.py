"""Async Anthropic JSON helper."""

import json
from typing import TypeVar

from anthropic import AsyncAnthropic
from pydantic import BaseModel, ValidationError

from app.config import settings

ModelT = TypeVar("ModelT", bound=BaseModel)
client = AsyncAnthropic(api_key=settings.anthropic_api_key)


async def request_json(response_model: type[ModelT], prompt: str) -> ModelT:
    """Ask the configured model for JSON and validate it, retrying invalid output once."""
    for attempt in range(2):
        response = await client.messages.create(
            model=settings.anthropic_model,
            max_tokens=2048,
            system="Respond with only valid JSON matching the requested schema.",
            messages=[{"role": "user", "content": prompt}],
        )
        raw_output = next(
            (block.text for block in response.content if block.type == "text"),
            "",
        )
        try:
            return response_model.model_validate_json(raw_output)
        except (ValidationError, json.JSONDecodeError) as error:
            if attempt == 1:
                raise ValueError("Anthropic returned invalid JSON for the requested schema.") from error
            prompt = f"{prompt}\n\nYour previous response was invalid. Return valid JSON only."
    raise RuntimeError("The JSON retry loop exited unexpectedly.")
