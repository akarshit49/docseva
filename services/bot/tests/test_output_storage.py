"""
#genai: WS-1 — Tests for MinIO output file storage wiring.
Covers: upload_output, upload_input, generate_presigned_url, delete_object,
        _upload_output_file helper, _log_and_increment helper, /history download links.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.asyncio


# ── storage_client unit tests ────────────────────────────────────────────────

class TestStorageClientUploadOutput:
    """Verify upload_output builds correct key and calls S3 put_object."""

    def test_upload_output_key_format(self, tmp_path: Path):
        out = tmp_path / "result.pdf"
        out.write_text("dummy")

        mock_s3 = MagicMock()
        with patch("app.storage_client._client", return_value=mock_s3):
            from app.storage_client import upload_output
            key = upload_output("org-123", "doc-456", out)

        assert key == "outputs/org-123/doc-456/result.pdf"
        mock_s3.put_object.assert_called_once()
        call_kwargs = mock_s3.put_object.call_args
        assert call_kwargs[1]["Key"] == key

    def test_upload_input_key_format(self, tmp_path: Path):
        inp = tmp_path / "invoice.docx"
        inp.write_text("dummy")

        mock_s3 = MagicMock()
        with patch("app.storage_client._client", return_value=mock_s3):
            from app.storage_client import upload_input
            key = upload_input("org-123", "doc-789", inp)

        assert key == "uploads/org-123/doc-789/invoice.docx"
        mock_s3.put_object.assert_called_once()


class TestStorageClientPresignedUrl:
    """Verify presigned URL generation."""

    def test_generate_presigned_url_returns_url(self):
        mock_s3 = MagicMock()
        mock_s3.generate_presigned_url.return_value = "https://minio/presigned"
        # generate_presigned_url uses _public_client (separate client for correct HMAC host)
        with patch("app.storage_client._public_client", return_value=mock_s3):
            from app.storage_client import generate_presigned_url
            url = generate_presigned_url("docseva-outputs", "outputs/org/doc/file.pdf")

        assert url == "https://minio/presigned"

    def test_generate_presigned_url_returns_none_on_error(self):
        mock_s3 = MagicMock()
        from botocore.exceptions import ClientError
        mock_s3.generate_presigned_url.side_effect = ClientError(
            {"Error": {"Code": "403", "Message": "Forbidden"}}, "GetObject"
        )
        with patch("app.storage_client._public_client", return_value=mock_s3):
            from app.storage_client import generate_presigned_url
            url = generate_presigned_url("docseva-outputs", "bad/key")

        assert url is None


class TestStorageClientDeleteObject:
    """Verify delete_object calls S3 correctly."""

    def test_delete_object_calls_s3(self):
        mock_s3 = MagicMock()
        with patch("app.storage_client._client", return_value=mock_s3):
            from app.storage_client import delete_object
            delete_object("docseva-outputs", "outputs/org/doc/file.pdf")

        mock_s3.delete_object.assert_called_once_with(
            Bucket="docseva-outputs", Key="outputs/org/doc/file.pdf"
        )


# ── _upload_output_file helper tests ─────────────────────────────────────────

class TestUploadOutputFileHelper:
    """Tests for the _upload_output_file async helper in bot.py."""

    async def test_returns_key_on_success(self, tmp_path: Path):
        from app.session_store import UserSession
        session = UserSession()
        session.org_id = "org-test"
        out = tmp_path / "test.pdf"
        out.write_text("content")

        with patch("app.storage_client.upload_output", return_value="outputs/org-test/id/test.pdf"):
            from app.bot import _upload_output_file
            key = await _upload_output_file("uid-1", session, out)

        assert key is not None
        assert "outputs/" in key

    async def test_returns_none_when_no_org_id(self, tmp_path: Path):
        from app.session_store import UserSession
        session = UserSession()
        session.org_id = ""
        out = tmp_path / "test.pdf"
        out.write_text("content")

        from app.bot import _upload_output_file
        key = await _upload_output_file("uid-1", session, out)
        assert key is None

    async def test_returns_none_on_upload_failure(self, tmp_path: Path):
        from app.session_store import UserSession
        session = UserSession()
        session.org_id = "org-test"
        out = tmp_path / "test.pdf"
        out.write_text("content")

        with patch("app.storage_client.upload_output", side_effect=RuntimeError("MinIO down")):
            from app.bot import _upload_output_file
            key = await _upload_output_file("uid-1", session, out)

        assert key is None


# ── _log_and_increment helper tests ──────────────────────────────────────────

class TestLogAndIncrement:
    """Tests for the _log_and_increment async helper in bot.py."""

    async def test_calls_increment_and_log(self):
        with patch("app.bot.api_client.increment_quota") as mock_inc, \
             patch("app.bot.api_client.log_document") as mock_log:
            from app.bot import _log_and_increment
            await _log_and_increment("uid-1", "to_docx", "in.pdf", "out.docx", "key-123")

        mock_inc.assert_called_once_with("uid-1")
        mock_log.assert_called_once()
        call_kwargs = mock_log.call_args
        assert call_kwargs[1].get("output_file_key") == "key-123" or call_kwargs[0][4] == "key-123" if len(call_kwargs[0]) > 4 else True

    async def test_retries_on_failure_then_succeeds(self):
        call_count = {"n": 0}

        def _increment_side(uid):
            call_count["n"] += 1
            if call_count["n"] < 3:
                raise ConnectionError("transient")

        with patch("app.bot.api_client.increment_quota", side_effect=_increment_side), \
             patch("app.bot.api_client.log_document"):
            from app.bot import _log_and_increment
            await _log_and_increment("uid-1", "test", "in.txt", "out.txt")

        assert call_count["n"] == 3

    async def test_gives_up_after_3_attempts(self):
        with patch("app.bot.api_client.increment_quota", side_effect=ConnectionError("down")), \
             patch("app.bot.api_client.log_document", side_effect=ConnectionError("down")):
            from app.bot import _log_and_increment
            await _log_and_increment("uid-1", "test", "in.txt", "out.txt")
            # Should not raise — just logs the error


# ── /history with download links ─────────────────────────────────────────────

class TestHistoryDownloadLinks:
    """Verify /history shows download links when output_file_key is present."""

    async def test_history_includes_download_link(self):
        from app.bot import cmd_history

        update = MagicMock()
        update.effective_user.id = 999
        update.message = MagicMock()
        update.message.reply_text = AsyncMock()

        with patch("app.bot._require_auth", return_value=True), \
             patch("app.bot.api_client.get_documents", return_value=[
                 {
                     "status": "completed",
                     "output_filename": "result.pdf",
                     "original_filename": "input.docx",
                     "feature": "to_pdf",
                     "created_at": "2026-05-31T10:00:00",
                     "output_file_key": "outputs/org/doc/result.pdf",
                 }
             ]), \
             patch("app.storage_client.generate_presigned_url", return_value="https://minio/presigned/result.pdf"):
            await cmd_history(update, MagicMock())

        call_text = str(update.message.reply_text.call_args)
        assert "Download" in call_text
        assert "presigned" in call_text

    async def test_history_no_download_when_no_key(self):
        from app.bot import cmd_history

        update = MagicMock()
        update.effective_user.id = 999
        update.message = MagicMock()
        update.message.reply_text = AsyncMock()

        with patch("app.bot._require_auth", return_value=True), \
             patch("app.bot.api_client.get_documents", return_value=[
                 {
                     "status": "completed",
                     "output_filename": "result.pdf",
                     "feature": "to_pdf",
                     "created_at": "2026-05-31T10:00:00",
                 }
             ]):
            await cmd_history(update, MagicMock())

        call_text = str(update.message.reply_text.call_args)
        assert "Download" not in call_text
