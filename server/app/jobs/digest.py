"""Weekly personalized digest draft generation."""

import logging
from datetime import datetime, timedelta
from uuid import UUID

from pydantic import BaseModel, TypeAdapter
from postgrest.exceptions import APIError
from supabase import AsyncClient

from app.core.dates import INDIA_TIMEZONE

logger = logging.getLogger(__name__)


class _MemberRow(BaseModel):
    """Member receiving a personalized weekly digest."""

    id: UUID
    name: str


class _DigestItemRow(BaseModel):
    """Approved or completed action selected for a digest."""

    id: UUID
    owner_id: UUID | None
    type: str
    topic: str
    text: str
    deadline: str | None
    status: str


member_rows = TypeAdapter(list[_MemberRow])
digest_item_rows = TypeAdapter(list[_DigestItemRow])


async def prepare_weekly_digest_drafts(supabase: AsyncClient | None = None) -> None:
    """Create one pending digest per member; sending requires separate approval."""
    if supabase is None:
        raise RuntimeError("The digest job requires the application Supabase client.")

    today = datetime.now(INDIA_TIMEZONE).date()
    week_start = today - timedelta(days=7)
    try:
        members_response = await supabase.table("members").select("id,name").execute()
        item_response = await (
            supabase.table("items")
            .select("id,owner_id,type,topic,text,deadline,status")
            .in_("status", ["approved", "done"])
            .gte("created_at", week_start.isoformat())
            .lt("created_at", today.isoformat())
            .execute()
        )
        members = member_rows.validate_python(members_response.data)
        items = digest_item_rows.validate_python(item_response.data)
        for member in members:
            existing_response = await (
                supabase.table("digests")
                .select("id")
                .eq("member_id", str(member.id))
                .eq("week_start", week_start.isoformat())
                .execute()
            )
            if existing_response.data:
                continue
            member_items = [item for item in items if item.owner_id == member.id]
            grouped: dict[str, list[_DigestItemRow]] = {
                "action": [],
                "decision": [],
                "intent": [],
            }
            for item in member_items:
                if item.type in grouped:
                    grouped[item.type].append(item)

            lines = [
                f"Hi {member.name},",
                "",
                f"Your Yaad update for {week_start.isoformat()} through {(today - timedelta(days=1)).isoformat()}:",
                "",
            ]
            for label, heading in (
                ("action", "Actions"),
                ("decision", "Decisions"),
                ("intent", "Intents"),
            ):
                lines.append(f"{heading}:")
                lines.extend(
                    f"- {item.text} (deadline: {item.deadline or 'not set'})"
                    for item in grouped[label]
                )
                if not grouped[label]:
                    lines.append("- None")
                lines.append("")
            subject = f"Yaad weekly digest · {week_start.isoformat()}"
            await supabase.table("digests").insert(
                {
                    "member_id": str(member.id),
                    "week_start": week_start.isoformat(),
                    "subject": subject,
                    "body": "\n".join(lines).strip(),
                }
            ).execute()
    except APIError as error:
        logger.error("Supabase could not prepare weekly digest drafts: %s", error.message)
        raise
