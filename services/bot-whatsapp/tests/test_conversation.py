#genai: Sprint 5 — end-to-end conversation tests with the mock BSP.
"""
We patch the API client so no HTTP hits happen, then drive the state machine
with a sequence of InboundMessages and assert on what the conversation sent
to the BSP and what session state it left behind.
"""
from __future__ import annotations

import base64
from typing import Any

import pytest

from app.bsp.base import InboundMedia, InboundMessage
from app.conversation import Conversation
from app.session_store import get_session_store


# ── Helpers ──────────────────────────────────────────────────────────────────


def _text(e164: str, text: str, message_id: str | None = None) -> InboundMessage:
    return InboundMessage(
        message_id=message_id or f"text-{text[:8]}",
        from_e164=e164,
        kind="text",
        text=text,
    )


def _button(e164: str, payload: str, title: str = "") -> InboundMessage:
    return InboundMessage(
        message_id=f"btn-{payload}",
        from_e164=e164,
        kind="button",
        text=title or payload,
        interactive_payload=payload,
    )


def _media(e164: str, media_id: str = "m-1", filename: str = "quote.pdf") -> InboundMessage:
    return InboundMessage(
        message_id=f"media-{media_id}",
        from_e164=e164,
        kind="media",
        media=InboundMedia(media_id=media_id, mime_type="application/pdf",
                           filename=filename, size_bytes=100),
    )


# ── Test cases ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_first_time_user_is_asked_for_business_name(mock_bsp):
    store = get_session_store()
    convo = Conversation(bsp=mock_bsp, store=store)
    await convo.handle(_text("+919900000001", "hi"))
    sent = mock_bsp.outbox
    assert len(sent) == 1
    assert "business name" in (sent[0].text or "").lower()
    session = await store.get("+919900000001")
    assert session["step"] == "awaiting_name"


@pytest.mark.asyncio
async def test_business_name_provisions_user(mock_bsp, monkeypatch):
    captured: dict[str, Any] = {}

    async def fake_register_channel(**kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {
            "user_id": "u-1", "user": {"id": "u-1", "name": kwargs["name"]},
            "organization": {"id": "o-1", "name": kwargs["company_name"]},
        }

    monkeypatch.setattr("app.conversation.register_channel", fake_register_channel)

    store = get_session_store()
    convo = Conversation(bsp=mock_bsp, store=store)
    await convo.handle(_text("+919900000002", "hello"))
    await convo.handle(_text("+919900000002", "Acme Instruments"))

    assert captured["e164"] == "+919900000002"
    assert captured["company_name"] == "Acme Instruments"
    session = await store.get("+919900000002")
    assert session["step"] == "idle"
    assert session["company_name"] == "Acme Instruments"


@pytest.mark.asyncio
async def test_file_drop_offers_action_buttons(mock_bsp, monkeypatch):
    store = get_session_store()
    convo = Conversation(bsp=mock_bsp, store=store)
    # Pre-provision the user so we skip the welcome.
    await store.put("+919900000003", {
        "step": "idle", "user_id": "u-3", "organization_id": "o-3",
        "company_name": "Acme",
    })

    mock_bsp.seed_media("m-1", b"%PDF-1.4", "quote.pdf")
    await convo.handle(_media("+919900000003"))

    last = mock_bsp.outbox[-1]
    assert "quote.pdf" in (last.text or "")
    payloads = {b.payload for b in last.buttons}
    assert "feature:sister_quote" in payloads
    assert "feature:gst_validate" in payloads

    session = await store.get("+919900000003")
    assert session["step"] == "file_received"
    assert session["filename"] == "quote.pdf"
    # File bytes are stored base64-encoded so they survive the JSON roundtrip.
    assert base64.b64decode(session["file_b64"]) == b"%PDF-1.4"


@pytest.mark.asyncio
async def test_non_document_attachment_is_rejected(mock_bsp):
    store = get_session_store()
    convo = Conversation(bsp=mock_bsp, store=store)
    await store.put("+91999", {"step": "idle", "user_id": "u", "company_name": "x"})
    # Send a text msg saying "hi" with no media → ACK_NON_DOC isn't triggered
    # because that only fires for media kind without a `media` attachment.
    # The actual unsupported-attachment path: filename with bad extension.
    mock_bsp.seed_media("m-bad", b"abc", "song.mp3")
    bad = InboundMessage(
        message_id="m-bad-1",
        from_e164="+91999",
        kind="media",
        media=InboundMedia(media_id="m-bad", mime_type="audio/mp3",
                           filename="song.mp3", size_bytes=10),
    )
    await convo.handle(bad)
    assert "only read documents" in (mock_bsp.outbox[-1].text or "").lower()


@pytest.mark.asyncio
async def test_sister_quote_happy_path_through_to_final(mock_bsp, monkeypatch):
    """drop → button → confirm → format → done."""
    store = get_session_store()
    convo = Conversation(bsp=mock_bsp, store=store)
    e164 = "+919900000099"
    await store.put(e164, {
        "step": "idle", "user_id": "u-99", "organization_id": "o-99",
        "company_name": "Acme",
    })

    sent_to_api: list[dict[str, Any]] = []

    async def fake_process(**kwargs: Any) -> dict[str, Any]:
        sent_to_api.append(kwargs)
        if kwargs["mode"] == "preview":
            return {
                "parsed_data": {
                    "recipient_name": "ABC Lab",
                    "sections": [
                        {"name": "GEN", "items": [
                            {"sno": "1", "description": "pH Meter", "qty": "2",
                             "unit_price": 12000.0, "total": 24000.0},
                        ]},
                    ],
                },
                "needs_confirmation": True,
            }
        return {
            "document_id": "d-1",
            "output_filename": "ABC_Lab_quote.docx",
            "output_url": "https://minio.example/outputs/d-1/ABC_Lab_quote.docx",
            "quota": {"used": 3, "limit": 10},
        }

    async def fake_formats(_e164: str) -> list[dict[str, Any]]:
        return [
            {"id": "fmt-1", "name": "Tender Format", "original_filename": "tender.docx"},
        ]

    monkeypatch.setattr("app.conversation.process_feature", fake_process)
    monkeypatch.setattr("app.conversation.list_sister_formats", fake_formats)

    mock_bsp.seed_media("m-pdf", b"PDFCONTENT", "quote.pdf")
    await convo.handle(_media(e164, media_id="m-pdf", filename="quote.pdf"))
    await convo.handle(_button(e164, "feature:sister_quote"))
    await convo.handle(_button(e164, "confirm:yes"))
    await convo.handle(_button(e164, "format:fmt-1"))

    # Expect at least: ACK, "Reading…", confirm, formats list, "Generating…", document
    last = mock_bsp.outbox[-1]
    assert last.document_url == "https://minio.example/outputs/d-1/ABC_Lab_quote.docx"
    assert last.document_filename == "ABC_Lab_quote.docx"
    assert "3/10" in (last.document_caption or "")

    # The final call used the cached preview & format id.
    finals = [c for c in sent_to_api if c["mode"] == "final"]
    assert len(finals) == 1
    assert finals[0]["feature"] == "sister_quote"
    assert finals[0]["format_id"] == "fmt-1"
    assert finals[0]["params"]["quote"]["recipient_name"] == "ABC Lab"

    session = await store.get(e164)
    assert session["step"] == "idle"
    assert session.get("file_b64") is None


@pytest.mark.asyncio
async def test_cancel_clears_state(mock_bsp, monkeypatch):
    store = get_session_store()
    convo = Conversation(bsp=mock_bsp, store=store)
    e164 = "+919900000004"
    await store.put(e164, {
        "step": "confirming", "user_id": "u", "company_name": "x",
        "filename": "q.pdf", "file_b64": base64.b64encode(b"x").decode(),
    })
    await convo.handle(_text(e164, "/cancel"))
    session = await store.get(e164)
    assert session.get("step") == "idle"
    assert session.get("file_b64") is None


@pytest.mark.asyncio
async def test_link_command_routes_to_api(mock_bsp, monkeypatch):
    calls: dict[str, Any] = {}

    async def fake_link(*, e164: str, token: str) -> dict[str, Any]:
        calls["link"] = (e164, token)
        return {"id": "link-1"}

    async def fake_register(**kwargs: Any) -> dict[str, Any]:
        calls["register"] = kwargs
        return {
            "user": {"id": "u-7"},
            "organization": {"id": "o-7", "name": "Linked Co"},
        }

    monkeypatch.setattr("app.conversation.confirm_channel_link", fake_link)
    monkeypatch.setattr("app.conversation.register_channel", fake_register)

    store = get_session_store()
    convo = Conversation(bsp=mock_bsp, store=store)
    e164 = "+919900000005"
    await convo.handle(_text(e164, "/link CODE-XYZ"))

    assert calls["link"] == (e164, "CODE-XYZ")
    assert "Linked" in (mock_bsp.outbox[-1].text or "")


@pytest.mark.asyncio
async def test_link_without_code_shows_help(mock_bsp):
    store = get_session_store()
    convo = Conversation(bsp=mock_bsp, store=store)
    await convo.handle(_text("+91999", "/link"))
    assert "link this whatsapp" in (mock_bsp.outbox[-1].text or "").lower()


@pytest.mark.asyncio
async def test_dedup_skips_replayed_webhook(mock_bsp):
    """A BSP retrying the same message_id should be a no-op."""
    from app.session_store import get_session_store

    store = get_session_store()
    assert (await store.seen("dup-1")) is False
    assert (await store.seen("dup-1")) is True
    assert (await store.seen("dup-2")) is False
