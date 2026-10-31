"""Telegram reminder delivery for human-approved action items."""

import logging
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

import httpx
from pydantic import BaseModel, TypeAdapter
from postgrest.exceptions import APIError
from supabase import AsyncClient

from app.core.dates import INDIA_TIMEZONE
from app.core.telegram import send_telegram_message

logger = logging.getLogger(__name__)


class _ReminderRow(BaseModel):
    """Due reminder waiting to be delivered."""

    id: UUID
    item_id: UUID
    send_at: datetime


class _ReminderItemRow(BaseModel):
    """Approved action context used to build a reminder."""

    id: UUID
    type: Literal["decision", "action", "intent"]
    text: str
    deadline: datetime | None
    status: Literal["pending", "approved", "rejected", "done"]


reminder_rows = TypeAdapter(list[_ReminderRow])
reminder_item_rows = TypeAdapter(list[_ReminderItemRow])


async def send_due_reminders(supabase: AsyncClient | None = None) -> None:
    """Send due reminders only for actions that are still approved."""
    if supabase is None:
        raise RuntimeError("The reminder job requires the application Supabase client.")
    now = datetime.now(UTC)
    try:
        response = await (
            supabase.table("reminders")
            .select("id,item_id,send_at")
            .eq("channel", "telegram")
            .eq("sent", False)
            .lte("send_at", now.isoformat())
            .order("send_at")
            .execute()
        )
        due_reminders = reminder_rows.validate_python(response.data)
        for reminder in due_reminders:
            item_response = await (
                supabase.table("items")
                .select("id,type,text,deadline,status")
                .eq("id", str(reminder.item_id))
                .execute()
            )
            item_rows = reminder_item_rows.validate_python(item_response.data)
            if not item_rows:
                await _mark_sent(supabase, reminder.id)
                continue
            item = item_rows[0]
            if item.type != "action" or item.status != "approved":
                await _mark_sent(supabase, reminder.id)
                continue

            deadline_text = (
                item.deadline.astimezone(INDIA_TIMEZONE).strftime("%a, %d %b %Y %H:%M")
                if item.deadline
                else "the demo reminder is due"
            )
            await send_telegram_message(
                f"Yaad reminder: {item.text}\nDeadline: {deadline_text}"
            )
            await _mark_sent(supabase, reminder.id)
    except APIError as error:
        logger.error("Supabase reminder operation failed: %s", error.message)
        raise
    except httpx.HTTPError:
        logger.error("Supabase connection failed while processing reminders.")
        raise
    except RuntimeError as error:
        logger.error("Telegram reminder delivery failed: %s", error)
        raise


async def _mark_sent(supabase: AsyncClient, reminder_id: UUID) -> None:
    await (
        supabase.table("reminders")
        .update({"sent": True})
        .eq("id", str(reminder_id))
        .execute()
    )
