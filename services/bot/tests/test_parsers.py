"""
#genai: Unit tests for pure-function parsers — date parsing, blank detection, bill text cleaning.
No external dependencies required (no network, no files, no LLM).
"""
from __future__ import annotations

import pytest


# ── _parse_date tests (imported from app.utils) ───────────────────────────────

class TestParseDate:
    """TC-DATE-*: Validate date string parsing across many formats."""

    @pytest.fixture(autouse=True)
    def _import(self):
        from app.utils import parse_date
        self.parse = parse_date

    def test_dd_mm_yyyy_dash(self):
        assert self.parse("31-05-2024") == "31-05-2024"

    def test_dd_mm_yyyy_slash(self):
        assert self.parse("31/05/2024") == "31-05-2024"

    def test_dd_mm_yyyy_dot(self):
        assert self.parse("31.05.2024") == "31-05-2024"

    def test_yyyy_mm_dd(self):
        assert self.parse("2024-05-31") == "31-05-2024"

    def test_dd_mon_yyyy(self):
        assert self.parse("31 May 2024") == "31-05-2024"

    def test_dd_mon_yyyy_abbrev(self):
        assert self.parse("31 May 2024") == "31-05-2024"

    def test_short_year_dash(self):
        assert self.parse("31-05-24") == "31-05-2024"

    def test_numeric_only_is_rejected(self):
        assert self.parse("3454") is None

    def test_garbage_string_is_rejected(self):
        assert self.parse("not-a-date") is None

    def test_empty_string_is_rejected(self):
        assert self.parse("") is None

    def test_implausible_year_is_rejected(self):
        assert self.parse("31-05-1999") is None

    def test_implausible_future_year_is_rejected(self):
        assert self.parse("31-05-2100") is None

    def test_single_digit_day(self):
        assert self.parse("1-1-2025") == "01-01-2025"

    def test_whitespace_trimmed(self):
        assert self.parse("  31-05-2024  ") == "31-05-2024"


# ── _is_blank tests (imported from app.utils) ─────────────────────────────────

class TestIsBlank:
    """TC-BLANK-*: Values that should be treated as empty/missing."""

    @pytest.fixture(autouse=True)
    def _import(self):
        from app.utils import is_blank
        self.blank = is_blank

    def test_empty_string(self):
        assert self.blank("") is True

    def test_na_lower(self):
        assert self.blank("na") is True

    def test_na_upper(self):
        assert self.blank("NA") is True

    def test_n_slash_a(self):
        assert self.blank("N/A") is True

    def test_none_string(self):
        assert self.blank("none") is True

    def test_nil(self):
        assert self.blank("nil") is True

    def test_dash(self):
        assert self.blank("-") is True

    def test_not_available(self):
        assert self.blank("not available") is True

    def test_valid_name_not_blank(self):
        assert self.blank("ABC Corp") is False

    def test_valid_address_not_blank(self):
        assert self.blank("45 MG Road, Delhi") is False

    def test_whitespace_only(self):
        assert self.blank("   ") is True


# ── Bill text cleaning tests ──────────────────────────────────────────────────

class TestCleanBillText:
    """TC-CLEAN-*: Page-break markers and blank lines are stripped."""

    @pytest.fixture(autouse=True)
    def _import(self):
        from app.processors.bill_to_make import _clean_bill_text  # noqa: PLC0415
        self.clean = _clean_bill_text

    def test_removes_page_markers_with_dashes(self):
        text = "Item 1\n-- 1 of 3 --\nItem 2"
        result = self.clean(text)
        assert "1 of 3" not in result
        assert "Item 1" in result
        assert "Item 2" in result

    def test_removes_page_markers_single_dash(self):
        text = "Row A\n- 2 of 5 -\nRow B"
        result = self.clean(text)
        assert "2 of 5" not in result

    def test_collapses_excess_blank_lines(self):
        text = "Line A\n\n\n\n\nLine B"
        result = self.clean(text)
        assert result.count("\n\n\n") == 0

    def test_preserves_content(self):
        text = "Steel Bars\n7214\n1000 kg\n68000"
        result = self.clean(text)
        assert "Steel Bars" in result
        assert "68000" in result


# ── parse_billto_block (KI-11) ────────────────────────────────────────────────

class TestParseBillToBlock:
    """TC-BTBLOCK-*: case- and whitespace-tolerant BillTo parsing."""

    @pytest.fixture(autouse=True)
    def _import(self):
        from app.utils import parse_billto_block
        self.parse = parse_billto_block

    def test_lowercase_keys(self):
        text = "name: ABC\naddress: 45 MG Rd\ngstin: 07ABCDE\nstate: Delhi"
        d = self.parse(text)
        assert d["name"] == "ABC"
        assert d["address"] == "45 MG Rd"
        assert d["gstin"] == "07ABCDE"
        assert d["state"] == "Delhi"

    def test_uppercase_keys(self):
        text = "NAME: ABC\nADDRESS: 45 MG Rd"
        d = self.parse(text)
        assert d["name"] == "ABC"
        assert d["address"] == "45 MG Rd"

    def test_extra_whitespace_in_key(self):
        text = "Ship To  Name:    Carrier\nShip  to  address: Warehouse"
        d = self.parse(text)
        assert d["shipto_name"] == "Carrier"
        assert d["shipto_address"] == "Warehouse"

    def test_aliases(self):
        text = "Company: XYZ Pvt Ltd\nGST No: 27GSTIN"
        d = self.parse(text)
        assert d["name"] == "XYZ Pvt Ltd"
        assert d["gstin"] == "27GSTIN"

    def test_missing_fields_default_to_empty(self):
        d = self.parse("name: Solo")
        assert d["address"] == ""
        assert d["gstin"] == ""

    def test_empty_input(self):
        d = self.parse("")
        assert all(v == "" for v in d.values())


# ── format_history_date (KI-08) ───────────────────────────────────────────────

class TestFormatHistoryDate:
    """TC-HISTDATE-*: ISO timestamps formatted to friendly dates."""

    @pytest.fixture(autouse=True)
    def _import(self):
        from app.utils import format_history_date
        self.fmt = format_history_date

    def test_full_iso(self):
        assert self.fmt("2024-05-31T10:45:00+00:00") == "31 May 2024"

    def test_with_z_suffix(self):
        assert self.fmt("2024-12-25T00:00:00Z") == "25 Dec 2024"

    def test_date_only(self):
        assert self.fmt("2024-03-15") == "15 Mar 2024"

    def test_invalid_falls_back(self):
        assert self.fmt("not-a-date").startswith("not-a-da")

    def test_empty(self):
        assert self.fmt("") == ""


# ── chunk_text (KI-10) ────────────────────────────────────────────────────────

class TestChunkText:
    """TC-CHUNK-*: chunking semantics for GST validate."""

    @pytest.fixture(autouse=True)
    def _import(self):
        from app.utils import chunk_text
        self.chunk = chunk_text

    def test_short_text_one_chunk(self):
        assert self.chunk("Hello world") == ["Hello world"]

    def test_empty_returns_empty(self):
        assert self.chunk("") == []

    def test_long_text_splits(self):
        text = "x" * 20000
        chunks = self.chunk(text, max_chars=6000, overlap=200)
        assert len(chunks) >= 3
        # No chunk should exceed max_chars by a noticeable margin
        assert all(len(c) <= 6500 for c in chunks)

    def test_paragraph_boundary_preferred(self):
        body = ("para one. " * 200) + "\n\n" + ("para two. " * 200)
        chunks = self.chunk(body, max_chars=1500, overlap=50)
        # First chunk should end at or near the paragraph break
        assert chunks[0].endswith("\n\n") or "para two" in chunks[1]


# ── user_tmp_path (KI-15) ─────────────────────────────────────────────────────

class TestUserTmpPath:
    """TC-USERTMP-*: per-user paths isolate concurrent users."""

    @pytest.fixture(autouse=True)
    def _import(self):
        from app.utils import user_tmp_path
        self.utp = user_tmp_path

    def test_paths_are_isolated(self, tmp_path):
        p1 = self.utp(101, "report.pdf", root=tmp_path)
        p2 = self.utp(202, "report.pdf", root=tmp_path)
        assert p1 != p2
        assert "101" in str(p1.parent)
        assert "202" in str(p2.parent)

    def test_parent_dir_created(self, tmp_path):
        p = self.utp("abc", "doc.docx", root=tmp_path)
        assert p.parent.is_dir()

    def test_unsafe_chars_sanitised(self, tmp_path):
        p = self.utp("uid", "../../etc/passwd", root=tmp_path)
        assert "/etc/" not in str(p)
        assert ".." not in p.name

    def test_long_filename_truncated(self, tmp_path):
        long_name = "x" * 500 + ".pdf"
        p = self.utp("uid", long_name, root=tmp_path)
        assert len(p.name) <= 124


# ── is_file_size_ok (KI-06) ───────────────────────────────────────────────────

class TestFileSizeOk:
    """TC-SIZE-*: enforce the 15 MB upload limit."""

    @pytest.fixture(autouse=True)
    def _import(self):
        from app.utils import is_file_size_ok, MAX_UPLOAD_BYTES
        self.check = is_file_size_ok
        self.cap = MAX_UPLOAD_BYTES

    def test_none_passes(self):
        ok, msg = self.check(None)
        assert ok and msg == ""

    def test_small_file_passes(self):
        ok, msg = self.check(1024)
        assert ok

    def test_at_limit_passes(self):
        ok, _ = self.check(self.cap)
        assert ok

    def test_over_limit_rejected(self):
        ok, msg = self.check(self.cap + 1)
        assert not ok
        assert "too large" in msg.lower()
