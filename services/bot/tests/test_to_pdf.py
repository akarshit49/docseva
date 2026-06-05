"""
#genai: Smoke tests for app.processors.to_pdf — DOCX/XLSX → PDF.
Verifies that the pure-Python pipeline produces a valid PDF without LibreOffice.
"""
from __future__ import annotations

from pathlib import Path

import pytest

SAMPLES = Path(__file__).parent.parent.parent.parent / "test-samples"


class TestDocxToPdf:
    """KI-02: pure-Python DOCX→PDF works without LibreOffice."""

    def test_docx_to_pdf_smoke(self, tmp_path):
        from app.processors.to_pdf import convert_to_pdf
        src = SAMPLES / "quotation" / "sample_quotation.docx"
        if not src.exists():
            pytest.skip("Sample quotation docx not present")
        out = tmp_path / "out.pdf"
        result = convert_to_pdf(src, out)
        assert result.exists()
        assert result.stat().st_size > 500
        with open(result, "rb") as f:
            assert f.read(4) == b"%PDF"

    def test_unsupported_extension_raises(self, tmp_path):
        from app.processors.to_pdf import convert_to_pdf
        src = tmp_path / "foo.txt"
        src.write_text("hello")
        with pytest.raises(ValueError):
            convert_to_pdf(src, tmp_path / "out.pdf")


class TestExcelToPdf:
    def test_xlsx_to_pdf(self, tmp_path):
        import openpyxl
        src = tmp_path / "data.xlsx"
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["Item", "Qty", "Price"])
        ws.append(["Steel", 10, 1500])
        wb.save(str(src))

        from app.processors.to_pdf import convert_to_pdf
        out = tmp_path / "out.pdf"
        result = convert_to_pdf(src, out)
        assert result.exists()

    def test_xls_to_pdf(self, tmp_path):
        try:
            import xlwt
        except ImportError:
            pytest.skip("xlwt not installed in this environment")
        src = tmp_path / "data.xls"
        wb = xlwt.Workbook()
        ws = wb.add_sheet("Sheet1")
        ws.write(0, 0, "Item")
        ws.write(0, 1, "Price")
        ws.write(1, 0, "Bolt")
        ws.write(1, 1, 10)
        wb.save(str(src))

        from app.processors.to_pdf import convert_to_pdf
        out = tmp_path / "out.pdf"
        result = convert_to_pdf(src, out)
        assert result.exists()
