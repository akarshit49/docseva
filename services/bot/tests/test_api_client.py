"""
#genai: Tests for app.api_client — HTTP error handling and request shape.
We patch httpx.Client so no real network call happens.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def _resp(status: int = 200, json_body: dict | None = None, text: str = ""):
    r = MagicMock()
    r.status_code = status
    r.is_success = 200 <= status < 300
    r.json = MagicMock(return_value=(json_body if json_body is not None else {}))
    r.text = text
    return r


@pytest.fixture()
def mock_client():
    """Patch httpx.Client to return a MagicMock client with configurable responses."""
    with patch("httpx.Client") as cls:
        client = MagicMock()
        cls.return_value.__enter__.return_value = client
        yield client


class TestApiErrors:
    def test_api_error_raised_on_500(self, mock_client):
        from app.api_client import ApiError, get_quota
        mock_client.get.return_value = _resp(500, json_body={"detail": "boom"})
        with pytest.raises(ApiError) as ei:
            get_quota("123")
        assert ei.value.status == 500

    def test_api_error_falls_back_to_text(self, mock_client):
        from app.api_client import ApiError, get_quota
        bad = _resp(500)
        bad.json = MagicMock(side_effect=ValueError("not json"))
        bad.text = "<html>oops</html>"
        mock_client.get.return_value = bad
        with pytest.raises(ApiError):
            get_quota("123")


class TestAuth:
    def test_register_or_login_returns_json(self, mock_client):
        from app.api_client import register_or_login
        mock_client.post.return_value = _resp(200, json_body={"user_id": "u", "is_new": True})
        out = register_or_login("123", "Akarshit", "ACo")
        assert out["user_id"] == "u"

    def test_get_quota_returns_json(self, mock_client):
        from app.api_client import get_quota
        mock_client.get.return_value = _resp(200, json_body={"plan": "free", "docs_used": 0, "docs_limit": 10, "quota_ok": True})
        out = get_quota("123")
        assert out["plan"] == "free"

    def test_increment_quota_no_return(self, mock_client):
        from app.api_client import increment_quota
        mock_client.post.return_value = _resp(204)
        increment_quota("123")  # no exception


class TestProfile:
    def test_get_profile_404_returns_none(self, mock_client):
        from app.api_client import get_company_profile
        mock_client.get.return_value = _resp(404)
        assert get_company_profile("123") is None

    def test_get_profile_200_returns_dict(self, mock_client):
        from app.api_client import get_company_profile
        mock_client.get.return_value = _resp(200, json_body={"display_name": "ACo"})
        p = get_company_profile("123")
        assert p["display_name"] == "ACo"

    #genai: WS-3 — increment_counter atomic API
    def test_increment_counter_returns_new_value(self, mock_client):
        from app.api_client import increment_counter
        mock_client.post.return_value = _resp(200, json_body={
            "counter_type": "invoice", "new_value": 43
        })
        out = increment_counter("123", "invoice")
        assert out == 43
        # Verify the request body
        call_kwargs = mock_client.post.call_args.kwargs
        assert call_kwargs["json"] == {"counter_type": "invoice"}

    def test_increment_counter_quotation(self, mock_client):
        from app.api_client import increment_counter
        mock_client.post.return_value = _resp(200, json_body={
            "counter_type": "quotation", "new_value": 8
        })
        assert increment_counter("123", "quotation") == 8

    def test_increment_counter_raises_on_bad_type(self, mock_client):
        from app.api_client import ApiError, increment_counter
        mock_client.post.return_value = _resp(400, json_body={"detail": "bad type"})
        with pytest.raises(ApiError):
            increment_counter("123", "bogus")

    def test_log_document_passes_new_fields(self, mock_client):
        from app.api_client import log_document
        mock_client.post.return_value = _resp(200, json_body={"id": "doc-1"})
        log_document(
            "123", "create_invoice",
            original_filename="(scratch) ABC",
            output_filename="INV-0001.pdf",
            output_file_key="outputs/org/abc/INV-0001.pdf",
            input_file_key="inputs/org/abc/orig.pdf",
            source_document_id="11111111-2222-3333-4444-555555555555",
            document_type="invoice",
            metadata={"bill_number": "INV-0001"},
        )
        body = mock_client.post.call_args.kwargs["json"]
        assert body["input_file_key"] == "inputs/org/abc/orig.pdf"
        assert body["source_document_id"] == "11111111-2222-3333-4444-555555555555"
        assert body["document_type"] == "invoice"
        assert body["metadata"] == {"bill_number": "INV-0001"}

    def test_update_profile(self, mock_client):
        from app.api_client import update_company_profile
        mock_client.put.return_value = _resp(200, json_body={"display_name": "New"})
        out = update_company_profile("123", {"display_name": "New"})
        assert out["display_name"] == "New"
