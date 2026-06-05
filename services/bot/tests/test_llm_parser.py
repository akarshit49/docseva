"""
#genai: Tests for app.processors.llm_parser — schema mapping with mocked OpenAI.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

# llm_parser does `from openai import OpenAI` at module load — patch the local reference.
_OAI_PATCH = "app.processors.llm_parser.OpenAI"


def _mock_completion(content: str):
    m = MagicMock()
    m.choices = [MagicMock()]
    m.choices[0].message.content = content
    return m


class TestParseQuotationText:
    def test_simple_quote_parses(self):
        from app.processors.llm_parser import parse_quotation_text
        body = {
            "recipient_name": "ABC Buyer",
            "recipient_address_lines": ["123 Main St"],
            "subject": "items",
            "ref_no": "R1",
            "date": "31-05-2024",
            "valid_until": "30-06-2024",
            "sections": [
                {
                    "name": "GENERAL",
                    "items": [
                        {"sno": "1.", "description": "Item A", "qty": "2", "unit_price": 100.0},
                    ],
                }
            ],
        }
        with patch(_OAI_PATCH) as cls:
            client = cls.return_value
            client.chat.completions.create.return_value = _mock_completion(json.dumps(body))
            quote = parse_quotation_text("key", "model", "raw text")
        assert quote.recipient_name == "ABC Buyer"
        assert len(quote.sections) == 1
        item = quote.sections[0].items[0]
        assert item.unit_price == 100.0
        assert item.total == 200.0

    def test_markdown_wrapped_json_still_parses(self):
        from app.processors.llm_parser import parse_quotation_text
        body = {
            "recipient_name": "X", "recipient_address_lines": [], "subject": "",
            "ref_no": "", "date": "", "valid_until": "",
            "sections": [{"name": "G", "items": []}],
        }
        wrapped = "```json\n" + json.dumps(body) + "\n```"
        with patch(_OAI_PATCH) as cls:
            client = cls.return_value
            client.chat.completions.create.return_value = _mock_completion(wrapped)
            quote = parse_quotation_text("key", "model", "x")
        assert quote.recipient_name == "X"

    def test_missing_api_key_raises(self):
        from app.processors.llm_parser import parse_quotation_text
        with pytest.raises(RuntimeError):
            parse_quotation_text("", "model", "text")

    def test_bad_response_raises(self):
        from app.processors.llm_parser import parse_quotation_text
        with patch(_OAI_PATCH) as cls:
            client = cls.return_value
            client.chat.completions.create.return_value = _mock_completion("not json")
            with pytest.raises(Exception):
                parse_quotation_text("key", "model", "x")

    def test_safe_qty_handles_set_suffix(self):
        from app.processors.llm_parser import _safe_qty
        assert _safe_qty("3 set") == 3.0
        assert _safe_qty("abc") == 1.0
        assert _safe_qty("2.5") == 2.5
