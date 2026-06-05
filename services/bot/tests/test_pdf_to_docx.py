"""
#genai: Tests for app.processors.pdf_to_docx — PDF → DOCX conversion.
"""
from __future__ import annotations

from pathlib import Path

import pytest


def _make_simple_pdf(path: Path) -> None:
    """Build a tiny PDF using fpdf2 so we can round-trip it."""
    from fpdf import FPDF
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "", 12)
    pdf.cell(0, 10, "Hello from DocSeva PDF", ln=True)
    pdf.cell(0, 10, "Second line for extraction.")
    pdf.output(str(path))


class TestPdfToDocx:
    def test_alias_exported(self):
        from app.processors.pdf_to_docx import pdf_to_docx, convert_pdf_to_docx
        assert pdf_to_docx is not None
        assert convert_pdf_to_docx is not None

    def test_round_trip(self, tmp_path):
        from app.processors.pdf_to_docx import pdf_to_docx
        pdf_path = tmp_path / "src.pdf"
        _make_simple_pdf(pdf_path)
        out = tmp_path / "out.docx"
        result = pdf_to_docx(pdf_path, out)
        assert result.exists()
        assert result.stat().st_size > 500

    def test_alias_matches_canonical(self, tmp_path):
        from app.processors.pdf_to_docx import pdf_to_docx, convert_pdf_to_docx
        pdf_path = tmp_path / "src.pdf"
        _make_simple_pdf(pdf_path)
        a = tmp_path / "a.docx"
        b = tmp_path / "b.docx"
        pdf_to_docx(pdf_path, a)
        convert_pdf_to_docx(pdf_path, b)
        assert a.exists() and b.exists()
