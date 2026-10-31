"""Optional Voyage embeddings for decision-memory retrieval."""

import httpx
from pydantic import BaseModel

from app.config import settings


class _Embedding(BaseModel):
    """Voyage embedding response row."""

    embedding: list[float]


class _EmbeddingResponse(BaseModel):
    """Validated subset of the Voyage embeddings response."""

    data: list[_Embedding]


async def embed_text(text: str, *, input_type: str = "document") -> list[float] | None:
    """Embed text when Voyage is configured; return None for the supported no-key fallback."""
    if settings.embeddings_provider.casefold() in {"", "none"}:
        return None
    if settings.embeddings_provider.casefold() != "voyage":
        raise ValueError(f"Unsupported embeddings provider: {settings.embeddings_provider}")
    if not settings.voyage_api_key:
        return None
    if not text.strip():
        raise ValueError("Cannot create an embedding for empty text.")

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            "https://api.voyageai.com/v1/embeddings",
            headers={"Authorization": f"Bearer {settings.voyage_api_key}"},
            json={
                "model": "voyage-3-lite",
                "input": [text],
                "input_type": input_type,
            },
        )
        response.raise_for_status()

    parsed = _EmbeddingResponse.model_validate(response.json())
    if len(parsed.data) != 1:
        raise ValueError("Voyage returned an unexpected number of embeddings.")
    return parsed.data[0].embedding
