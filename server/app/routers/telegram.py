"""Telegram webhook and human approval commands."""

import logging
import secrets
from uuid import UUID

import httpx
from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, ValidationError
from postgrest.exceptions import APIError
from supabase import AsyncClient

from app.config import settings
from app.routers.items import _approve_item, _load_review_row
from app.routers.meetings import SupabaseDependency

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/telegram", tags=["telegram"])


class _TelegramChat(BaseModel):
    """Authorized Telegram chat identifier."""

    id: int


class _TelegramMessage(BaseModel):
    """Message fields needed for approval commands."""

    text: str | None = None
    chat: _TelegramChat


class _TelegramUpdate(BaseModel):
    """Minimal supported Telegram update envelope."""

    message: _TelegramMessage | None = None


async def process_telegram_update(
    supabase: AsyncClient,
    update: dict[str, object],
) -> None:
    """Apply an explicit /approve or /reject command from the configured chat."""
    try:
        parsed = _TelegramUpdate.model_validate(update)
    except ValidationError:
        logger.warning("Ignoring malformed Telegram update.")
        return
    message = parsed.message
    if (
        message is None
        or message.text is None
        or settings.telegram_chat_id is None
        or str(message.chat.id) != settings.telegram_chat_id
    ):
        return

    parts = message.text.strip().split()
    if len(parts) != 2 or parts[0] not in {"/approve", "/reject"}:
        return
    try:
        item_id = UUID(parts[1])
    except ValueError:
        logger.warning("Ignoring Telegram approval command with an invalid item ID.")
        return

    try:
        if parts[0] == "/approve":
            await _approve_item(supabase, item_id)
            return
        item = await _load_review_row(supabase, item_id)
        if item.status != "pending" and not (
            item.status == "approved" and item.tracker_ref is None
        ):
            logger.info("Telegram rejection ignored because the item is no longer actionable.")
            return
        await (
            supabase.table("items")
            .update({"status": "rejected"})
            .eq("id", str(item_id))
            .execute()
        )
    except (APIError, httpx.HTTPError, HTTPException, RuntimeError) as error:
        logger.warning(
            "Telegram approval command could not be completed (%s).",
            type(error).__name__,
        )


@router.post("/webhook")
async def telegram_webhook(
    update: dict[str, object],
    supabase: SupabaseDependency,
    secret_token: str | None = Header(default=None, alias="X-Telegram-Bot-Api-Secret-Token"),
) -> dict[str, str]:
    """Accept production bot updates after validating Telegram's webhook secret."""
    if settings.app_env == "development":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Use Telegram long polling during development.",
        )
    if not settings.telegram_webhook_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Set TELEGRAM_WEBHOOK_SECRET before enabling the Telegram webhook.",
        )
    if secret_token is None or not secrets.compare_digest(
        secret_token,
        settings.telegram_webhook_secret,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Telegram webhook authentication failed.",
        )
    await process_telegram_update(supabase, update)
    return {"status": "ok"}
