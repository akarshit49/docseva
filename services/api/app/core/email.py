#genai: Sprint 1 / WS-A — minimal email sender abstraction (OTP delivery).
"""
Email abstraction. Supports multiple providers via EMAIL_PROVIDER env var:
  log      — print OTP to Docker stdout (default / dev mode)
  smtp     — any SMTP server; use SMTP_HOST/PORT/USER/PASS/FROM (works with Gmail)
  resend   — Resend API (requires verified domain for unrestricted delivery)
  sendgrid — SendGrid API

Gmail SMTP setup (recommended for no-domain testing):
  1. Enable 2-factor auth on your Google account
  2. Go to myaccount.google.com → Security → App passwords → generate one
  3. Set EMAIL_PROVIDER=smtp, SMTP_USER=you@gmail.com, SMTP_PASS=<app-password>

The interface is `send_email(to, subject, html, text)`.
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
        _log_otp_fallback(msg)
        return
    _send_via_provider(provider, msg)


def _send_via_provider(provider: str, msg: EmailMessage) -> None:
    if provider == "smtp":
        _send_via_smtp(msg)
        return
    if provider == "resend":
        _send_via_resend(msg)
        return
    if provider == "sendgrid":
        _send_via_sendgrid(msg)
        return
    logger.warning("Unknown EMAIL_PROVIDER=%r; falling back to log.", provider)
    _log_otp_fallback(msg)


def _send_via_smtp(msg: EmailMessage) -> None:
    """Send via any SMTP server — works with Gmail, Outlook, Zoho, custom MTAs."""
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ.get("SMTP_USER", "")
    password = os.environ.get("SMTP_PASS", "")
    sender = os.environ.get("EMAIL_FROM") or os.environ.get("SMTP_USER", "")

    if not user or not password:
        logger.warning("EMAIL_PROVIDER=smtp but SMTP_USER or SMTP_PASS is missing.")
        _log_otp_fallback(msg)
        return

    mime = MIMEMultipart("alternative")
    mime["Subject"] = msg.subject
    mime["From"] = sender
    mime["To"] = msg.to
    mime.attach(MIMEText(msg.text, "plain"))
    mime.attach(MIMEText(msg.html, "html"))

    try:
        with smtplib.SMTP(host, port, timeout=20) as server:
            server.ehlo()
            server.starttls()
            server.login(user, password)
            server.sendmail(sender, [msg.to], mime.as_string())
        logger.info("SMTP email sent → %s", msg.to)
    except Exception as exc:
        logger.error("SMTP send failed: %s", exc)
        _log_otp_fallback(msg)


def _send_via_resend(msg: EmailMessage) -> None:
    import httpx

    key = os.environ.get("RESEND_API_KEY")
    if not key:
        logger.warning("EMAIL_PROVIDER=resend but RESEND_API_KEY is missing.")
        _log_otp_fallback(msg)
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
        # Fall back to logging the OTP so sign-in always works.
        _log_otp_fallback(msg)
    else:
        logger.info("Resend email sent → %s", msg.to)


def _send_via_sendgrid(msg: EmailMessage) -> None:
    import httpx

    key = os.environ.get("SENDGRID_API_KEY")
    if not key:
        logger.warning("EMAIL_PROVIDER=sendgrid but SENDGRID_API_KEY is missing.")
        _log_otp_fallback(msg)
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
        _log_otp_fallback(msg)
    else:
        logger.info("SendGrid email sent → %s", msg.to)


def _log_otp_fallback(msg: EmailMessage) -> None:
    """Always-available fallback: print OTP clearly to Docker logs."""
    logger.info(
        "EMAIL[fallback] → to=%s subject=%s\n%s",
        msg.to,
        msg.subject,
        msg.text,
    )
