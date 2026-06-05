#genai: Sprint 5 / WS-E — Thin HTTP client to the DocSeva API.
"""
Mirrors the Telegram bot's api_client. Sends X-Bot-Token + X-User-Id (the
caller's E.164 with the leading '+') + X-Channel='whatsapp'. The API's
`resolve_caller` dependency handles the rest.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import get_settings

logger = logging.getLogger(__name__)


class ApiError(RuntimeError):
    def __init__(self, status: int, code: str | None, message: str, retryable: bool = False):
        super().__init__(message)
        self.status = status
        self.code = code
        self.retryable = retryable


def _client() -> httpx.AsyncClient:
    s = get_settings()
    return httpx.AsyncClient(timeout=httpx.Timeout(s.request_timeout_seconds, connect=10.0))


def _headers(e164: str, *, extra: dict[str, str] | None = None) -> dict[str, str]:
    s = get_settings()
    h: dict[str, str] = {
        "X-Bot-Token": s.api_bot_token,
        "X-User-Id": e164,
        "X-Channel": "whatsapp",
    }
    if extra:
        h.update(extra)
    return h


async def register_channel(*, e164: str, name: str, company_name: str) -> dict[str, Any]:
    """Idempotent — call on the first user message. Returns the AuthResponse."""
    s = get_settings()
    body = {
        "channel": "whatsapp",
        "handle": e164,
        "name": name,
        "company_name": company_name,
        "phone": e164,
        "verified": True,
    }
    async with _client() as c:
        resp = await c.post(
            f"{s.api_base_url}/api/v1/auth/register-channel",
            json=body,
            headers={"X-Bot-Token": s.api_bot_token},
        )
        _raise_for_status(resp, "register-channel")
        return resp.json()


async def process_feature(
    *,
    e164: str,
    feature: str,
    file_bytes: bytes,
    filename: str,
    mode: str = "final",
    params: dict[str, Any] | None = None,
    format_id: str | None = None,
) -> dict[str, Any]:
    """POST /api/v1/process/<feature> with the user's file."""
    s = get_settings()
    data: dict[str, Any] = {"mode": mode}
    if params:
        import json as _json
        data["params"] = _json.dumps(params)
    if format_id:
        data["format_id"] = format_id

    async for attempt in AsyncRetrying(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, max=4),
        retry=retry_if_exception_type((httpx.HTTPError, ApiError)),
        reraise=True,
    ):
        with attempt:
            async with _client() as c:
                files = {"file": (filename, file_bytes)}
                resp = await c.post(
                    f"{s.api_base_url}/api/v1/process/{feature}",
                    data=data,
                    files=files,
                    headers=_headers(e164),
                )
                _raise_for_status(resp, "process")
                return resp.json()
    raise ApiError(500, "E005", "process retries exhausted")  # pragma: no cover


async def list_sister_formats(e164: str) -> list[dict[str, Any]]:
    s = get_settings()
    async with _client() as c:
        resp = await c.get(
            f"{s.api_base_url}/api/v1/me/sister-formats",
            headers=_headers(e164),
        )
        _raise_for_status(resp, "list-formats")
        body = resp.json()
        return body if isinstance(body, list) else []


async def confirm_channel_link(*, e164: str, token: str) -> dict[str, Any]:
    """Web → WhatsApp linking: the user types `/link <token>` and we POST it."""
    s = get_settings()
    body = {"token": token, "handle": e164, "channel": "whatsapp"}
    async with _client() as c:
        resp = await c.post(
            f"{s.api_base_url}/api/v1/channels/link",
            json=body,
            headers={"X-Bot-Token": s.api_bot_token},
        )
        _raise_for_status(resp, "channels/link")
        return resp.json()


def _raise_for_status(resp: httpx.Response, op: str) -> None:
    if resp.status_code < 400:
        return
    code = None
    message = resp.text or resp.reason_phrase or f"HTTP {resp.status_code}"
    retryable = resp.status_code >= 500
    try:
        body = resp.json()
        if isinstance(body, dict):
            detail = body.get("detail")
            if isinstance(detail, dict):
                code = detail.get("code")
                message = detail.get("user_message") or message
                retryable = bool(detail.get("retryable", retryable))
            elif isinstance(detail, str):
                message = detail
    except Exception:  # pragma: no cover
        pass
    logger.warning("API %s failed: %s %s code=%s", op, resp.status_code, message, code)
    raise ApiError(resp.status_code, code, message, retryable=retryable)
