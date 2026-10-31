"""Telegram delivery and development long-polling transport."""

import asyncio
import logging
from collections.abc import Awaitable, Callable

import httpx

from app.config import settings

logger = logging.getLogger(__name__)
TelegramUpdateHandler = Callable[[dict[str, object]], Awaitable[None]]


async def send_telegram_message(text: str) -> None:
    """Deliver a message to the configured Telegram chat."""
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        raise RuntimeError("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID to enable Telegram.")
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
                json={"chat_id": settings.telegram_chat_id, "text": text},
            )
    except httpx.HTTPError as error:
        raise RuntimeError("Telegram API connection failed.") from error
    if response.is_error:
        raise RuntimeError(f"Telegram message delivery failed (HTTP {response.status_code}).")
    try:
        body: object = response.json()
    except ValueError as error:
        raise RuntimeError("Telegram returned an invalid send response.") from error
    accepted = body.get("ok") if isinstance(body, dict) else None
    if accepted is not True:
        raise RuntimeError("Telegram did not accept the message.")


async def start_telegram(
    handler: TelegramUpdateHandler,
) -> asyncio.Task[None] | None:
    """Start development long polling; production receives webhook updates."""
    if settings.app_env != "development":
        return None
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        logger.info("Telegram long polling is disabled until bot token and chat ID are configured.")
        return None
    return asyncio.create_task(_poll_updates(handler), name="yaad-telegram-polling")


async def _poll_updates(handler: TelegramUpdateHandler) -> None:
    """Poll Telegram updates and retry transient failures without logging secrets."""
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required for long polling.")
    endpoint = f"https://api.telegram.org/bot{settings.telegram_bot_token}/getUpdates"
    offset: int | None = None
    async with httpx.AsyncClient(timeout=35) as client:
        while True:
            try:
                response = await client.get(
                    endpoint,
                    params={"timeout": 25, "offset": offset},
                )
                response.raise_for_status()
                body: object = response.json()
                updates_value = body.get("result", []) if isinstance(body, dict) else []
                if not isinstance(updates_value, list):
                    raise ValueError("Telegram update payload was not a list.")
                for update in updates_value:
                    if not isinstance(update, dict):
                        continue
                    update_id = update.get("update_id")
                    if isinstance(update_id, int):
                        offset = update_id + 1
                    await handler({str(key): value for key, value in update.items()})
            except asyncio.CancelledError:
                raise
            except (httpx.HTTPError, ValueError, RuntimeError):
                logger.warning("Telegram long polling failed; retrying shortly.")
                await asyncio.sleep(5)
