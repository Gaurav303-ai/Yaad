"""Approval-gated email delivery through Resend."""

import httpx

from app.config import settings


async def send_email(recipient: str, subject: str, body: str) -> str:
    """Send one approved digest and return the provider message ID."""
    if not settings.resend_api_key or not settings.digest_from_email:
        raise RuntimeError("Set RESEND_API_KEY and DIGEST_FROM_EMAIL to enable email.")
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {settings.resend_api_key}"},
                json={
                    "from": settings.digest_from_email,
                    "to": [recipient],
                    "subject": subject,
                    "text": body,
                },
            )
    except httpx.HTTPError as error:
        raise RuntimeError("Resend email delivery failed due to a network error.") from error
    if response.is_error:
        raise RuntimeError(f"Resend email delivery failed (HTTP {response.status_code}).")
    try:
        response_body: object = response.json()
    except ValueError as error:
        raise RuntimeError("Resend returned an invalid email response.") from error
    message_id = (
        response_body.get("id")
        if isinstance(response_body, dict)
        else None
    )
    if not isinstance(message_id, str) or not message_id:
        raise RuntimeError("Resend accepted no message ID.")
    return message_id
