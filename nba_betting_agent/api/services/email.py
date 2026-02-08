"""Email sending via Resend API."""

import logging

import httpx

from nba_betting_agent.api.config import Settings

logger = logging.getLogger(__name__)


async def send_verification_email(email: str, token: str, settings: Settings) -> bool:
    """Send email verification link via Resend API.

    Returns True if sent successfully, False otherwise.
    """
    if not settings.resend_api_key:
        logger.warning("RESEND_API_KEY not configured, skipping verification email")
        return False

    verification_url = f"{settings.frontend_url}/verify-email?token={token}"

    payload = {
        "from": settings.resend_from_email,
        "to": [email],
        "subject": "Verify your SportAgent account",
        "html": (
            f"<h2>Welcome to SportAgent</h2>"
            f"<p>Click the link below to verify your email address:</p>"
            f'<p><a href="{verification_url}">Verify Email</a></p>'
            f"<p>This link expires in {settings.email_verification_token_expire_hours} hours.</p>"
            f"<p>If you didn't create an account, you can ignore this email.</p>"
        ),
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.resend.com/emails",
                json=payload,
                headers={"Authorization": f"Bearer {settings.resend_api_key}"},
                timeout=10.0,
            )
            if resp.status_code == 200:
                logger.info("Verification email sent to %s", email)
                return True
            else:
                logger.error("Resend API error %d: %s", resp.status_code, resp.text)
                return False
    except httpx.HTTPError as e:
        logger.error("Failed to send verification email: %s", e)
        return False
