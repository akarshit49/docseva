#genai: Sprint 1 / WS-A — minimal email sender abstraction (OTP delivery).
"""
Email abstraction. In development / staging we just log the OTP so the team can
copy-paste from the API logs; in production we route through Resend/SendGrid.

The interface is `send_email(to, subject, html, text)` — feel free to add a
real SDK call in `_send_via_provider` later without touching callers.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class EmailMessage:
    to: str
    subject: str
    html: str
    text: str


def send_email(msg: EmailMessage) -> None:
    """Send `msg`. Falls back to a log line when no provider is configured."""
    provider = os.environ.get("EMAIL_PROVIDER", "").lower()
    if provider in ("", "log", "console"):
        logger.info(
            "EMAIL[dev] → to=%s subject=%s\n%s",
            msg.to,
            msg.subject,
            msg.text,
        )
        return
    _send_via_provider(provider, msg)


def _send_via_provider(provider: str, msg: EmailMessage) -> None:
    if provider == "resend":
        _send_via_resend(msg)
        return
    if provider == "sendgrid":
        _send_via_sendgrid(msg)
        return
    logger.warning("Unknown EMAIL_PROVIDER=%r; falling back to log.", provider)
    logger.info("EMAIL[fallback] → to=%s subject=%s\n%s", msg.to, msg.subject, msg.text)


def _send_via_resend(msg: EmailMessage) -> None:
    import httpx

    key = os.environ.get("RESEND_API_KEY")
    if not key:
        logger.warning("EMAIL_PROVIDER=resend but RESEND_API_KEY is missing.")
        return
    sender = os.environ.get("EMAIL_FROM", "DocSeva <noreply@docseva.in>")
    resp = httpx.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {key}"},
        json={
            "from": sender,
            "to": [msg.to],
            "subject": msg.subject,
            "html": msg.html,
            "text": msg.text,
        },
        timeout=15,
    )
    if resp.status_code >= 400:
        logger.error("Resend send failed: %s %s", resp.status_code, resp.text)


def _send_via_sendgrid(msg: EmailMessage) -> None:
    import httpx

    key = os.environ.get("SENDGRID_API_KEY")
    if not key:
        logger.warning("EMAIL_PROVIDER=sendgrid but SENDGRID_API_KEY is missing.")
        return
    sender = os.environ.get("EMAIL_FROM", "noreply@docseva.in")
    resp = httpx.post(
        "https://api.sendgrid.com/v3/mail/send",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        json={
            "personalizations": [{"to": [{"email": msg.to}]}],
            "from": {"email": sender, "name": "DocSeva"},
            "subject": msg.subject,
            "content": [
                {"type": "text/plain", "value": msg.text},
                {"type": "text/html", "value": msg.html},
            ],
        },
        timeout=15,
    )
    if resp.status_code >= 400:
        logger.error("SendGrid send failed: %s %s", resp.status_code, resp.text)
