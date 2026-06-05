"""
#genai: WS-2 — Tests for state-aware input handling and graceful flow recovery.
Covers: state hints on wrong input, file-during-text-state rejection,
        file replacement confirmation, soft_reset, back-to-actions button.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.session_store import BotState, SessionStore, UserSession

pytestmark = pytest.mark.asyncio


def _make_update(user_id: int = 222, text: str = None, doc_name: str = None):
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
        doc.file_unique_id = "unique_state"
        doc.file_size = 4096
        doc.get_file = AsyncMock(return_value=MagicMock(download_to_drive=AsyncMock()))
        update.message.document = doc
        update.message.text = None

    update.callback_query = None
    return update


def _make_callback(user_id: int = 222, data: str = "action:exit"):
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


def _mock_auth(registered: bool = True):
    async def _auth(update):
        return registered
    return patch("app.bot._require_auth", side_effect=_auth)


# ── State-aware text hints ───────────────────────────────────────────────────

class TestStateAwareTextHints:
    """When user sends text in a button-expected state, show a helpful hint."""

    async def test_text_in_waiting_action_shows_hint(self):
        from app.bot import handle_text, store
        update = _make_update(text="random question")
        uid = str(update.effective_user.id)
        s = store.get(uid)
        s.state = BotState.WAITING_ACTION
        s.is_registered = True
        s.pending_file = Path("/tmp/test.docx")

        await handle_text(update, _ctx())
        call_text = str(update.message.reply_text.call_args)
        assert "waiting" in call_text.lower() or "button" in call_text.lower()

    async def test_text_in_waiting_format_shows_hint(self):
        from app.bot import handle_text, store
        update = _make_update(text="some text")
        uid = str(update.effective_user.id)
        s = store.get(uid)
        s.state = BotState.WAITING_FORMAT
        s.is_registered = True

        await handle_text(update, _ctx())
        call_text = str(update.message.reply_text.call_args)
        assert "format" in call_text.lower() or "button" in call_text.lower()

    async def test_text_in_waiting_comparison_files_shows_file_count(self):
        from app.bot import handle_text, store
        update = _make_update(text="what files?")
        uid = str(update.effective_user.id)
        s = store.get(uid)
        s.state = BotState.WAITING_COMPARISON_FILES
        s.is_registered = True
        s.comparison_total = 3
        s.comparison_files = [{"path": "/tmp/q1.docx", "name": "q1.docx"}]

        await handle_text(update, _ctx())
        call_text = str(update.message.reply_text.call_args)
        assert "2 of 3" in call_text or "quotation" in call_text.lower()

    async def test_text_in_waiting_watermark_mode_shows_hint(self):
        from app.bot import handle_text, store
        update = _make_update(text="hello")
        uid = str(update.effective_user.id)
        s = store.get(uid)
        s.state = BotState.WAITING_WATERMARK_MODE
        s.is_registered = True

        await handle_text(update, _ctx())
        call_text = str(update.message.reply_text.call_args)
        assert "watermark" in call_text.lower() or "button" in call_text.lower()

    async def test_text_in_idle_shows_send_file_prompt(self):
        from app.bot import handle_text, store
        update = _make_update(text="hello there")
        uid = str(update.effective_user.id)
        s = store.get(uid)
        s.state = BotState.IDLE
        s.is_registered = True

        await handle_text(update, _ctx())
        call_text = str(update.message.reply_text.call_args)
        assert "file" in call_text.lower() or "menu" in call_text.lower()


# ── File during text-expected state ──────────────────────────────────────────

class TestFileDuringTextExpected:
    """Sending a file when text is expected should be rejected with a hint."""

    async def test_file_during_waiting_rename_rejected(self):
        from app.bot import handle_document, store
        update = _make_update(doc_name="another.docx")
        uid = str(update.effective_user.id)
        s = store.get(uid)
        s.state = BotState.WAITING_RENAME
        s.is_registered = True

        with _mock_auth():
            await handle_document(update, _ctx())

        call_text = str(update.message.reply_text.call_args)
        assert "text" in call_text.lower() or "expecting" in call_text.lower()
        assert store.get(uid).state == BotState.WAITING_RENAME

    async def test_file_during_waiting_bill_meta_rejected(self):
        from app.bot import handle_document, store
        update = _make_update(doc_name="file.pdf")
        uid = str(update.effective_user.id)
        s = store.get(uid)
        s.state = BotState.WAITING_BILL_META
        s.is_registered = True

        with _mock_auth():
            await handle_document(update, _ctx())

        call_text = str(update.message.reply_text.call_args)
        assert "text" in call_text.lower()

    async def test_file_during_waiting_hsn_rejected(self):
        from app.bot import handle_document, store
        update = _make_update(doc_name="data.xlsx")
        uid = str(update.effective_user.id)
        s = store.get(uid)
        s.state = BotState.WAITING_BILL_HSN
        s.is_registered = True

        with _mock_auth():
            await handle_document(update, _ctx())

        assert store.get(uid).state == BotState.WAITING_BILL_HSN


# ── File replacement confirmation ────────────────────────────────────────────

class TestFileReplacement:
    """When user sends a new file while one is already loaded, ask to confirm."""

    async def test_new_file_during_waiting_action_asks_confirmation(self):
        from app.bot import handle_document, store
        update = _make_update(doc_name="new_file.pdf")
        uid = str(update.effective_user.id)
        s = store.get(uid)
        s.state = BotState.WAITING_ACTION
        s.pending_file = Path("/tmp/old_file.docx")
        s.original_filename = "old_file.docx"
        s.is_registered = True

        with _mock_auth(), \
             patch("app.bot._user_tmp", return_value=Path("/tmp/new_file.pdf")):
            await handle_document(update, _ctx())

        assert store.get(uid).state == BotState.CONFIRMING_FILE_REPLACE
        call_text = str(update.message.reply_text.call_args)
        assert "replace" in call_text.lower() or "old_file" in call_text

    async def test_replace_yes_loads_new_file(self):
        from app.bot import handle_callback, store
        update = _make_callback(data="replace:yes")
        uid = str(update.effective_user.id)
        s = store.get(uid)
        s.state = BotState.CONFIRMING_FILE_REPLACE
        s._replacement_file = Path("/tmp/new.pdf")
        s._replacement_filename = "new.pdf"
        s.pending_file = Path("/tmp/old.docx")
        s.original_filename = "old.docx"
        s.is_registered = True

        await handle_callback(update, _ctx())

        assert store.get(uid).state == BotState.WAITING_ACTION
        assert store.get(uid).original_filename == "new.pdf"

    async def test_replace_no_keeps_current(self):
        from app.bot import handle_callback, store
        update = _make_callback(data="replace:no")
        uid = str(update.effective_user.id)
        s = store.get(uid)
        s.state = BotState.CONFIRMING_FILE_REPLACE
        s._replacement_file = Path("/tmp/new.pdf")
        s._replacement_filename = "new.pdf"
        s.pending_file = Path("/tmp/old.docx")
        s.original_filename = "old.docx"
        s.is_registered = True

        await handle_callback(update, _ctx())

        assert store.get(uid).state == BotState.WAITING_ACTION
        assert store.get(uid).original_filename == "old.docx"


# ── soft_reset ───────────────────────────────────────────────────────────────

class TestSoftReset:
    """soft_reset should keep file and registration but clear flow state."""

    def test_soft_reset_preserves_file(self):
        ss = SessionStore()
        uid = "test_sr_1"
        s = ss.get(uid)
        s.is_registered = True
        s.user_id = "user-1"
        s.org_id = "org-1"
        s.pending_file = Path("/tmp/test.docx")
        s.original_filename = "test.docx"
        s.state = BotState.WAITING_BILL_HSN
        s.pending_bill_data = {"parsed": {}, "bill_no": "INV-1", "bill_date": "01-01-2024"}

        result = ss.soft_reset(uid)
        assert result.state == BotState.WAITING_ACTION
        assert result.pending_file == Path("/tmp/test.docx")
        assert result.original_filename == "test.docx"
        assert result.is_registered is True
        assert result.pending_bill_data is None

    def test_soft_reset_goes_idle_without_file(self):
        ss = SessionStore()
        uid = "test_sr_2"
        s = ss.get(uid)
        s.is_registered = True
        s.state = BotState.WAITING_BILL_HSN

        result = ss.soft_reset(uid)
        assert result.state == BotState.IDLE

    def test_soft_reset_clears_comparison_state(self):
        ss = SessionStore()
        uid = "test_sr_3"
        s = ss.get(uid)
        s.state = BotState.WAITING_COMPARISON_FILES
        s.comparison_total = 3
        s.comparison_files = [{"path": "/tmp/q1.docx", "name": "q1.docx"}]

        result = ss.soft_reset(uid)
        assert result.comparison_total == 0
        assert result.comparison_files == []


# ── Back to actions ──────────────────────────────────────────────────────────

class TestBackToActions:
    """Test the action:back_to_actions callback."""

    async def test_back_to_actions_with_file(self):
        from app.bot import handle_callback, store
        update = _make_callback(data="action:back_to_actions")
        uid = str(update.effective_user.id)
        s = store.get(uid)

        tmp = Path("/tmp/docseva_test_back")
        tmp.mkdir(parents=True, exist_ok=True)
        test_file = tmp / "test.docx"
        test_file.write_text("dummy")

        s.state = BotState.WAITING_BILL_HSN
        s.pending_file = test_file
        s.original_filename = "test.docx"
        s.is_registered = True

        await handle_callback(update, _ctx())

        assert store.get(uid).state == BotState.WAITING_ACTION
        query = update.callback_query
        # Should have shown the action keyboard
        assert query.edit_message_text.called or query.message.reply_text.called

        test_file.unlink(missing_ok=True)

    async def test_back_to_actions_without_file_resets(self):
        from app.bot import handle_callback, store
        update = _make_callback(data="action:back_to_actions")
        uid = str(update.effective_user.id)
        s = store.get(uid)
        s.state = BotState.WAITING_BILL_HSN
        s.pending_file = Path("/tmp/nonexistent_file_xyz.docx")
        s.is_registered = True

        await handle_callback(update, _ctx())

        assert store.get(uid).state == BotState.IDLE


# ── bill:skip_hsn callback ───────────────────────────────────────────────────

class TestBillSkipHsnButton:
    """Test the bill:skip_hsn callback button."""

    async def test_skip_hsn_button_advances(self):
        from app.bot import handle_callback, store
        update = _make_callback(data="bill:skip_hsn")
        uid = str(update.effective_user.id)
        s = store.get(uid)
        s.state = BotState.WAITING_BILL_HSN
        s.is_registered = True
        s.pending_file = Path("/tmp/test.docx")
        s.original_filename = "test.docx"
        s.pending_bill_data = {
            "parsed": {
                "bill_to": {"name": "Co", "address": "Addr", "gstin": "NA",
                            "state_code": "27", "state_name": "MH"},
                "ship_to": {"name": "Co", "address": "Addr", "gstin": "NA",
                            "state_code": "27", "state_name": "MH"},
                "items": [{"sno": "1", "name": "Item", "hsn": "", "unit_cost": 100.0, "amount": 100.0}],
                "gst_rate": 18,
            },
            "bill_no": "INV-001",
            "bill_date": "31-05-2024",
        }

        with patch("app.bot._bill_check_bill_to", new=AsyncMock()):
            await handle_callback(update, _ctx())
