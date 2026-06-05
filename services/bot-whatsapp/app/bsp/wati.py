#genai: Sprint 5 / WS-E — WATI BSP implementation.
"""
WATI is our chosen launch BSP (cheapest at low volume, India-friendly, easy
webhook). Their inbound webhook flattens everything into a single JSON
object with `eventType` and `type` keys. Outbound calls hit
`/sendInteractiveButtonsMessage`, `/sendInteractiveListMessage`,
`/sendSessionFile`, or `/sendSessionMessage` depending on payload.

Reference (last seen): https://docs.wati.io/reference
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

from app.bsp.base import (
    BspError,
    BspProvider,
    InboundMedia,
    InboundMessage,
    OutboundMessage,
)
from app.config import get_settings

logger = logging.getLogger(__name__)


class WatiBsp(BspProvider):
    name = "wati"

    def __init__(self, api_base: str, token: str):
        self.api_base = api_base.rstrip("/")
        self.token = token
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=10.0),
            headers={"Authorization": f"Bearer {token}"} if token else {},
        )

    # ── Webhook ──────────────────────────────────────────────────────────────

    async def parse_webhook(self, body: dict[str, Any]) -> list[InboundMessage]:
        """
        WATI sends one event at a time. Shape (abbreviated):
          {
            "id": "...", "eventType": "message",
            "waId": "918012345678", "type": "text|image|document|interactive",
            "text": "hi", "senderName": "Akarshit",
            "data": "<base64 if media>" | null,
            "buttonReply": {"text": "...", "payload": "..."} | null
          }
        """
        event = body.get("eventType") or body.get("type") or ""
        msg_id = str(body.get("id") or body.get("messageId") or "")
        wa_id = body.get("waId") or body.get("from") or ""
        e164 = _to_e164(str(wa_id))
        from_name = body.get("senderName")

        if not msg_id or not e164:
            return []

        kind = "text"
        text = None
        media = None
        interactive_payload = None

        msg_type = (body.get("type") or "").lower()
        if msg_type in {"text", ""} and body.get("text"):
            kind = "text"
            text = str(body.get("text"))
        elif msg_type in {"document", "image", "audio", "video"}:
            kind = "media"
            text = body.get("caption") or body.get("text")
            media = InboundMedia(
                media_id=str(body.get("id") or body.get("messageId") or ""),
                mime_type=body.get("mimeType") or body.get("mime_type"),
                filename=body.get("fileName") or body.get("filename"),
                size_bytes=_int_or_none(body.get("size") or body.get("fileSize")),
            )
        elif msg_type == "interactive" or body.get("buttonReply") or body.get("listReply"):
            button = body.get("buttonReply") or {}
            lst = body.get("listReply") or {}
            kind = "button" if button else "list"
            text = button.get("text") or lst.get("title")
            interactive_payload = button.get("payload") or lst.get("id")
        else:
            kind = "unknown"

        return [
            InboundMessage(
                message_id=msg_id,
                from_e164=e164,
                from_name=from_name,
                kind=kind,
                text=text,
                interactive_payload=interactive_payload,
                media=media,
                raw=body,
            )
        ]

    # ── Media fetch ──────────────────────────────────────────────────────────

    async def fetch_media(self, message: InboundMessage) -> tuple[bytes, str]:
        if not message.media:
            raise BspError("Message has no media attachment.")
        url = f"{self.api_base}/getMedia?fileName={message.media.media_id}"
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=0.4, max=4),
            retry=retry_if_exception_type((httpx.HTTPError,)),
            reraise=True,
        ):
            with attempt:
                resp = await self._client.get(url)
                if resp.status_code >= 400:
                    raise BspError(f"WATI media fetch failed: {resp.status_code}")
                filename = message.media.filename or f"{message.media.media_id}.bin"
                return resp.content, filename
        raise BspError("WATI media fetch failed after retries.")  # pragma: no cover

    # ── Send ────────────────────────────────────────────────────────────────

    async def send(self, message: OutboundMessage) -> str:
        to = _strip_plus(message.to_e164)
        if message.document_url:
            return await self._send_document(to, message)
        if message.buttons:
            return await self._send_buttons(to, message)
        if message.list_items:
            return await self._send_list(to, message)
        return await self._send_text(to, message)

    async def _send_text(self, to: str, m: OutboundMessage) -> str:
        url = f"{self.api_base}/sendSessionMessage/{to}"
        resp = await self._client.post(url, params={"messageText": m.text or ""})
        return self._extract_id(resp, "send_text")

    async def _send_buttons(self, to: str, m: OutboundMessage) -> str:
        url = f"{self.api_base}/sendInteractiveButtonsMessage"
        payload = {
            "whatsappNumber": to,
            "body": m.text or "",
            "buttons": [
                {"text": b.title, "buttonId": b.payload[:200]} for b in m.buttons[:3]
            ],
        }
        resp = await self._client.post(url, json=payload)
        return self._extract_id(resp, "send_buttons")

    async def _send_list(self, to: str, m: OutboundMessage) -> str:
        url = f"{self.api_base}/sendInteractiveListMessage"
        payload = {
            "whatsappNumber": to,
            "header": m.list_title or "Options",
            "body": m.text or "",
            "buttonText": m.list_button_label or "Choose",
            "sections": [
                {
                    "title": m.list_title or "Options",
                    "rows": [
                        {
                            "id": item.payload or item.title,
                            "title": item.title[:24],
                            "description": (item.description or "")[:72],
                        }
                        for item in m.list_items[:10]
                    ],
                }
            ],
        }
        resp = await self._client.post(url, json=payload)
        return self._extract_id(resp, "send_list")

    async def _send_document(self, to: str, m: OutboundMessage) -> str:
        url = f"{self.api_base}/sendSessionFile/{to}"
        payload = {
            "fileLink": m.document_url,
            "caption": m.document_caption or "",
            "fileName": m.document_filename or "file",
        }
        resp = await self._client.post(url, json=payload)
        return self._extract_id(resp, "send_document")

    def _extract_id(self, resp: httpx.Response, op: str) -> str:
        if resp.status_code >= 400:
            logger.warning("WATI %s failed: %s %s", op, resp.status_code, resp.text[:200])
            raise BspError(f"WATI {op} failed: {resp.status_code}")
        try:
            data = resp.json()
        except Exception:  # pragma: no cover
            return ""
        return str(data.get("id") or data.get("messageId") or "")

    def verify_signature(self, headers: dict[str, str], body: bytes) -> bool:
        """WATI lets you configure a static verify token in their console;
        we expect it in the `Authorization` header on inbound webhooks."""
        expected = get_settings().wati_verify_token
        if not expected:
            return True  # not configured → accept (dev mode)
        provided = headers.get("authorization") or headers.get("Authorization") or ""
        return provided.endswith(expected) or provided == expected


def _to_e164(wa_id: str) -> str:
    """WATI returns `'918012345678'`; we standardise to `'+918012345678'`."""
    wa_id = wa_id.strip()
    if not wa_id:
        return ""
    return wa_id if wa_id.startswith("+") else f"+{wa_id}"


def _strip_plus(e164: str) -> str:
    return e164[1:] if e164.startswith("+") else e164


def _int_or_none(v: Any) -> int | None:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None
