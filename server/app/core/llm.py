"""Async Gemini JSON helper."""

import json
from typing import TypeVar

from google import genai
from google.genai import types
from pydantic import BaseModel, ValidationError

from app.config import settings

ModelT = TypeVar("ModelT", bound=BaseModel)
client = genai.Client(api_key=settings.gemini_api_key)


async def request_json(response_model: type[ModelT], prompt: str) -> ModelT:
    """Ask the configured model for JSON and validate it, retrying invalid output once."""
    for attempt in range(2):
        response = await client.aio.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=2048,
                system_instruction="Respond with only valid JSON matching the requested schema.",
                response_mime_type="application/json",
            ),
        )
        raw_output = response.text or ""
        try:
            return response_model.model_validate_json(raw_output)
        except (ValidationError, json.JSONDecodeError) as error:
            if attempt == 1:
                raise ValueError("Gemini returned invalid JSON for the requested schema.") from error
            prompt = f"{prompt}\n\nYour previous response was invalid. Return valid JSON only."
    raise RuntimeError("The JSON retry loop exited unexpectedly.")
