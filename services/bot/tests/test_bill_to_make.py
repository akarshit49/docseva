"""
#genai: Tests for the Bill-to-Make LLM pipeline with mocked OpenAI calls.
Covers: parsing, HSN validation logic, BillTo check, and PDF generation end-to-end.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

# OpenAI is imported inline (from openai import OpenAI) — mock at the openai package level
_OAI_PATCH = "openai.OpenAI"

import pytest

SAMPLES = Path(__file__).parent.parent.parent.parent / "test-samples"


# ── parse_bill_doc_text (mocked LLM) ──────────────────────────────────────────

class TestParseBillDocText:
    """TC-PARSE-*: LLM-based structured extraction from bill text."""

    def _mock_llm(self, response_json: dict):
        mock_resp = MagicMock()
        mock_resp.choices[0].message.content = json.dumps(response_json)
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_resp
        return mock_client

    def test_returns_parsed_dict_on_success(self, parsed_bill_complete):
        from app.processors.bill_to_make import parse_bill_doc_text
        with patch(_OAI_PATCH) as MockOAI:
            MockOAI.return_value = self._mock_llm(parsed_bill_complete)
            result = parse_bill_doc_text("fake-key", "gpt-4o-mini", "Some bill text")
        assert isinstance(result, dict)
        assert "items" in result
        assert "bill_to" in result

    def test_computes_subtotal_server_side(self):
        from app.processors.bill_to_make import parse_bill_doc_text
        llm_data = {
            "bill_to": {"name": "Co", "address": "Addr", "gstin": "NA", "state_code": "27", "state_name": "MH"},
            "ship_to": {"name": "Co", "address": "Addr", "gstin": "NA", "state_code": "27", "state_name": "MH"},
            "items": [
                {"sno": "1", "name": "Item A", "hsn": "1234", "unit_cost": 1000.0, "amount": 1000.0},
                {"sno": "2", "name": "Item B", "hsn": "5678", "unit_cost": 500.0, "amount": 500.0},
            ],
            "gst_rate": 18,
        }
        with patch(_OAI_PATCH) as MockOAI:
            MockOAI.return_value = self._mock_llm(llm_data)
            result = parse_bill_doc_text("fake-key", "gpt-4o-mini", "Some bill text")
        assert result["subtotal"] == 1500.0
        assert abs(result["gst_amount"] - 270.0) < 1
        assert abs(result["total"] - 1770.0) < 1

    def test_filters_zero_amount_items(self):
        from app.processors.bill_to_make import parse_bill_doc_text
        llm_data = {
            "bill_to": {"name": "Co", "address": "Addr", "gstin": "NA", "state_code": "27", "state_name": "MH"},
            "ship_to": {"name": "Co", "address": "Addr", "gstin": "NA", "state_code": "27", "state_name": "MH"},
            "items": [
                {"sno": "1", "name": "Valid Item", "hsn": "1234", "unit_cost": 5000.0, "amount": 5000.0},
                {"sno": "2", "name": "", "hsn": "", "unit_cost": 0.0, "amount": 0.0},
            ],
            "gst_rate": 18,
        }
        with patch(_OAI_PATCH) as MockOAI:
            MockOAI.return_value = self._mock_llm(llm_data)
            result = parse_bill_doc_text("fake-key", "gpt-4o-mini", "Some bill text")
        assert all(item["amount"] > 0 for item in result["items"])

    def test_resequences_sno(self):
        from app.processors.bill_to_make import parse_bill_doc_text
        llm_data = {
            "bill_to": {"name": "Co", "address": "Addr", "gstin": "NA", "state_code": "27", "state_name": "MH"},
            "ship_to": {"name": "Co", "address": "Addr", "gstin": "NA", "state_code": "27", "state_name": "MH"},
            "items": [
                {"sno": "A", "name": "Item 1", "hsn": "8413", "unit_cost": 100.0, "amount": 100.0},
                {"sno": "B", "name": "Item 2", "hsn": "8481", "unit_cost": 200.0, "amount": 200.0},
                {"sno": "C", "name": "Item 3", "hsn": "7304", "unit_cost": 300.0, "amount": 300.0},
            ],
            "gst_rate": 18,
        }
        with patch(_OAI_PATCH) as MockOAI:
            MockOAI.return_value = self._mock_llm(llm_data)
            result = parse_bill_doc_text("fake-key", "gpt-4o-mini", "Some bill text")
        snos = [item["sno"] for item in result["items"]]
        assert snos == ["1", "2", "3"]

    def test_bad_json_raises(self):
        from app.processors.bill_to_make import parse_bill_doc_text
        mock_resp = MagicMock()
        mock_resp.choices[0].message.content = "NOT VALID JSON AT ALL"
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_resp
        with patch(_OAI_PATCH) as MockOAI:
            MockOAI.return_value = mock_client
            with pytest.raises(Exception):
                parse_bill_doc_text("fake-key", "gpt-4o-mini", "Some bill text")


# ── HSN validation logic ───────────────────────────────────────────────────────

class TestHsnValidation:
    """TC-HSN-*: HSN code detection and user prompting logic."""

    def _missing_hsn_items(self, parsed: dict) -> list:
        """Helper that mirrors the bot's _is_blank logic."""
        from app.utils import is_blank as _is_blank
        return [
            (i, item)
            for i, item in enumerate(parsed.get("items", []))
            if _is_blank(str(item.get("hsn", "")))
        ]

    def test_detects_empty_hsn(self, parsed_bill_no_hsn):
        missing = self._missing_hsn_items(parsed_bill_no_hsn)
        assert len(missing) == 2

    def test_all_hsn_present_returns_empty(self, parsed_bill_complete):
        missing = self._missing_hsn_items(parsed_bill_complete)
        assert len(missing) == 0

    def test_na_hsn_is_missing(self):
        parsed = {"items": [{"sno": "1", "name": "Valve", "hsn": "NA", "unit_cost": 1000, "amount": 1000}]}
        missing = self._missing_hsn_items(parsed)
        assert len(missing) == 1

    def test_partial_hsn_fill_detects_remaining(self):
        parsed = {
            "items": [
                {"sno": "1", "name": "Item A", "hsn": "8413", "unit_cost": 100, "amount": 100},
                {"sno": "2", "name": "Item B", "hsn": "", "unit_cost": 200, "amount": 200},
                {"sno": "3", "name": "Item C", "hsn": "", "unit_cost": 300, "amount": 300},
            ]
        }
        # Simulate user providing code for item 2 only
        parsed["items"][1]["hsn"] = "8481"
        missing = self._missing_hsn_items(parsed)
        assert len(missing) == 1
        assert missing[0][1]["name"] == "Item C"


# ── BillTo check logic ────────────────────────────────────────────────────────

class TestBillToCheck:
    """TC-BILLTO-*: Bill To / Ship To completeness detection."""

    def _has_bill_to(self, parsed: dict) -> bool:
        from app.utils import is_blank as _is_blank
        bill_to = parsed.get("bill_to", {})
        return (
            bool(bill_to.get("name", "").strip())
            and not _is_blank(bill_to.get("name", ""))
            and bool(bill_to.get("address", "").strip())
            and not _is_blank(bill_to.get("address", ""))
        )

    def test_complete_bill_to_passes(self, parsed_bill_complete):
        assert self._has_bill_to(parsed_bill_complete) is True

    def test_empty_bill_to_fails(self, parsed_bill_no_billto):
        assert self._has_bill_to(parsed_bill_no_billto) is False

    def test_na_name_fails(self):
        parsed = {"bill_to": {"name": "NA", "address": "Some Address"}}
        assert self._has_bill_to(parsed) is False

    def test_na_address_fails(self):
        parsed = {"bill_to": {"name": "Valid Name", "address": "N/A"}}
        assert self._has_bill_to(parsed) is False

    def test_missing_keys_fails(self):
        parsed = {"bill_to": {}}
        assert self._has_bill_to(parsed) is False


# ── End-to-end: parse sample files ────────────────────────────────────────────

class TestBillE2EWithSampleFiles:
    """TC-E2E-BILL-*: Parse actual sample DOCX files through the extractor."""

    def test_extracts_text_from_complete_invoice(self):
        from app.processors.extractors import extract_text
        path = SAMPLES / "invoice" / "sample_invoice_complete.docx"
        text = extract_text(path)
        assert len(text) > 200
        assert "XYZ" in text or "Steel" in text or "Cement" in text

    def test_extracts_text_from_no_hsn_invoice(self):
        from app.processors.extractors import extract_text
        path = SAMPLES / "invoice" / "sample_invoice_no_hsn.docx"
        text = extract_text(path)
        assert "Pump" in text or "Water" in text.lower()

    def test_extracts_text_from_multi_table_invoice(self):
        from app.processors.extractors import extract_text
        path = SAMPLES / "invoice" / "sample_invoice_multi_table.docx"
        text = extract_text(path)
        # Both sections must appear
        assert "Civil" in text or "Electrical" in text or "Excavation" in text

    def test_generate_pdf_from_complete_sample(self, tmp_path, company_profile):
        from app.processors.bill_to_make import _build_company_info, generate_bill_pdf
        parsed = {
            "bill_to": {"name": "XYZ Construction", "address": "Plot 12, Noida", "gstin": "09ABCDE1234F1Z5",
                        "state_code": "09", "state_name": "Uttar Pradesh"},
            "ship_to": {"name": "XYZ Construction", "address": "Plot 12, Noida", "gstin": "09ABCDE1234F1Z5",
                        "state_code": "09", "state_name": "Uttar Pradesh"},
            "items": [
                {"sno": "1", "name": "Cement OPC 53 Grade", "hsn": "2523", "unit_cost": 380.0, "amount": 76000.0},
                {"sno": "2", "name": "TMT Steel Bars 10mm", "hsn": "7214", "unit_cost": 68.0, "amount": 34000.0},
            ],
            "gst_rate": 18,
            "subtotal": 110000.0,
            "gst_amount": 19800.0,
            "total": 129800.0,
        }
        out = tmp_path / "real_bill.pdf"
        ci = _build_company_info(company_profile)
        generate_bill_pdf(parsed, "INV-TEST-001", "31-05-2024", out, ci)
        assert out.exists()
        assert out.stat().st_size > 500
        with open(out, "rb") as f:
            assert f.read(4) == b"%PDF"
