"""
#genai: Tests for the sister-quotation renderer pipeline.
Renders each TargetFormat with a fixed QuoteDocument and verifies file output.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.processors.formats import TargetFormat
from app.processors.models import QuoteDocument, QuoteItem, QuoteSection


def _build_doc() -> QuoteDocument:
    return QuoteDocument(
        recipient_name="ABC Buyer",
        recipient_address_lines=["Plot 1, Industrial Area", "Mumbai"],
        subject="Required Items",
        ref_no="REF/2024/001",
        date="31-05-2024",
        valid_until="30-06-2024",
        sections=[
            QuoteSection(
                name="MEASUREMENT",
                items=[
                    QuoteItem("1.", "Digital Vernier Caliper", "2", 1500.0, 3000.0),
                    QuoteItem("2.", "Stainless Steel Ruler", "5", 200.0, 1000.0),
                ],
            ),
            QuoteSection(
                name="GENERAL",
                items=[
                    QuoteItem("3.", "Safety Goggles", "10", 80.0, 800.0),
                ],
            ),
        ],
    )


COMPANY = {
    "display_name": "Acme Test Inc",
    "address": "1 Test Avenue, Pune",
    "phone": "+91-9999988888",
    "gstin": "27TEST1234A1Z5",
    "email": "info@acme.test",
}


class TestRenderers:
    @pytest.mark.parametrize("fmt", list(TargetFormat))
    def test_render_each_format(self, tmp_path, fmt):
        from app.processors.renderers import render
        out = tmp_path / f"quote_{fmt.value}.docx"
        render(_build_doc(), fmt, out, COMPANY)
        assert out.exists()
        assert out.stat().st_size > 1000


class TestTargetFormat:
    def test_labels(self):
        for f in TargetFormat:
            assert isinstance(f.label, str) and f.label

    def test_parse_sv(self):
        assert TargetFormat.parse("sv enterprises") == TargetFormat.SV_ENTERPRISES

    def test_parse_sanmati(self):
        assert TargetFormat.parse("SANMATI") == TargetFormat.SANMATI

    def test_parse_nr(self):
        assert TargetFormat.parse("NR Survey") == TargetFormat.NR_SURVEY

    def test_parse_unknown(self):
        assert TargetFormat.parse("xxx") is None
