#genai: Regression tests for the four UX/UI issues reported after Phase 2:
#  1. /history broke again because filename underscores collided with the
#     Markdown parse_mode the bot was sending.
#  2. /create was reachable only via /help; the main menu now surfaces it.
#  3. Sending a photo while in "Upload Logo" mode used to push the user
#     into the generic image-actions flow; it now saves the logo and exits.
#  4. Renderers no longer fall back to a bundled default logo in production.
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── 1. /history must not use Markdown parse mode anymore ─────────────────────

@pytest.mark.asyncio
async def test_history_sends_plain_text_not_markdown():
    """Filenames with underscores must not break /history (no parse_mode)."""
    from app.bot import cmd_history

    update = MagicMock()
    update.effective_user.id = 7
    update.message = MagicMock()
    update.message.reply_text = AsyncMock()

    with patch("app.bot._require_auth", return_value=True), \
         patch("app.bot.api_client.get_documents", return_value=[
             {
                 "status": "completed",
                 "output_filename": "Bill_to_make_004-2_1__bill.pdf",
                 "original_filename": "input_file.docx",
                 "feature": "bill_to_make",
                 "created_at": "2026-06-01T10:00:00",
                 "output_file_key": "outputs/x/y/Bill_to_make_004-2_1__bill.pdf",
             }
         ]), \
         patch("app.storage_client.generate_presigned_url",
               return_value="https://minio/x?a=b&c=d_e_f_g_h"):
        await cmd_history(update, MagicMock())

    kwargs = update.message.reply_text.call_args.kwargs
    # The bug: passing parse_mode="Markdown" with an underscore-laden body
    # makes Telegram return BadRequest. We must not pass parse_mode at all.
    assert "parse_mode" not in kwargs


# ── 2. /create reachable from the main menu ──────────────────────────────────

def test_main_menu_keyboard_has_create_button():
    from app.keyboards import main_menu_keyboard

    kb = main_menu_keyboard()
    callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row]
    assert "menu:create" in callbacks


def test_cmd_menu_text_mentions_create():
    """The /menu copy must include /create so users without a file see it."""
    import inspect
    from app.bot import cmd_menu

    src = inspect.getsource(cmd_menu)
    assert "/create" in src


# ── 3. Logo upload flow saves and returns to settings ────────────────────────

@pytest.mark.asyncio
async def test_photo_during_logo_upload_saves_logo(tmp_path):
    from app.bot import handle_photo
    from app.session_store import BotState, SessionStore

    store = SessionStore()
    store.reset("42")
    session = store.get("42")
    session.is_registered = True
    session.state = BotState.UPDATING_PROFILE_FIELD
    session.updating_field = "logo"

    photo = MagicMock()
    photo.file_size = 1024
    photo.file_unique_id = "abc"
    tg_file = MagicMock()
    tg_file.download_to_drive = AsyncMock()
    photo.get_file = AsyncMock(return_value=tg_file)

    update = MagicMock()
    update.effective_user.id = 42
    update.message = MagicMock()
    update.message.photo = [photo]
    update.message.reply_text = AsyncMock()

    with patch("app.bot._require_auth", return_value=True), \
         patch("app.bot.store", store), \
         patch("app.bot.api_client.upload_company_logo",
               return_value={"logo_key": "logos/42/logo.png"}) as upload_mock:
        await handle_photo(update, MagicMock())

    upload_mock.assert_called_once()
    # After saving, the bot should not be in profile-update state anymore.
    s = store.get("42")
    assert s.state == BotState.IDLE
    assert s.updating_field is None
    # User should not have been offered the generic image-action keyboard.
    all_replies = "".join(str(c) for c in update.message.reply_text.call_args_list)
    assert "Logo saved" in all_replies
    assert "Add Watermark" not in all_replies
    assert "Remove Background" not in all_replies


# ── 4. No default-logo fallback in production renderers ──────────────────────

def test_renderers_skip_logo_when_user_has_none(tmp_path):
    """_add_logo_header should write only the company name if logo is None."""
    from docx import Document
    from app.processors.renderers import _add_logo_header

    doc = Document()
    _add_logo_header(doc, logo_path=None, company_name="Acme Co")
    out = tmp_path / "t.docx"
    doc.save(str(out))

    # Open and inspect the saved docx — header should contain only the name,
    # no <w:drawing> (image) element.
    import zipfile
    with zipfile.ZipFile(str(out)) as zf:
        header_xml = ""
        for name in zf.namelist():
            if "header" in name and name.endswith(".xml"):
                header_xml += zf.read(name).decode("utf-8")
        assert "ACME CO" in header_xml.upper()
        assert "w:drawing" not in header_xml  # no image embedded
        assert "logo.png" not in header_xml


def test_catalog_pdf_skips_logo_block_when_no_user_logo(tmp_path):
    """generate_catalog must not draw a logo when logo_path is None."""
    from app.processors import catalog_pdf

    # Sanity: the module-level fallback path must not be used.
    assert not hasattr(catalog_pdf, "LOGO_PATH")

    out = tmp_path / "c.pdf"
    # generate_catalog with logo_path=None should still succeed and produce a PDF.
    catalog_pdf.generate_catalog(
        image_path=None,
        output_path=out,
        item_name="Test Product",
        description="A test",
        price=None,
        company_profile={"display_name": "Acme"},
        logo_path=None,
    )
    assert out.exists() and out.stat().st_size > 500


def test_watermark_falls_back_to_text_when_no_logo(tmp_path):
    """add_watermark(mode='logo', logo_path=None) must not crash; falls back to text."""
    from PIL import Image
    from app.processors.watermark import add_watermark

    src = tmp_path / "src.png"
    Image.new("RGB", (200, 200), (255, 255, 255)).save(src, "PNG")

    out = add_watermark(src, tmp_path / "wm.png", mode="logo", logo_path=None)
    assert out.exists()


def test_compare_quotations_accepts_company_profile_and_logo():
    """compare_quotations signature must accept logo_path and company_profile."""
    import inspect
    from app.processors.quotation_compare import compare_quotations

    sig = inspect.signature(compare_quotations)
    assert "logo_path" in sig.parameters
    assert "company_profile" in sig.parameters
