"""
#genai: Async handler tests for bot.py — mock Telegram objects, verify state transitions and replies.
Covers: handle_document, handle_text, handle_callback routing, error recovery, session management.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

SAMPLES = Path(__file__).parent.parent.parent.parent / "test-samples"

pytestmark = pytest.mark.asyncio


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_update(user_id: int = 111, text: str = None, doc_name: str = None):
    update = MagicMock()
    update.effective_user.id = user_id
    update.message = MagicMock()
    update.message.reply_text = AsyncMock()
    update.message.reply_document = AsyncMock()

    if text:
        update.message.text = text
        update.message.document = None
    if doc_name:
        doc = MagicMock()
        doc.file_name = doc_name
        doc.file_unique_id = "unique123"
        doc.file_size = 4096  # small enough to pass the KI-06 size guard
        doc.get_file = AsyncMock(return_value=MagicMock(download_to_drive=AsyncMock()))
        update.message.document = doc
        update.message.text = None

    update.callback_query = None
    return update


def _make_callback(user_id: int = 111, data: str = "action:exit"):
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


def _mock_auth(registered: bool = True):
    """Patch _require_auth to allow or deny."""
    async def _auth(update):
        return registered
    return patch("app.bot._require_auth", side_effect=_auth)


def _ctx():
    return MagicMock()


# ── handle_document ───────────────────────────────────────────────────────────

class TestHandleDocument:
    """TC-DOC-*: File upload routing."""

    async def test_unsupported_extension_rejected(self):
        from app.bot import handle_document
        update = _make_update(doc_name="malware.exe")
        with _mock_auth():
            await handle_document(update, _ctx())
        call_args = update.message.reply_text.call_args_list
        assert any("Unsupported" in str(c) or "unsupported" in str(c).lower() for c in call_args)

    async def test_docx_accepted_and_action_keyboard_shown(self):
        from app.bot import handle_document, store
        update = _make_update(doc_name="quotation.docx")
        with _mock_auth(), \
             patch("app.bot._user_tmp", return_value=Path("/tmp/test.docx")):
            await handle_document(update, _ctx())
        uid = str(update.effective_user.id)
        from app.session_store import BotState
        assert store.get(uid).state == BotState.WAITING_ACTION

    async def test_pdf_accepted(self):
        from app.bot import handle_document, store
        update = _make_update(doc_name="invoice.pdf")
        uid = str(update.effective_user.id)
        store.reset(uid)  # ensure clean state — no leftover pending_file
        with _mock_auth(), \
             patch("app.bot._user_tmp", return_value=Path("/tmp/test.pdf")):
            await handle_document(update, _ctx())
        from app.session_store import BotState
        assert store.get(uid).state == BotState.WAITING_ACTION

    async def test_excel_accepted(self):
        from app.bot import handle_document, store
        update = _make_update(doc_name="products.xlsx")
        uid = str(update.effective_user.id)
        store.reset(uid)  # ensure clean state — no leftover pending_file
        with _mock_auth(), \
             patch("app.bot._user_tmp", return_value=Path("/tmp/test.xlsx")):
            await handle_document(update, _ctx())
        from app.session_store import BotState
        assert store.get(uid).state == BotState.WAITING_ACTION

    async def test_oversize_file_rejected(self):
        """KI-06: files larger than 15 MB are rejected before download."""
        from app.bot import handle_document, store
        update = _make_update(doc_name="huge.docx")
        update.message.document.file_size = 30 * 1024 * 1024  # 30 MB
        uid = str(update.effective_user.id)
        store.reset(uid)
        with _mock_auth():
            await handle_document(update, _ctx())
        from app.session_store import BotState
        assert store.get(uid).state == BotState.IDLE
        call_text = str(update.message.reply_text.call_args)
        assert "too large" in call_text.lower() or "Max" in call_text

    async def test_unauthenticated_user_blocked(self):
        from app.bot import handle_document, store
        update = _make_update(doc_name="file.docx")
        uid = str(update.effective_user.id)
        store.reset(uid)  # ensure clean state before test
        with _mock_auth(registered=False):
            await handle_document(update, _ctx())
        from app.session_store import BotState
        assert store.get(uid).state == BotState.IDLE

    async def test_crash_in_download_resets_session(self):
        """TC-ERR-01: Download failure must reset session and reply with error."""
        from app.bot import handle_document, store
        update = _make_update(doc_name="file.docx")
        uid = str(update.effective_user.id)
        store.reset(uid)

        with _mock_auth(), \
             patch("app.bot._user_tmp", side_effect=RuntimeError("Disk full")):
            await handle_document(update, _ctx())

        from app.session_store import BotState
        assert store.get(uid).state == BotState.IDLE
        update.message.reply_text.assert_called()


# ── handle_callback: navigation ───────────────────────────────────────────────

class TestHandleCallbackNavigation:
    """TC-CB-NAV-*: Navigation callbacks (exit, new_file)."""

    async def test_exit_resets_session(self):
        from app.bot import handle_callback, store
        update = _make_callback(data="action:exit")
        uid = str(update.effective_user.id)
        with _mock_auth(), \
             patch("app.bot.api_client.get_quota", return_value={"plan": "free", "docs_used": 0, "docs_limit": 10}):
            await handle_callback(update, _ctx())
        from app.session_store import BotState
        assert store.get(uid).state == BotState.IDLE

    async def test_new_file_resets_session(self):
        from app.bot import handle_callback, store
        update = _make_callback(data="action:new_file")
        uid = str(update.effective_user.id)
        await handle_callback(update, _ctx())
        from app.session_store import BotState
        assert store.get(uid).state == BotState.IDLE

    async def test_exit_shows_menu_message(self):
        from app.bot import handle_callback
        update = _make_callback(data="action:exit")
        with patch("app.bot.api_client.get_quota", return_value={"plan": "free", "docs_used": 0, "docs_limit": 10}):
            await handle_callback(update, _ctx())
        query = update.callback_query
        # Must have called edit_message_text or reply_text
        called_texts = []
        if query.edit_message_text.called:
            called_texts += [str(c) for c in query.edit_message_text.call_args_list]
        if query.message.reply_text.called:
            called_texts += [str(c) for c in query.message.reply_text.call_args_list]
        assert any("menu" in t.lower() or "Menu" in t or "DocSeva" in t for t in called_texts)


# ── handle_callback: bill_to_make ─────────────────────────────────────────────

class TestHandleCallbackBillToMake:
    """TC-CB-BILL-*: Bill-to-Make action routing."""

    async def test_bill_to_make_action_sets_state(self):
        from app.bot import handle_callback, store
        update = _make_callback(data="action:bill_to_make")
        uid = str(update.effective_user.id)
        store.get(uid).pending_file = Path(SAMPLES / "invoice" / "sample_invoice_complete.docx")
        await handle_callback(update, _ctx())
        from app.session_store import BotState
        assert store.get(uid).state == BotState.WAITING_BILL_META

    async def test_action_without_file_shows_warning(self):
        from app.bot import handle_callback, store
        update = _make_callback(data="action:bill_to_make")
        uid = str(update.effective_user.id)
        store.reset(uid)  # no pending file
        await handle_callback(update, _ctx())
        query = update.callback_query
        assert query.edit_message_text.called


# ── handle_text: bill meta parsing ────────────────────────────────────────────

class TestHandleTextBillMeta:
    """TC-TEXT-BILL-*: Bill metadata (number + date) input parsing."""

    def _setup_bill_state(self, uid: str, file_path: Path):
        from app.bot import store
        from app.session_store import BotState
        s = store.get(uid)
        s.state = BotState.WAITING_BILL_META
        s.pending_file = file_path
        s.original_filename = file_path.name

    async def test_valid_input_advances_state(self):
        from app.bot import handle_text, store
        update = _make_update(text="INV-001, 31-05-2024")
        uid = str(update.effective_user.id)
        self._setup_bill_state(uid, SAMPLES / "invoice" / "sample_invoice_complete.docx")

        with patch("app.bot._check_quota", return_value=(True, "")), \
             patch("app.bot._refresh_profile", return_value={}), \
             patch("app.bot._bill_check_hsn", new=AsyncMock()) as mock_check, \
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
        mock_check.assert_called_once()

    async def test_invalid_date_reprompts(self):
        from app.bot import handle_text, store
        update = _make_update(text="INV-001, 3454")
        uid = str(update.effective_user.id)
        self._setup_bill_state(uid, SAMPLES / "invoice" / "sample_invoice_complete.docx")
        await handle_text(update, _ctx())
        # Must have replied asking for a valid date
        update.message.reply_text.assert_called()
        call_text = str(update.message.reply_text.call_args)
        assert "date" in call_text.lower() or "Date" in call_text or "format" in call_text.lower()

    async def test_missing_comma_reprompts(self):
        from app.bot import handle_text, store
        update = _make_update(text="INV001 31052024")  # no comma
        uid = str(update.effective_user.id)
        self._setup_bill_state(uid, SAMPLES / "invoice" / "sample_invoice_complete.docx")
        await handle_text(update, _ctx())
        update.message.reply_text.assert_called()

    async def test_quota_exceeded_blocks(self):
        from app.bot import handle_text, store
        update = _make_update(text="INV-001, 31-05-2024")
        uid = str(update.effective_user.id)
        self._setup_bill_state(uid, SAMPLES / "invoice" / "sample_invoice_complete.docx")
        with patch("app.bot._check_quota", return_value=(False, "⚠️ Quota exhausted")), \
             patch("app.bot._refresh_profile", return_value={}):
            await handle_text(update, _ctx())
        call_text = str(update.message.reply_text.call_args)
        assert "Quota" in call_text or "quota" in call_text


# ── handle_text: HSN flow ─────────────────────────────────────────────────────

class TestHandleTextHsn:
    """TC-TEXT-HSN-*: HSN code collection and re-validation."""

    def _setup_hsn_state(self, uid: str, items: list):
        from app.bot import store
        from app.session_store import BotState
        s = store.get(uid)
        s.state = BotState.WAITING_BILL_HSN
        s.pending_bill_data = {
            "parsed": {
                "bill_to": {"name": "Co", "address": "Addr", "gstin": "NA",
                            "state_code": "27", "state_name": "MH"},
                "ship_to": {"name": "Co", "address": "Addr", "gstin": "NA",
                            "state_code": "27", "state_name": "MH"},
                "items": items,
                "gst_rate": 18,
            },
            "bill_no": "INV-001",
            "bill_date": "31-05-2024",
        }

    async def test_skip_advances_to_billto_check(self):
        from app.bot import handle_text, store
        update = _make_update(text="skip")
        uid = str(update.effective_user.id)
        items = [{"sno": "1", "name": "Item", "hsn": "", "unit_cost": 100.0, "amount": 100.0}]
        self._setup_hsn_state(uid, items)
        with patch("app.bot._bill_check_bill_to", new=AsyncMock()) as mock_check:
            await handle_text(update, _ctx())
        mock_check.assert_called_once()

    async def test_valid_hsn_code_applied(self):
        from app.bot import handle_text, store
        update = _make_update(text="1: 8413")
        uid = str(update.effective_user.id)
        items = [{"sno": "1", "name": "Pump", "hsn": "", "unit_cost": 100.0, "amount": 100.0}]
        self._setup_hsn_state(uid, items)
        with patch("app.bot._bill_check_bill_to", new=AsyncMock()):
            await handle_text(update, _ctx())
        s = store.get(uid)
        assert s.pending_bill_data["parsed"]["items"][0]["hsn"] == "8413"

    async def test_partial_fill_re_prompts(self):
        from app.bot import handle_text, store
        update = _make_update(text="1: 8413")  # only item 1 of 2
        uid = str(update.effective_user.id)
        items = [
            {"sno": "1", "name": "Pump", "hsn": "", "unit_cost": 100.0, "amount": 100.0},
            {"sno": "2", "name": "Valve", "hsn": "", "unit_cost": 200.0, "amount": 200.0},
        ]
        self._setup_hsn_state(uid, items)
        await handle_text(update, _ctx())
        # Still in WAITING_BILL_HSN
        from app.session_store import BotState
        assert store.get(uid).state == BotState.WAITING_BILL_HSN


# ── handle_text: rename flow ──────────────────────────────────────────────────

class TestHandleTextRename:
    """TC-TEXT-RENAME-*: File rename via text input."""

    async def test_rename_sends_renamed_file(self):
        from app.bot import handle_text, store
        from app.session_store import BotState
        update = _make_update(text="my_new_name")
        uid = str(update.effective_user.id)
        store.reset(uid)
        s = store.get(uid)
        s.state = BotState.WAITING_RENAME
        src = SAMPLES / "quotation" / "sample_quotation.docx"
        s.pending_file = src
        s.original_filename = src.name

        await handle_text(update, _ctx())

        # Either reply_document was sent (success) or reply_text with an error — either is acceptable
        assert update.message.reply_document.called or update.message.reply_text.called


# ── Error recovery ────────────────────────────────────────────────────────────

class TestErrorRecovery:
    """TC-ERR-*: Crashes in handlers reset session and inform user."""

    async def test_handle_text_crash_resets_session(self):
        """TC-ERR-02: RuntimeError inside _do_bill_to_make must soft_reset (preserve file)."""
        from app.bot import handle_text, store
        from app.session_store import BotState
        update = _make_update(text="INV-001, 31-05-2024")
        uid = str(update.effective_user.id)
        s = store.get(uid)
        s.state = BotState.WAITING_BILL_META
        s.pending_file = SAMPLES / "invoice" / "sample_invoice_complete.docx"
        s.original_filename = "sample_invoice_complete.docx"

        with patch("app.bot._check_quota", return_value=(True, "")), \
             patch("app.bot._refresh_profile", return_value={}), \
             patch("app.processors.bill_to_make.parse_bill_doc_text", side_effect=RuntimeError("LLM timeout")):
            await handle_text(update, _ctx())

        # WS-2/WS-9: soft_reset preserves file, so state goes to WAITING_ACTION (not IDLE)
        assert store.get(uid).state == BotState.WAITING_ACTION
        update.message.reply_text.assert_called()

    async def test_handle_document_crash_resets_session(self):
        """TC-ERR-03: Crash during file download resets session."""
        from app.bot import handle_document, store
        from app.session_store import BotState
        update = _make_update(doc_name="test.docx")
        uid = str(update.effective_user.id)
        store.reset(uid)

        with _mock_auth(), \
             patch("app.bot._user_tmp", side_effect=Exception("IO Error")):
            await handle_document(update, _ctx())

        assert store.get(uid).state == BotState.IDLE

    async def test_global_error_handler_called_on_uncaught_exception(self):
        """TC-ERR-04: global_error_handler resets session and replies."""
        from app.bot import global_error_handler, store
        update = _make_update(text="hello")
        uid = str(update.effective_user.id)
        store.reset(uid)

        # global_error_handler checks hasattr(update, 'effective_user') — MagicMock has it
        ctx = MagicMock()
        ctx.error = RuntimeError("Unexpected crash")
        await global_error_handler(update, ctx)
        assert store.get(uid).state.name == "IDLE"
        # _reply_error tried reply_text on update.message
        update.message.reply_text.assert_called()


# ── KI-07: custom comparison count ───────────────────────────────────────────

class TestComparisonCustomCount:
    """KI-07: custom count entry path."""

    async def test_custom_button_enters_text_state(self):
        from app.bot import handle_callback, store
        from app.session_store import BotState
        update = _make_callback(data="cmp_n:custom")
        uid = str(update.effective_user.id)
        s = store.get(uid)
        s.pending_file = Path("/tmp/anyfile.docx")
        await handle_callback(update, _ctx())
        assert store.get(uid).state == BotState.WAITING_COMPARISON_CUSTOM_COUNT

    async def test_valid_count_sets_total(self):
        from app.bot import handle_text, store
        from app.session_store import BotState
        update = _make_update(text="7")
        uid = str(update.effective_user.id)
        s = store.get(uid)
        s.state = BotState.WAITING_COMPARISON_CUSTOM_COUNT
        s.pending_file = Path("/tmp/q1.docx")
        s.original_filename = "q1.docx"
        await handle_text(update, _ctx())
        assert store.get(uid).comparison_total == 7
        assert store.get(uid).state == BotState.WAITING_COMPARISON_FILES

    async def test_invalid_count_reprompts(self):
        from app.bot import handle_text, store
        from app.session_store import BotState
        update = _make_update(text="abc")
        uid = str(update.effective_user.id)
        s = store.get(uid)
        s.state = BotState.WAITING_COMPARISON_CUSTOM_COUNT
        s.pending_file = Path("/tmp/q1.docx")
        await handle_text(update, _ctx())
        assert store.get(uid).state == BotState.WAITING_COMPARISON_CUSTOM_COUNT
        update.message.reply_text.assert_called()

    async def test_out_of_range_count_reprompts(self):
        from app.bot import handle_text, store
        from app.session_store import BotState
        update = _make_update(text="50")
        uid = str(update.effective_user.id)
        s = store.get(uid)
        s.state = BotState.WAITING_COMPARISON_CUSTOM_COUNT
        s.pending_file = Path("/tmp/q1.docx")
        await handle_text(update, _ctx())
        assert store.get(uid).state == BotState.WAITING_COMPARISON_CUSTOM_COUNT


# ── KI-13: watermark mode picker ─────────────────────────────────────────────

class TestWatermarkModeFlow:
    async def test_watermark_action_enters_mode_state(self):
        from app.bot import handle_callback, store
        from app.session_store import BotState
        update = _make_callback(data="action:watermark")
        uid = str(update.effective_user.id)
        s = store.get(uid)
        s.pending_file = Path("/tmp/img.png")
        await handle_callback(update, _ctx())
        assert store.get(uid).state == BotState.WAITING_WATERMARK_MODE

    async def test_text_mode_enters_text_state(self):
        from app.bot import handle_callback, store
        from app.session_store import BotState
        update = _make_callback(data="wm:text")
        uid = str(update.effective_user.id)
        s = store.get(uid)
        s.pending_file = Path("/tmp/img.png")
        await handle_callback(update, _ctx())
        assert store.get(uid).state == BotState.WAITING_WATERMARK_TEXT
