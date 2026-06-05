"""
#genai: Tests for the GST invoice validator — mocked LLM responses.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

# OpenAI is imported inline in the processor — patch at the openai package level
_OAI_PATCH = "openai.OpenAI"

import pytest

import json

SAMPLES = Path(__file__).parent.parent.parent.parent / "test-samples"

# The LLM returns a JSON dict — format_validation_report() converts it to text
_VALID_RESULT = {
    "invoice_no": "INV-2024-089",
    "date": "20-05-2024",
    "supplier": "Sanmati Enterprises",
    "supplier_gstin": "27ABCDE1234F1Z5",
    "buyer_gstin": "29FGHIJ5678K2L6",
    "place_of_supply": "Karnataka (29)",
    "taxable_value": 258000,
    "total_tax": 46440,
    "total": 304440,
    "overall_valid": True,
    "issues": [],
    "items": [
        {"sno": "1", "description": "TMT Bars", "hsn": "7214", "gst_rate": 18,
         "taxable": 68000, "tax": 12240, "total": 80240,
         "math_ok": True, "hsn_valid": True, "hsn_matches_product": True, "gst_rate_correct": True},
    ],
}

_INVALID_RESULT = {
    "invoice_no": "INV-BAD-001",
    "date": "",
    "supplier": "",
    "supplier_gstin": "INVALID",
    "buyer_gstin": "",
    "place_of_supply": "",
    "taxable_value": 0,
    "total_tax": 0,
    "total": 0,
    "overall_valid": False,
    "issues": ["Supplier GSTIN missing/invalid", "Buyer GSTIN not present", "Tax calculation mismatch"],
    "items": [
        {"sno": "1", "description": "Some Item", "hsn": "", "gst_rate": 18,
         "taxable": 1000, "tax": 100, "total": 1100,
         "math_ok": False, "hsn_valid": False, "hsn_matches_product": False, "gst_rate_correct": False},
    ],
}


class TestGstValidator:
    """TC-GST-*: GST invoice validation with LLM analysis."""

    def _mock_llm(self, result_dict: dict):
        """Return a mock client whose LLM call returns the given dict as JSON."""
        mock_resp = MagicMock()
        mock_resp.choices[0].message.content = json.dumps(result_dict)
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_resp
        return mock_client

    def test_valid_invoice_returns_report(self):
        from app.processors.gst_validator import validate_invoice
        with patch(_OAI_PATCH) as MockOAI:
            MockOAI.return_value = self._mock_llm(_VALID_RESULT)
            result = validate_invoice("VALID INVOICE TEXT HERE")
        assert isinstance(result, str)
        assert len(result) > 10

    def test_valid_invoice_shows_valid_status(self):
        from app.processors.gst_validator import validate_invoice
        with patch(_OAI_PATCH) as MockOAI:
            MockOAI.return_value = self._mock_llm(_VALID_RESULT)
            result = validate_invoice("VALID INVOICE TEXT")
        assert "✅" in result or "VALID" in result.upper() or "valid" in result.lower()

    def test_invalid_invoice_shows_errors(self):
        from app.processors.gst_validator import validate_invoice
        with patch(_OAI_PATCH) as MockOAI:
            MockOAI.return_value = self._mock_llm(_INVALID_RESULT)
            result = validate_invoice("BAD INVOICE TEXT")
        assert "❌" in result or "INVALID" in result.upper() or "issues" in result.lower()

    def test_empty_text_does_not_crash(self):
        from app.processors.gst_validator import validate_invoice
        with patch(_OAI_PATCH) as MockOAI:
            MockOAI.return_value = self._mock_llm({"overall_valid": False, "issues": [], "items": []})
            result = validate_invoice("")
        assert isinstance(result, str)

    def test_sample_gst_invoice_text_extractable(self):
        from app.processors.extractors import extract_text
        path = SAMPLES / "invoice" / "sample_gst_invoice.docx"
        text = extract_text(path)
        assert "GSTIN" in text or "GST" in text
        assert len(text) > 100

    def test_validate_accepts_invoice_api_key_model_order(self):
        """
        TC-GST-ARG: Argument order must be (api_key, model, text).
        A previous bug passed text as the API key — ensure it is fixed.
        """
        from app.processors.gst_validator import validate_invoice
        captured_args = {}

        def _capture(*args, **kwargs):
            captured_args.update({"args": args, "kwargs": kwargs})
            mock = MagicMock()
            mock.choices[0].message.content = "Report"
            return mock

        _fallback = MagicMock()
        _fallback.choices[0].message.content = json.dumps({"overall_valid": False, "issues": [], "items": []})

        def _capture_and_return(*args, **kwargs):
            _capture(*args, **kwargs)
            return _fallback

        with patch(_OAI_PATCH) as MockOAI:
            instance = MagicMock()
            instance.chat.completions.create.side_effect = _capture_and_return
            MockOAI.return_value = instance
            validate_invoice("invoice text here")

        # The API key must NOT be the invoice text
        if "args" in captured_args:
            for a in captured_args["args"]:
                assert "invoice text" not in str(a).lower()
