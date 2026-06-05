"""
#genai: WS-9 — Tests for error handling: retry behaviour, friendly error mapping,
        soft_reset vs hard reset, tenacity decorator on api_client.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.error_messages import friendly_error, ERROR_CODES
from app.session_store import BotState, SessionStore

pytestmark = pytest.mark.asyncio


# ── friendly_error mapping ───────────────────────────────────────────────────

class TestFriendlyError:
    """Verify error mapping produces user-friendly messages."""

    def test_key_error_maps_to_document_read_message(self):
        msg = friendly_error(KeyError("items"), "bill_to_make")
        assert "couldn't read" in msg.lower()
        assert "Tip" in msg
        assert "DOC/DOCX" in msg

    def test_json_decode_error_maps_correctly(self):
        import json
        msg = friendly_error(json.JSONDecodeError("bad", "", 0), "sister_quotation")
        assert "unexpected results" in msg.lower()

    def test_value_error_maps_correctly(self):
        msg = friendly_error(ValueError("bad number"), "gst_validate")
        assert "couldn't be processed" in msg.lower()

    def test_connection_error_maps_correctly(self):
        msg = friendly_error(httpx.ConnectError("refused"), "")
        assert "server" in msg.lower() or "connect" in msg.lower()

    def test_timeout_error_maps_correctly(self):
        msg = friendly_error(httpx.TimeoutException("timeout"), "")
        assert "long" in msg.lower()

    def test_unknown_error_gives_generic_message(self):
        msg = friendly_error(RuntimeError("something weird"), "")
        assert "Something went wrong" in msg

    def test_message_includes_file_still_loaded_hint(self):
        msg = friendly_error(RuntimeError("x"), "to_docx")
        assert "file is still loaded" in msg.lower()

    def test_feature_hint_for_bg_remove(self):
        msg = friendly_error(RuntimeError("x"), "bg_remove")
        assert "image" in msg.lower()

    def test_feature_hint_for_quotation_compare(self):
        msg = friendly_error(RuntimeError("x"), "quotation_compare")
        assert "quotation" in msg.lower()


class TestErrorCodes:
    """Verify error code catalogue entries exist."""

    def test_all_error_codes_present(self):
        for code in [f"E{i:03d}" for i in range(1, 11)]:
            assert code in ERROR_CODES, f"Missing error code {code}"

    def test_e004_has_placeholder(self):
        assert "{used}" in ERROR_CODES["E004"]
        assert "{limit}" in ERROR_CODES["E004"]


# ── tenacity retry on api_client ─────────────────────────────────────────────

class TestApiClientRetry:
    """Verify tenacity retry decorator is applied to api_client functions."""

    def test_get_quota_retries_on_connect_error(self):
        call_count = {"n": 0}

        def _mock_get(*a, **kw):
            call_count["n"] += 1
            if call_count["n"] < 3:
                raise httpx.ConnectError("refused")
            resp = MagicMock()
            resp.is_success = True
            resp.json.return_value = {"quota_ok": True, "docs_used": 0, "docs_limit": 10}
            return resp

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get = _mock_get

        with patch("httpx.Client", return_value=mock_client):
            from app.api_client import get_quota
            result = get_quota("uid-1")

        assert result["quota_ok"] is True
        assert call_count["n"] == 3

    def test_increment_quota_retries_on_timeout(self):
        call_count = {"n": 0}

        def _mock_post(*a, **kw):
            call_count["n"] += 1
            if call_count["n"] < 2:
                raise httpx.TimeoutException("timeout")
            resp = MagicMock()
            resp.is_success = True
            return resp

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post = _mock_post

        with patch("httpx.Client", return_value=mock_client):
            from app.api_client import increment_quota
            increment_quota("uid-1")

        assert call_count["n"] == 2

    def test_get_quota_raises_after_max_retries(self):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.side_effect = httpx.ConnectError("down")

        with patch("httpx.Client", return_value=mock_client):
            from app.api_client import get_quota
            with pytest.raises(httpx.ConnectError):
                get_quota("uid-1")


# ── soft_reset in error flows ────────────────────────────────────────────────

class TestSoftResetInErrorFlows:
    """Verify that processing failures use soft_reset, not hard reset."""

    async def test_sister_quotation_failure_uses_soft_reset(self):
        from app.bot import _convert_with_format_id, store
        uid = "err_sr_1"
        s = store.get(uid)
        s.is_registered = True
        s.org_id = "org-1"
        s.pending_file = Path("/tmp/test.docx")
        s.original_filename = "test.docx"
        s.state = BotState.WAITING_ACTION

        msg = MagicMock()
        msg.reply_text = AsyncMock()
        msg.reply_document = AsyncMock()

        edit_msg = MagicMock()
        edit_msg.edit_message_text = AsyncMock()

        with patch("app.processors.service.convert_with_template", side_effect=RuntimeError("parse error")):
            await _convert_with_format_id(
                msg, uid, s, "fmt-1", "key", "Test Format", Path("/tmp/tmpl.pdf"),
                edit_msg=edit_msg,
            )

        session = store.get(uid)
        # soft_reset should keep the file
        assert session.pending_file == Path("/tmp/test.docx")
        assert session.state == BotState.WAITING_ACTION

    async def test_to_docx_failure_preserves_file(self):
        from app.bot import _do_to_docx, store
        uid = "err_sr_2"
        s = store.get(uid)
        s.is_registered = True
        s.org_id = "org-1"
        s.pending_file = Path("/tmp/test.pdf")
        s.original_filename = "test.pdf"
        s.state = BotState.WAITING_ACTION

        query = MagicMock()
        query.edit_message_text = AsyncMock()
        query.message = MagicMock()
        query.message.reply_text = AsyncMock()

        with patch("app.bot._check_quota", return_value=(True, "")), \
             patch("app.processors.pdf_to_docx.pdf_to_docx", side_effect=RuntimeError("corrupt pdf")):
            await _do_to_docx(query, uid, s)

        session = store.get(uid)
        assert session.pending_file == Path("/tmp/test.pdf")
        assert session.state == BotState.WAITING_ACTION


# ── No more except:pass ──────────────────────────────────────────────────────

class TestNoSilentFailures:
    """Verify that the old try/except:pass pattern is replaced."""

    def test_bot_py_has_no_bare_except_pass(self):
        """Scan bot.py for the old pattern where quota/log calls are silently swallowed."""
        import re
        bot_path = Path(__file__).parent.parent / "app" / "bot.py"
        content = bot_path.read_text()

        # Match the OLD pattern: try block with increment_quota + log_document
        # followed immediately by 'except Exception:\n            pass'
        # (NOT the _log_and_increment helper which has retry logic)
        pattern = r"try:\s*\n\s+api_client\.increment_quota\([^)]+\)\s*\n\s+api_client\.log_document\([^)]+\)\s*\n\s+except Exception:\s*\n\s+pass"
        matches = re.findall(pattern, content)
        assert len(matches) == 0, (
            f"Found {len(matches)} old try/except:pass blocks for quota/logging. "
            "These should be replaced with _log_and_increment()."
        )
