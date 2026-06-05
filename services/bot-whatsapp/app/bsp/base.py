#genai: Sprint 5 / WS-E — BSP-agnostic interfaces.
"""
Every WhatsApp BSP exposes a slightly different webhook + send API. We hide
those differences behind these dataclasses so the rest of the service only
deals with `InboundMessage` and `OutboundMessage`.

Reasoning: the plan calls out that BSP must be swappable (§9.1). Anything
that knows about BSP-specific JSON shapes lives in `bsp/<provider>.py`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class BspError(RuntimeError):
    """Raised on BSP-side failures (auth, transport, malformed payloads)."""


# ── Inbound (BSP → us) ───────────────────────────────────────────────────────


@dataclass
class InboundMedia:
    """A media attachment on an inbound message."""
    media_id: str           # BSP-specific id; passed back to fetch the bytes
    mime_type: str | None   # 'application/pdf', 'image/jpeg', ...
    filename: str | None    # caller-provided file name when known
    size_bytes: int | None  # may be unknown until we download


@dataclass
class InboundMessage:
    """
    Normalized inbound message. Adapters convert provider payloads into this
    shape; conversation logic only deals with this dataclass.
    """
    # Stable id for dedup (each BSP gives us one; we re-use it as the
    # idempotency key in Redis so accidental webhook replays are no-ops).
    message_id: str

    # Sender phone number in E.164 (with the leading `+`). The
    # `ChannelLink.handle` for the WhatsApp channel uses this exact form.
    from_e164: str

    # Best-effort display name from the BSP (we don't trust it; only use as
    # default if the user types it themselves later).
    from_name: str | None = None

    # One of: 'text', 'media', 'button', 'list', 'unknown'
    kind: str = "text"

    # Body text (the user's message, or button title for button replies).
    text: str | None = None

    # For interactive button/list replies, the value our previous outbound
    # message attached to that choice (e.g. 'feature:sister_quote').
    interactive_payload: str | None = None

    media: InboundMedia | None = None

    # Raw provider envelope, kept for debugging / future feature support.
    raw: dict[str, Any] = field(default_factory=dict)


# ── Outbound (us → BSP) ──────────────────────────────────────────────────────


@dataclass
class OutboundButton:
    title: str           # ≤ 20 chars; WA enforces this
    payload: str         # opaque id we get back as `interactive_payload`


@dataclass
class OutboundListItem:
    title: str           # ≤ 24 chars
    description: str | None = None
    payload: str = ""


@dataclass
class OutboundMessage:
    """
    What we want to send. Renderers in `bsp/<provider>.py` translate this to
    the right JSON for that BSP.
    """
    to_e164: str
    text: str | None = None

    # Up to 3 buttons per WA spec.
    buttons: list[OutboundButton] = field(default_factory=list)

    # List section title + items. Use either buttons or list, not both.
    list_title: str | None = None
    list_button_label: str | None = None  # label of the "Open list" button
    list_items: list[OutboundListItem] = field(default_factory=list)

    # Optional file to ship back to the user — we pass a presigned URL the
    # BSP can fetch.
    document_url: str | None = None
    document_filename: str | None = None
    document_caption: str | None = None


# ── Provider contract ────────────────────────────────────────────────────────


class BspProvider:
    """Every concrete BSP implements this minimal surface."""

    name: str = "base"

    async def parse_webhook(self, body: dict[str, Any]) -> list[InboundMessage]:
        """
        Convert a raw webhook payload into 0+ inbound messages. WhatsApp BSPs
        sometimes batch multiple events in a single webhook call.
        """
        raise NotImplementedError

    async def fetch_media(self, message: InboundMessage) -> tuple[bytes, str]:
        """
        Download the media attachment.
        Returns `(file_bytes, filename)`. Filename falls back to '<id>.bin'.
        """
        raise NotImplementedError

    async def send(self, message: OutboundMessage) -> str:
        """Send a message; returns the BSP-side message id."""
        raise NotImplementedError

    def verify_signature(self, headers: dict[str, str], body: bytes) -> bool:
        """
        Optional signature/secret check on inbound webhooks. Default: noop.
        Override in providers that ship a verification token / HMAC header.
        """
        return True
