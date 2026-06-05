#genai: Sprint 5 — WATI BSP webhook normalization tests.
"""
We don't hit WATI; we feed canned webhook payloads (taken from their docs) to
`WatiBsp.parse_webhook` and assert on the normalized `InboundMessage`.
"""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_wati_text_message_parses_to_text_kind():
    from app.bsp.wati import WatiBsp

    bsp = WatiBsp(api_base="https://wati.example/api/v1", token="")
    payload = {
        "id": "wati-msg-123",
        "eventType": "message",
        "type": "text",
        "waId": "918012345678",
        "text": "Hi there",
        "senderName": "Akarshit",
    }
    msgs = await bsp.parse_webhook(payload)
    assert len(msgs) == 1
    msg = msgs[0]
    assert msg.kind == "text"
    assert msg.text == "Hi there"
    assert msg.from_e164 == "+918012345678"
    assert msg.from_name == "Akarshit"
    assert msg.message_id == "wati-msg-123"


@pytest.mark.asyncio
async def test_wati_document_message_includes_media():
    from app.bsp.wati import WatiBsp

    bsp = WatiBsp(api_base="https://wati.example/api/v1", token="")
    payload = {
        "id": "wati-msg-doc-1",
        "type": "document",
        "waId": "918012345678",
        "mimeType": "application/pdf",
        "fileName": "supplier-quote.pdf",
        "size": 12345,
    }
    msgs = await bsp.parse_webhook(payload)
    assert len(msgs) == 1
    msg = msgs[0]
    assert msg.kind == "media"
    assert msg.media is not None
    assert msg.media.mime_type == "application/pdf"
    assert msg.media.filename == "supplier-quote.pdf"
    assert msg.media.size_bytes == 12345


@pytest.mark.asyncio
async def test_wati_button_reply_carries_payload():
    from app.bsp.wati import WatiBsp

    bsp = WatiBsp(api_base="https://wati.example/api/v1", token="")
    payload = {
        "id": "wati-int-1",
        "type": "interactive",
        "waId": "918012345678",
        "buttonReply": {"text": "Sister Quote", "payload": "feature:sister_quote"},
    }
    msgs = await bsp.parse_webhook(payload)
    assert len(msgs) == 1
    msg = msgs[0]
    assert msg.kind == "button"
    assert msg.interactive_payload == "feature:sister_quote"
    assert msg.text == "Sister Quote"


@pytest.mark.asyncio
async def test_wati_unknown_event_is_dropped_cleanly():
    from app.bsp.wati import WatiBsp

    bsp = WatiBsp(api_base="https://wati.example/api/v1", token="")
    # Missing both `waId` and `from` → unparseable, return empty.
    msgs = await bsp.parse_webhook({"eventType": "status", "id": "x"})
    assert msgs == []


def test_wati_signature_passthrough_when_no_token_configured(monkeypatch):
    """In dev (no verify token), verify_signature should be a no-op."""
    from app.bsp.wati import WatiBsp
    from app.config import get_settings

    s = get_settings()
    monkeypatch.setattr(s, "wati_verify_token", "")

    bsp = WatiBsp(api_base="https://wati.example/api/v1", token="")
    assert bsp.verify_signature({}, b"{}")


def test_wati_signature_check_rejects_when_token_missing(monkeypatch):
    """When a verify token is set, the Authorization header must match."""
    from app.bsp.wati import WatiBsp
    from app.config import get_settings

    s = get_settings()
    monkeypatch.setattr(s, "wati_verify_token", "secret-abc")

    bsp = WatiBsp(api_base="https://wati.example/api/v1", token="")
    assert bsp.verify_signature({"authorization": "Bearer secret-abc"}, b"{}")
    assert not bsp.verify_signature({"authorization": "Bearer wrong"}, b"{}")
    assert not bsp.verify_signature({}, b"{}")
