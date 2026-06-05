#genai: Sprint 5 / WS-E — in-memory BSP for local dev + tests.
"""
Records every outbound send in an in-memory list so tests can assert on them
without spinning up a real BSP. Also accepts a simple webhook shape (the
same one our `MockBsp` produces in `outbox`) so dev can play user-side ping-pong.
"""
from __future__ import annotations

import logging
from typing import Any

from app.bsp.base import (
    BspError,
    BspProvider,
    InboundMedia,
    InboundMessage,
    OutboundMessage,
)

logger = logging.getLogger(__name__)


class MockBsp(BspProvider):
    name = "mock"

    def __init__(self) -> None:
        # Tests inspect this to verify what the conversation produced.
        self.outbox: list[OutboundMessage] = []
        # Map media_id → (bytes, filename) seeded by tests.
        self._media: dict[str, tuple[bytes, str]] = {}
        self._send_counter = 0

    def seed_media(self, media_id: str, content: bytes, filename: str) -> None:
        self._media[media_id] = (content, filename)

    async def parse_webhook(self, body: dict[str, Any]) -> list[InboundMessage]:
        """
        Webhook shape for the mock:
          { "from": "+91…", "kind": "text|media|button|list",
            "text": "...", "payload": "...", "media_id": "...", "mime": "...",
            "filename": "...", "message_id": "..." }
        """
        e164 = str(body.get("from") or "")
        if not e164:
            return []
        kind = str(body.get("kind") or "text")
        media = None
        if kind == "media":
            media = InboundMedia(
                media_id=str(body.get("media_id") or ""),
                mime_type=body.get("mime"),
                filename=body.get("filename"),
                size_bytes=body.get("size"),
            )
        return [
            InboundMessage(
                message_id=str(body.get("message_id") or f"mock-{len(self.outbox)}"),
                from_e164=e164,
                from_name=body.get("name"),
                kind=kind,
                text=body.get("text"),
                interactive_payload=body.get("payload"),
                media=media,
                raw=body,
            )
        ]

    async def fetch_media(self, message: InboundMessage) -> tuple[bytes, str]:
        if not message.media:
            raise BspError("Mock: message has no media.")
        key = message.media.media_id
        if key not in self._media:
            raise BspError(f"Mock: no seeded media for id {key!r}.")
        return self._media[key]

    async def send(self, message: OutboundMessage) -> str:
        self.outbox.append(message)
        self._send_counter += 1
        logger.debug("MockBsp.send → %s (#%d)", message.to_e164, self._send_counter)
        return f"mock-msg-{self._send_counter}"
