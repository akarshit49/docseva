#genai: Sprint 5 / WS-E — Gupshup BSP implementation (secondary).
"""
Gupshup is our hot-spare BSP. Their webhook ships a `messages[]` array per
event, similar enough to Meta Cloud API that swapping later is a sed-and-test
job. We support text + media + interactive replies; outbound is via the
`/sm/api/v1/msg` and `/sm/api/v1/message` endpoints.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from app.bsp.base import (
    BspError,
    BspProvider,
    InboundMedia,
    InboundMessage,
    OutboundMessage,
)

logger = logging.getLogger(__name__)


class GupshupBsp(BspProvider):
    name = "gupshup"

    def __init__(self, api_base: str, api_key: str, source: str, app_name: str):
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.source = source
        self.app_name = app_name
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=10.0),
            headers={"apikey": api_key} if api_key else {},
        )

    async def parse_webhook(self, body: dict[str, Any]) -> list[InboundMessage]:
        msgs: list[InboundMessage] = []
        payload = body.get("payload") or {}
        sender = payload.get("sender") or {}
        wa_id = sender.get("phone") or ""
        e164 = f"+{wa_id}" if wa_id and not wa_id.startswith("+") else wa_id
        if not e164:
            return msgs

        message_id = payload.get("id") or body.get("messageId") or ""
        ptype = payload.get("type") or "text"
        kind = "text"
        text = None
        media = None
        interactive_payload = None

        if ptype == "text":
            text = payload.get("payload", {}).get("text")
        elif ptype in {"image", "audio", "video", "file", "document"}:
            kind = "media"
            data = payload.get("payload") or {}
            text = data.get("caption")
            media = InboundMedia(
                media_id=str(data.get("url") or data.get("id") or message_id),
                mime_type=data.get("contentType"),
                filename=data.get("name") or data.get("filename"),
                size_bytes=None,
            )
        elif ptype in {"button_reply", "list_reply"}:
            kind = "button" if ptype == "button_reply" else "list"
            inner = payload.get("payload") or {}
            text = inner.get("title")
            interactive_payload = inner.get("id") or inner.get("postbackText")

        msgs.append(
            InboundMessage(
                message_id=str(message_id),
                from_e164=e164,
                from_name=sender.get("name"),
                kind=kind,
                text=text,
                interactive_payload=interactive_payload,
                media=media,
                raw=body,
            )
        )
        return msgs

    async def fetch_media(self, message: InboundMessage) -> tuple[bytes, str]:
        if not message.media:
            raise BspError("Message has no media attachment.")
        url = message.media.media_id  # Gupshup passes the direct URL
        if not url.startswith("http"):
            raise BspError("Gupshup media id is not a URL — cannot fetch.")
        resp = await self._client.get(url)
        if resp.status_code >= 400:
            raise BspError(f"Gupshup media fetch failed: {resp.status_code}")
        return resp.content, message.media.filename or "gupshup-media.bin"

    async def send(self, message: OutboundMessage) -> str:
        # Gupshup uses URL-encoded form-bodies for the v1 send API.
        msg_payload: dict[str, Any]
        if message.document_url:
            msg_payload = {
                "type": "file",
                "url": message.document_url,
                "filename": message.document_filename or "file",
                "caption": message.document_caption or "",
            }
        elif message.buttons:
            msg_payload = {
                "type": "quick_reply",
                "content": {"type": "text", "text": message.text or ""},
                "options": [
                    {"type": "text", "title": b.title, "postbackText": b.payload}
                    for b in message.buttons[:3]
                ],
            }
        elif message.list_items:
            msg_payload = {
                "type": "list",
                "title": message.list_title or "Options",
                "body": message.text or "",
                "globalButtons": [
                    {"type": "text", "title": message.list_button_label or "Choose"}
                ],
                "items": [
                    {
                        "title": message.list_title or "Options",
                        "options": [
                            {
                                "type": "text",
                                "title": it.title,
                                "description": it.description or "",
                                "postbackText": it.payload or it.title,
                            }
                            for it in message.list_items[:10]
                        ],
                    }
                ],
            }
        else:
            msg_payload = {"type": "text", "text": message.text or ""}

        data = {
            "channel": "whatsapp",
            "source": self.source,
            "destination": message.to_e164.lstrip("+"),
            "src.name": self.app_name,
            "message": _json_dumps(msg_payload),
        }
        resp = await self._client.post(f"{self.api_base}/msg", data=data)
        if resp.status_code >= 400:
            raise BspError(f"Gupshup send failed: {resp.status_code} {resp.text[:200]}")
        try:
            return str(resp.json().get("messageId") or "")
        except Exception:  # pragma: no cover
            return ""


def _json_dumps(obj: Any) -> str:
    import json
    return json.dumps(obj, separators=(",", ":"))
