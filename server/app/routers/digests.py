"""Human-approved weekly digest drafts and email delivery."""

from datetime import datetime
from uuid import UUID

import httpx
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, TypeAdapter
from postgrest.exceptions import APIError
from supabase import AsyncClient

from app.core.dates import INDIA_TIMEZONE
from app.core.email import send_email
from app.jobs.digest import prepare_weekly_digest_drafts
from app.routers.meetings import SupabaseDependency

router = APIRouter(prefix="/digests", tags=["digests"])


class DigestDraftRequest(BaseModel):
    """Request a person-specific weekly preview draft."""

    member_id: UUID


class _DigestRow(BaseModel):
    """Persisted per-person digest content."""

    id: UUID
    member_id: UUID
    week_start: str
    subject: str
    body: str
    status: str
    sent_at: datetime | None = None


class _MemberEmail(BaseModel):
    """Email destination for an approved digest."""

    id: UUID
    email: str | None


class DigestResponse(BaseModel):
    """Digest preview and review state."""

    id: UUID
    member_id: UUID
    member_name: str
    week_start: str
    subject: str
    body: str
    status: str
    sent_at: datetime | None


digest_rows = TypeAdapter(list[_DigestRow])
member_email_rows = TypeAdapter(list[_MemberEmail])


async def _digest_response(supabase: AsyncClient, row: _DigestRow) -> DigestResponse:
    member_response = await (
        supabase.table("members")
        .select("id,name")
        .eq("id", str(row.member_id))
        .execute()
    )
    member_data = member_response.data
    if not member_data:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Digest references a missing team member.",
        )
    return DigestResponse(
        id=row.id,
        member_id=row.member_id,
        member_name=str(member_data[0]["name"]),
        week_start=row.week_start,
        subject=row.subject,
        body=row.body,
        status=row.status,
        sent_at=row.sent_at,
    )


@router.get("", response_model=list[DigestResponse])
async def list_digests(supabase: SupabaseDependency) -> list[DigestResponse]:
    """List stored digest drafts with their member names."""
    try:
        response = await (
            supabase.table("digests")
            .select("id,member_id,week_start,subject,body,status,sent_at")
            .order("created_at", desc=True)
            .execute()
        )
        rows = digest_rows.validate_python(response.data)
        return [await _digest_response(supabase, row) for row in rows]
    except APIError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Supabase could not load digest previews: {error.message}",
        ) from error
    except httpx.HTTPError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not connect to Supabase while loading digest previews.",
        ) from error


@router.post("/draft", response_model=DigestResponse)
async def create_digest_draft(
    payload: DigestDraftRequest,
    supabase: SupabaseDependency,
) -> DigestResponse:
    """Create internal digest drafts and return the selected person's preview."""
    try:
        await prepare_weekly_digest_drafts(supabase)
        response = await (
            supabase.table("digests")
            .select("id,member_id,week_start,subject,body,status,sent_at")
            .eq("member_id", str(payload.member_id))
            .order("week_start", desc=True)
            .limit(1)
            .execute()
        )
        rows = digest_rows.validate_python(response.data)
        if not rows:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No digest preview could be prepared for this member.",
            )
        return await _digest_response(supabase, rows[0])
    except APIError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Supabase could not prepare the digest preview: {error.message}",
        ) from error
    except httpx.HTTPError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not connect to Supabase while preparing the digest preview.",
        ) from error


@router.post("/{digest_id}/approve", response_model=DigestResponse)
async def approve_digest(digest_id: UUID, supabase: SupabaseDependency) -> DigestResponse:
    """Send an email digest only after a human has approved its preview."""
    try:
        response = await (
            supabase.table("digests")
            .select("id,member_id,week_start,subject,body,status,sent_at")
            .eq("id", str(digest_id))
            .execute()
        )
        rows = digest_rows.validate_python(response.data)
        if not rows:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Digest not found.")
        digest = rows[0]
        if digest.status not in {"pending", "approved"}:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Digest cannot be sent from status '{digest.status}'.",
            )
        member_response = await (
            supabase.table("members")
            .select("id,email")
            .eq("id", str(digest.member_id))
            .execute()
        )
        members = member_email_rows.validate_python(member_response.data)
        if not members or not members[0].email:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Add this member's email address before sending a digest.",
            )
        if digest.status == "pending":
            await (
                supabase.table("digests")
                .update({"status": "approved"})
                .eq("id", str(digest_id))
                .execute()
            )
        await send_email(members[0].email, digest.subject, digest.body)
        sent_at = datetime.now(INDIA_TIMEZONE)
        result = await (
            supabase.table("digests")
            .update({"status": "sent", "sent_at": sent_at.isoformat()})
            .eq("id", str(digest_id))
            .execute()
        )
        sent_rows = digest_rows.validate_python(result.data)
        if not sent_rows:
            sent_rows = [digest.model_copy(update={"status": "sent", "sent_at": sent_at})]
        return await _digest_response(supabase, sent_rows[0])
    except RuntimeError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(error),
        ) from error
    except APIError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Supabase could not record digest approval: {error.message}",
        ) from error
    except httpx.HTTPError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not connect to Supabase while sending the digest.",
        ) from error


@router.post("/{digest_id}/reject")
async def reject_digest(digest_id: UUID, supabase: SupabaseDependency) -> dict[str, str]:
    """Permanently remove a pending digest from the send queue."""
    try:
        response = await (
            supabase.table("digests")
            .select("id,status")
            .eq("id", str(digest_id))
            .execute()
        )
        if not response.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Digest not found.")
        if response.data[0]["status"] != "pending":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Only pending digests can be rejected.",
            )
        await (
            supabase.table("digests")
            .update({"status": "rejected"})
            .eq("id", str(digest_id))
            .execute()
        )
        return {"status": "rejected"}
    except APIError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Supabase could not reject the digest: {error.message}",
        ) from error
