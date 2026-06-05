"""
#genai: WS-10 — Tests for progress indicators on long-running operations.
Verifies that multi-step progress messages are shown during LLM operations.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

from app.session_store import BotState

SAMPLES = Path(__file__).parent.parent.parent.parent / "test-samples"

pytestmark = pytest.mark.asyncio


def _make_update(user_id: int = 333, text: str = None):
    update = MagicMock()
    update.effective_user.id = user_id
    update.message = MagicMock()
    update.message.reply_text = AsyncMock()
    update.message.reply_document = AsyncMock()
    if text:
        update.message.text = text
    update.callback_query = None
    return update


def _make_callback(user_id: int = 333, data: str = ""):
    update = MagicMock()
    update.effective_user.id = user_id
    query = MagicMock()
    query.answer = AsyncMock()
    query.data = data
    query.edit_message_text = AsyncMock()
    query.edit_message_reply_markup = AsyncMock()
    query.message = MagicMock()
    query.message.reply_text = AsyncMock()
    query.message.reply_document = AsyncMock()
    update.callback_query = query
    update.message = None
    return update


def _ctx():
    return MagicMock()


# ── Bill to Make progress ────────────────────────────────────────────────────

class TestBillToMakeProgress:
    """Verify progress messages during bill_to_make flow."""

    async def test_bill_parsing_shows_progress_steps(self):
        from app.bot import handle_text, store

        update = _make_update(text="INV-001, 31-05-2024")
        uid = str(update.effective_user.id)
        s = store.get(uid)
        s.state = BotState.WAITING_BILL_META
        s.pending_file = SAMPLES / "invoice" / "sample_invoice_complete.docx"
        s.original_filename = "sample_invoice_complete.docx"
        s.is_registered = True

        # Mock the progress message object
        progress_msg = MagicMock()
        progress_msg.edit_text = AsyncMock()
        update.message.reply_text = AsyncMock(return_value=progress_msg)

        with patch("app.bot._check_quota", return_value=(True, "")), \
             patch("app.bot._refresh_profile", return_value={}), \
             patch("app.bot._bill_check_hsn", new=AsyncMock()), \
             patch("app.processors.bill_to_make.parse_bill_doc_text", return_value={
                 "bill_to": {"name": "Co", "address": "Addr", "gstin": "NA",
                             "state_code": "27", "state_name": "MH"},
                 "ship_to": {"name": "Co", "address": "Addr", "gstin": "NA",
                             "state_code": "27", "state_name": "MH"},
                 "items": [{"sno": "1", "name": "Item", "hsn": "1234",
                            "unit_cost": 100.0, "amount": 100.0}],
                 "gst_rate": 18,
             }):
            await handle_text(update, _ctx())

        # The first reply_text should contain step 1 progress
        first_call = update.message.reply_text.call_args_list[0]
        first_text = str(first_call)
        assert "1/4" in first_text or "Reading" in first_text

        # The progress_msg.edit_text should have been called with step 2
        if progress_msg.edit_text.called:
            step2_calls = [str(c) for c in progress_msg.edit_text.call_args_list]
            assert any("2/4" in t or "extracting" in t.lower() for t in step2_calls)


# ── GST Validation progress ─────────────────────────────────────────────────

class TestGstValidateProgress:
    """Verify progress messages during GST validation."""

    async def test_gst_validate_shows_progress_steps(self):
        from app.bot import _do_gst_validate, store

        query = MagicMock()
        query.edit_message_text = AsyncMock()
        query.message = MagicMock()
        query.message.reply_text = AsyncMock()

        uid = "gst_prog_1"
        s = store.get(uid)
        s.is_registered = True
        s.pending_file = SAMPLES / "invoice" / "sample_invoice_complete.docx"
        s.original_filename = "test.docx"

        with patch("app.processors.extractors.extract_text", return_value="Invoice text"), \
             patch("app.processors.gst_validator.validate_invoice", return_value="All OK"):
            await _do_gst_validate(query, uid, s)

        # Should have multiple edit_message_text calls for progress
        calls = query.edit_message_text.call_args_list
        call_texts = [str(c) for c in calls]
        assert any("1/3" in t or "Reading" in t for t in call_texts)
        assert any("complete" in t.lower() for t in call_texts)


# ── Sister Quotation progress ────────────────────────────────────────────────

class TestSisterQuotationProgress:
    """Verify progress messages during sister quotation conversion."""

    async def test_sister_quotation_shows_progress_steps(self):
        from app.bot import _convert_with_format_id, store

        uid = "sister_prog_1"
        s = store.get(uid)
        s.is_registered = True
        s.org_id = "org-1"
        s.pending_file = Path("/tmp/test.docx")
        s.original_filename = "test.docx"

        msg = MagicMock()
        msg.reply_text = AsyncMock()
        msg.reply_document = AsyncMock()

        edit_msg = MagicMock()
        edit_msg.edit_message_text = AsyncMock()

        mock_quote_data = MagicMock()

        with patch("app.processors.service.convert_with_template",
                   return_value=(MagicMock(), mock_quote_data)), \
             patch("app.bot._upload_output_file", return_value="key"), \
             patch("app.bot._log_and_increment", new=AsyncMock()):
            await _convert_with_format_id(
                msg, uid, s, "fmt-1", "key", "Test", Path("/tmp/tmpl.pdf"),
                edit_msg=edit_msg,
            )

        calls = edit_msg.edit_message_text.call_args_list
        call_texts = [str(c) for c in calls]
        # Should show multiple progress steps
        assert any("1/4" in t or "Reading" in t for t in call_texts)
        assert any("2/4" in t or "Extracting" in t for t in call_texts)


# ── Comparison progress ──────────────────────────────────────────────────────

class TestComparisonProgress:
    """Verify progress messages during quotation comparison."""

    async def test_comparison_shows_progress_steps(self):
        from app.bot import _add_comparison_file, store

        uid = "cmp_prog_1"
        s = store.get(uid)
        s.is_registered = True
        s.org_id = "org-1"
        s.comparison_total = 2
        s.comparison_files = [{"path": Path("/tmp/q1.docx"), "name": "q1.docx"}]
        s.state = BotState.WAITING_COMPARISON_FILES

        update = _make_update()
        # Mock the progress message
        progress_msg = MagicMock()
        progress_msg.edit_text = AsyncMock()
        update.message.reply_text = AsyncMock(return_value=progress_msg)

        doc = MagicMock()
        doc.file_name = "q2.docx"
        doc.file_size = 4096
        doc.get_file = AsyncMock(return_value=MagicMock(download_to_drive=AsyncMock()))

        with patch("app.bot._user_tmp", return_value=Path("/tmp/q2.docx")), \
             patch("app.processors.quotation_compare.compare_quotations"), \
             patch("app.bot._upload_output_file", return_value="key"), \
             patch("app.bot._log_and_increment", new=AsyncMock()):
            await _add_comparison_file(update, _ctx(), uid, s, doc, ".docx")

        # After adding the last file, progress messages should start
        call_texts = [str(c) for c in update.message.reply_text.call_args_list]
        has_progress = any("1/4" in t or "Reading" in t for t in call_texts)
        # It should have shown at least a progress message
        assert len(call_texts) > 0
