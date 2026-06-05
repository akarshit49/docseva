#genai: Bill-to-Make converter — parse doc/docx with LLM, render as invoice PDF via fpdf2.
from __future__ import annotations

import json
import math
import re
from pathlib import Path

from fpdf import FPDF


# ---------------------------------------------------------------------------
# LLM prompt for structured extraction
# ---------------------------------------------------------------------------
_SYSTEM_PROMPT = """\
You are a billing data extractor. Extract structured data from text taken from a
"Bill to Make" Word document (which may contain multiple tables / sections) and return
ONLY a single valid JSON object.

Schema (fill every field):
{
  "bill_to": {
    "name": "customer / institution name",
    "address": "full postal address (use \\n for internal line breaks)",
    "gstin": "GSTIN value or 'NA'",
    "state_code": "2-digit state GST code as string (e.g. '09')",
    "state_name": "state name"
  },
  "ship_to": {
    "name": "delivery recipient name (same as bill_to if no separate delivery)",
    "address": "delivery address (same as bill_to if no separate delivery)",
    "gstin": "GSTIN value or 'NA'",
    "state_code": "2-digit state GST code as string",
    "state_name": "state name"
  },
  "items": [
    {
      "sno": "sequential number across ALL tables e.g. '1', '2', '3' ...",
      "name": "item description — clean text, remove HSN parentheticals",
      "hsn": "HSN or SAC code string, or '' if not present",
      "unit_cost": 0.0,
      "amount": 0.0,
      "gst_rate": 18
    }
  ],
  "gst_rate": 18
}

If the document mentions different GST rates per item (e.g. 5%, 12%, 18%, 28%),
populate each item's "gst_rate" individually. If a single rate applies to all
items, set the top-level "gst_rate" only and set each item's "gst_rate" to the
same value.

Critical rules:
- The document may have MULTIPLE tables, each restarting row numbers at 1. Treat ALL tables as one
  continuous item list and assign globally sequential sno values (1, 2, 3, ...).
- Skip any row that has no product name or no amount (e.g. header rows, blank rows, separator rows).
- Skip any row whose amount is exactly 0 — those are empty placeholder rows.
- Extract HSN/SAC code from text like "(HSN 9023)" or "(SAC 998719)" in item names; remove that
  parenthetical from the name. If HSN value is "NA" or not present, set "hsn" to "".
- QTY is NOT needed — it will be calculated from amount/unit_cost by the system.
- If a "Delivered to" address exists, use it as ship_to; otherwise ship_to = bill_to.
- State codes: Uttar Pradesh="09", Bihar="10", Uttarakhand="05", Delhi="07", Maharashtra="27".
- DO NOT include subtotal/gst_amount/total — those are calculated by the system.
- Return valid JSON only — no markdown fences, no extra text.\
"""


def _clean_bill_text(text: str) -> str:
    """
    Pre-process extracted document text before sending to LLM.
    Removes DOCX page-break markers and excessive whitespace.
    """
    # Remove page-break markers like "-- 1 of 9 --", "- 2 of 9 -"
    text = re.sub(r'-{1,3}\s*\d+\s*of\s*\d+\s*-{1,3}', ' ', text)
    # Collapse multiple blank lines into one
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Remove lines that are purely whitespace
    lines = [ln for ln in text.splitlines() if ln.strip()]
    return "\n".join(lines)


def parse_bill_doc_text(api_key: str, model: str, text: str) -> dict:
    """
    Call OpenAI to extract structured billing data from raw doc text.
    Handles multi-table documents with restarted row numbers.
    Returns a dict matching the schema in _SYSTEM_PROMPT.
    """
    from openai import OpenAI
    client = OpenAI(api_key=api_key)

    cleaned = _clean_bill_text(text)

    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": f"Extract from this document text:\n\n{cleaned[:14000]}"},
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )
    raw = resp.choices[0].message.content
    data = json.loads(raw)
    return _normalize_bill_data(data)


def _normalize_bill_data(data: dict) -> dict:
    """
    Filter / re-sequence items and compute server-side totals.
    Supports per-item gst_rate (KI-04). Falls back to the top-level rate.
    """
    items = data.get("items", [])
    items = [
        it for it in items
        if it.get("name", "").strip() and float(it.get("amount", 0)) > 0
    ]
    for idx, it in enumerate(items, 1):
        it["sno"] = str(idx)

    default_rate = float(data.get("gst_rate", 18))
    for it in items:
        try:
            it["gst_rate"] = float(it.get("gst_rate", default_rate))
        except (TypeError, ValueError):
            it["gst_rate"] = default_rate

    data["items"] = items

    subtotal = sum(float(it.get("amount", 0)) for it in items)
    rate_buckets: dict[float, float] = {}
    for it in items:
        rate = float(it.get("gst_rate", default_rate))
        rate_buckets[rate] = rate_buckets.get(rate, 0.0) + float(it.get("amount", 0))

    gst_breakdown = [
        {"rate": rate, "taxable": round(amt, 2), "tax": round(amt * rate / 100, 2)}
        for rate, amt in sorted(rate_buckets.items())
    ]
    gst_amount = round(sum(b["tax"] for b in gst_breakdown), 2)

    data["subtotal"] = round(subtotal, 2)
    data["gst_amount"] = gst_amount
    data["gst_breakdown"] = gst_breakdown
    data["total"] = round(subtotal + gst_amount, 2)
    return data


# ---------------------------------------------------------------------------
# PDF generation
# ---------------------------------------------------------------------------

def generate_bill_pdf(
    data: dict,
    bill_number: str,
    bill_date: str,
    output_path: Path,
    company_info: dict,
    logo_path: Path | None = None,
) -> Path:
    """
    Render a professional invoice PDF from the parsed bill data.

    company_info: built from the user's saved company profile (never hardcoded).
    logo_path:    optional local path to the company logo. If provided and the
                  file exists, it is drawn in the header (KI-09).

    Always recomputes totals from items so the summary is never 0 and supports
    a per-item gst_rate breakdown (KI-04).
    """
    data = _normalize_bill_data(data)
    gst_rate = float(data.get("gst_rate", 18))

    pdf = _InvoicePDF()
    pdf.set_margins(10, 10, 10)
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    _draw_header(pdf, company_info, logo_path)
    _draw_invoice_info(pdf, bill_number, bill_date)
    _draw_addresses(pdf, data)
    _draw_items_table(pdf, data["items"], gst_rate)
    _draw_summary(pdf, data)
    _draw_footer(pdf, company_info)

    pdf.output(str(output_path))
    return output_path


# ---------------------------------------------------------------------------
# PDF section helpers
# ---------------------------------------------------------------------------

class _InvoicePDF(FPDF):
    pass


_PW = 190  # usable page width in mm (A4 210 – 2×10 margins)


def _build_company_info(company_profile: dict) -> dict:
    """Extract and normalise company info from a CompanyProfile dict."""
    addr_parts = [
        company_profile.get("address") or "",
        company_profile.get("city") or "",
        company_profile.get("state") or "",
        company_profile.get("pincode") or "",
    ]
    address = ", ".join(p for p in addr_parts if p)

    return {
        "name": (company_profile.get("display_name") or "").upper(),
        "address": address,
        "gstin": company_profile.get("gstin") or "",
        "pan": company_profile.get("pan") or "",
        "phone": company_profile.get("phone") or "",
        "bank_name": company_profile.get("bank_name") or "",
        "bank_account": company_profile.get("bank_account") or "",
        "bank_ifsc": company_profile.get("bank_ifsc") or "",
    }


def _draw_header(pdf: _InvoicePDF, ci: dict, logo_path: Path | None = None) -> None:
    if logo_path is not None and Path(logo_path).exists():
        try:
            pdf.image(str(logo_path), x=10, y=8, w=22, h=22)
        except Exception:
            pass

    pdf.set_font("Helvetica", "B", 18)
    _cell(pdf, _PW, 10, ci["name"] or "YOUR COMPANY NAME", align="C", ln=True)

    pdf.set_font("Helvetica", "", 8)
    if ci["address"]:
        _cell(pdf, _PW, 5, ci["address"], align="C", ln=True)

    meta_parts = []
    if ci["gstin"]:
        meta_parts.append(f"GSTIN: {ci['gstin']}")
    if ci["pan"]:
        meta_parts.append(f"PAN: {ci['pan']}")
    if ci["phone"]:
        meta_parts.append(f"Ph: {ci['phone']}")
    if meta_parts:
        _cell(pdf, _PW, 5, "  |  ".join(meta_parts), align="C", ln=True)

    pdf.set_draw_color(0, 0, 0)
    pdf.line(pdf.l_margin, pdf.get_y() + 1, pdf.l_margin + _PW, pdf.get_y() + 1)
    pdf.ln(4)


def _draw_invoice_info(pdf: _InvoicePDF, bill_number: str, bill_date: str) -> None:
    half = _PW / 2
    pdf.set_font("Helvetica", "B", 11)
    _cell(pdf, half, 8, f"INVOICE :- {bill_number}")
    _cell(pdf, half, 8, f"Dated :- {bill_date}", align="R", ln=True)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.l_margin + _PW, pdf.get_y())
    pdf.ln(3)


def _draw_addresses(pdf: _InvoicePDF, data: dict) -> None:
    half = _PW / 2
    bt = data.get("bill_to", {})
    st = data.get("ship_to", bt)

    start_y = pdf.get_y()
    left_x = pdf.l_margin
    right_x = pdf.l_margin + half + 2

    # ---- Left column: Bill to ----
    pdf.set_xy(left_x, start_y)
    pdf.set_font("Helvetica", "B", 9)
    _cell(pdf, half - 2, 6, "Bill to:", ln=True)
    pdf.set_font("Helvetica", "B", 9)
    _cell(pdf, half - 2, 5, _s(bt.get("name", "")), ln=True)
    pdf.set_font("Helvetica", "", 8)
    for line in _s(bt.get("address", "")).split("\n"):
        if line.strip():
            _cell(pdf, half - 2, 5, line.strip(), ln=True)
    _cell(pdf, half - 2, 5, f"GSTIN : {_s(bt.get('gstin', 'NA'))}", ln=True)
    _cell(pdf, half - 2, 5,
          f"Place of Supply: {_s(bt.get('state_name', ''))} ({_s(bt.get('state_code', ''))})",
          ln=True)
    left_end_y = pdf.get_y()

    # ---- Right column: Ship to ----
    pdf.set_xy(right_x, start_y)
    pdf.set_font("Helvetica", "B", 9)
    _cell(pdf, half - 2, 6, "Ship to:", ln=True)
    pdf.set_xy(right_x, pdf.get_y())
    pdf.set_font("Helvetica", "B", 9)
    _cell(pdf, half - 2, 5, _s(st.get("name", "")), ln=True)
    pdf.set_xy(right_x, pdf.get_y())
    pdf.set_font("Helvetica", "", 8)
    for line in _s(st.get("address", "")).split("\n"):
        if line.strip():
            pdf.set_x(right_x)
            _cell(pdf, half - 2, 5, line.strip(), ln=True)
    pdf.set_x(right_x)
    _cell(pdf, half - 2, 5, f"GSTIN : {_s(st.get('gstin', 'NA'))}", ln=True)
    pdf.set_x(right_x)
    _cell(pdf, half - 2, 5,
          f"Place of Supply: {_s(st.get('state_name', ''))} ({_s(st.get('state_code', ''))})",
          ln=True)
    right_end_y = pdf.get_y()

    pdf.set_y(max(left_end_y, right_end_y) + 3)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.l_margin + _PW, pdf.get_y())
    pdf.ln(3)


def _draw_items_table(pdf: _InvoicePDF, items: list[dict], gst_rate: float) -> None:
    # Detect multi-rate scenario to switch the GST header label.
    rates = {float(it.get("gst_rate", gst_rate)) for it in items} if items else {gst_rate}
    is_multi_rate = len(rates) > 1
    gst_label = "GST\n(rate)" if is_multi_rate else f"GST\n({_fmt_rate(gst_rate)}%)"

    cw = [12, 66, 20, 12, 25, 25, 30]
    hdrs = ["S.No.", "PRODUCT / SERVICE NAME", "HSN/SAC", "QTY",
            "PER UNIT\nCOST RATE", gst_label, "AMOUNT\n(Rs.)"]
    row_h = 7
    hdr_h = 8

    pdf.set_font("Helvetica", "B", 8)
    for i, hdr in enumerate(hdrs):
        lines = hdr.split("\n")
        if len(lines) == 2:
            x, y = pdf.get_x(), pdf.get_y()
            pdf.rect(x, y, cw[i], hdr_h)
            pdf.set_font("Helvetica", "B", 7)
            pdf.set_xy(x, y + 0.5)
            pdf.cell(cw[i], 3.5, _s(lines[0]), align="C")
            pdf.set_xy(x, y + 4)
            pdf.cell(cw[i], 3.5, _s(lines[1]), align="C")
            pdf.set_xy(x + cw[i], y)
        else:
            pdf.set_font("Helvetica", "B", 8)
            pdf.cell(cw[i], hdr_h, _s(hdr), border=1, align="C")
    pdf.ln(hdr_h)

    pdf.set_font("Helvetica", "", 8)
    row_subtotal = row_gst = row_total = 0.0

    for item in items:
        unit_cost = float(item.get("unit_cost", 0))
        amount = float(item.get("amount", 0))
        if amount == 0:
            continue  # skip zero-amount rows entirely
        qty = _qty(unit_cost, amount)
        item_rate = float(item.get("gst_rate", gst_rate))
        gst_amt = round(amount * item_rate / 100, 2)
        line_total = round(amount + gst_amt, 2)

        row_subtotal += amount
        row_gst += gst_amt
        row_total += line_total

        name_lines = _wrap(_s(item.get("name", "")), 34)
        line_h = 5
        this_h = max(row_h, len(name_lines) * line_h + 2)

        # Page-break guard: if the row doesn't fit, start a new page and re-draw header
        if pdf.get_y() + this_h > pdf.page_break_trigger:
            pdf.add_page()
            pdf.set_font("Helvetica", "B", 8)
            for i, hdr in enumerate(hdrs):
                sub = hdr.split("\n")
                if len(sub) == 2:
                    x, y = pdf.get_x(), pdf.get_y()
                    pdf.rect(x, y, cw[i], hdr_h)
                    pdf.set_font("Helvetica", "B", 7)
                    pdf.set_xy(x, y + 0.5)
                    pdf.cell(cw[i], 3.5, _s(sub[0]), align="C")
                    pdf.set_xy(x, y + 4)
                    pdf.cell(cw[i], 3.5, _s(sub[1]), align="C")
                    pdf.set_xy(x + cw[i], y)
                else:
                    pdf.set_font("Helvetica", "B", 8)
                    pdf.cell(cw[i], hdr_h, _s(hdr), border=1, align="C")
            pdf.ln(hdr_h)
            pdf.set_font("Helvetica", "", 8)

        y_start = pdf.get_y()

        pdf.cell(cw[0], this_h, _s(item.get("sno", "")), border=1, align="C")

        x_name = pdf.get_x()
        pdf.rect(x_name, y_start, cw[1], this_h)
        for li, nl in enumerate(name_lines):
            pdf.set_xy(x_name, y_start + 1 + li * line_h)
            pdf.cell(cw[1], line_h, nl)
        pdf.set_xy(x_name + cw[1], y_start)

        pdf.cell(cw[2], this_h, _s(item.get("hsn", "")), border=1, align="C")
        pdf.cell(cw[3], this_h, str(qty), border=1, align="C")
        pdf.cell(cw[4], this_h, _fmt(unit_cost), border=1, align="R")
        gst_cell = (
            f"{_fmt(gst_amt)} ({_fmt_rate(item_rate)}%)"
            if is_multi_rate else _fmt(gst_amt)
        )
        pdf.cell(cw[5], this_h, gst_cell, border=1, align="R")
        pdf.cell(cw[6], this_h, _fmt(line_total), border=1, align="R")
        pdf.ln(this_h)

    pdf.set_font("Helvetica", "B", 8)
    pdf.cell(sum(cw[:4]), row_h, "TOTAL", border=1, align="C")
    pdf.cell(cw[4], row_h, _fmt(row_subtotal), border=1, align="R")
    pdf.cell(cw[5], row_h, _fmt(row_gst), border=1, align="R")
    pdf.cell(cw[6], row_h, _fmt(row_total), border=1, align="R")
    pdf.ln(row_h + 3)


def _draw_summary(pdf: _InvoicePDF, data: dict) -> None:
    subtotal = float(data.get("subtotal", 0))
    gst_amount = float(data.get("gst_amount", 0))
    total = float(data.get("total", 0))
    breakdown = data.get("gst_breakdown") or []

    lw = 90
    vw = 40
    rh = 7

    def summary_row(label: str, value: str, bold: bool = False) -> None:
        pdf.set_font("Helvetica", "B" if bold else "", 9)
        pdf.set_x(pdf.l_margin + _PW - lw - vw)
        pdf.cell(lw, rh, _s(label), border="B")
        pdf.cell(vw, rh, _s(value), border="B", align="R", ln=True)

    summary_row("TOTAL TAXABLE BEFORE TAX", f"Rs. {_fmt_ind(subtotal)}")
    #genai: KI fix — drop GST-jurisdiction labels (IGST/CGST/SGST) in favour of
    #       a generic "Total Tax" label. Different rates appear as separate
    #       "Tax @ X%" lines so the breakdown stays informative without
    #       implying a specific tax type.
    if len(breakdown) > 1:
        for entry in breakdown:
            rate = entry.get("rate", 0)
            tax = entry.get("tax", 0)
            taxable = entry.get("taxable", 0)
            label = f"Tax @ {_fmt_rate(rate)}% on Rs. {_fmt_ind(taxable)}"
            summary_row(label, f"Rs. {_fmt_ind(tax)}")
        summary_row("TOTAL TAX", f"Rs. {_fmt_ind(gst_amount)}", bold=True)
    else:
        rate = breakdown[0]["rate"] if breakdown else float(data.get("gst_rate", 18))
        summary_row(f"TOTAL TAX @ {_fmt_rate(rate)}%", f"Rs. {_fmt_ind(gst_amount)}")
    summary_row("TOTAL TAXABLE AFTER TAX", f"Rs. {_fmt_ind(total)}")
    summary_row("TOTAL AMOUNT", f"Rs. {_fmt_ind(total)}")
    summary_row("AMOUNT DUE", f"Rs. {_fmt_ind(total)}", bold=True)

    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 9)
    words = _amount_in_words(total)
    pdf.multi_cell(_PW, 6, _s(f"Total: {words}"), border=1)
    pdf.ln(5)


def _draw_footer(pdf: _InvoicePDF, ci: dict) -> None:
    half = _PW / 2
    start_y = pdf.get_y()

    pdf.set_font("Helvetica", "B", 9)
    _cell(pdf, half, 6, "Bank Details :-", ln=True)
    pdf.set_font("Helvetica", "", 8)

    if ci["bank_name"] or ci["bank_account"]:
        bank_line = ci["bank_name"]
        if ci["bank_account"]:
            bank_line += f" A/c - {ci['bank_account']}" if bank_line else f"A/c - {ci['bank_account']}"
        _cell(pdf, half, 5, bank_line, ln=True)
    else:
        _cell(pdf, half, 5, "(Bank details not set — update via /settings)", ln=True)

    if ci["bank_ifsc"]:
        _cell(pdf, half, 5, f"IFSC Code :- {ci['bank_ifsc']}", ln=True)

    right_x = pdf.l_margin + half + 2
    pdf.set_xy(right_x, start_y)
    pdf.set_font("Helvetica", "", 8)
    pdf.cell(half - 2, 5, "")
    pdf.ln(16)
    pdf.set_x(right_x)
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(half - 2, 6, "AUTHORIZED SIGNATORY", align="C")
    pdf.ln(8)


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _cell(pdf: FPDF, w: float, h: float, text: str,
          align: str = "L", ln: bool = False, **kw) -> None:
    pdf.cell(w, h, _s(text), align=align, new_x="LMARGIN" if ln else "RIGHT", new_y="NEXT" if ln else "TOP", **kw)


def _s(text: object) -> str:
    """Latin-1 safe string for fpdf2 core fonts."""
    return str(text).encode("latin-1", errors="replace").decode("latin-1")


def _fmt(val: float) -> str:
    return f"{val:,.2f}"


def _fmt_rate(rate: float) -> str:
    """Format a GST rate: 18 -> '18', 12.5 -> '12.5'."""
    if rate == int(rate):
        return str(int(rate))
    return f"{rate:.1f}"


def _fmt_ind(val: float) -> str:
    """Indian-style number formatting: commas at thousands and lakhs."""
    rupees = int(val)
    paise = round((val - rupees) * 100)
    s = str(rupees)
    if len(s) > 3:
        s = s[:-3] + "," + s[-3:]
    if len(s) > 6:
        s = s[:-6] + "," + s[-6:]
    return f"{s}.{paise:02d}"


def _qty(unit_cost: float, amount: float) -> int | str:
    if unit_cost <= 0:
        return 1
    q = amount / unit_cost
    if abs(q - round(q)) < 0.01:
        return int(round(q))
    return f"{q:.2f}"


def _wrap(text: str, max_chars: int) -> list[str]:
    """Word-wrap text into lines of at most max_chars characters."""
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = (current + " " + word).strip()
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]


# ---------------------------------------------------------------------------
# Number to words (Indian currency)
# ---------------------------------------------------------------------------

_ONES = [
    "", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
    "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
    "Seventeen", "Eighteen", "Nineteen",
]
_TENS = ["", "", "Twenty", "Thirty", "Forty", "Fifty",
         "Sixty", "Seventy", "Eighty", "Ninety"]


def _n2w(n: int) -> str:
    if n == 0:
        return ""
    if n < 20:
        return _ONES[n]
    if n < 100:
        return _TENS[n // 10] + (" " + _ONES[n % 10] if n % 10 else "")
    if n < 1_000:
        rest = _n2w(n % 100)
        return _ONES[n // 100] + " Hundred" + (" " + rest if rest else "")
    if n < 1_00_000:
        rest = _n2w(n % 1_000)
        return _n2w(n // 1_000) + " Thousand" + (" " + rest if rest else "")
    if n < 1_00_00_000:
        rest = _n2w(n % 1_00_000)
        return _n2w(n // 1_00_000) + " Lakh" + (" " + rest if rest else "")
    rest = _n2w(n % 1_00_00_000)
    return _n2w(n // 1_00_00_000) + " Crore" + (" " + rest if rest else "")


def _amount_in_words(amount: float) -> str:
    rupees = int(amount)
    paise = round((amount - rupees) * 100)
    text = _n2w(rupees) or "Zero"
    if paise:
        text += " and " + _n2w(paise) + " Paise"
    return text + " Only"


# ---------------------------------------------------------------------------
# High-level entry point — used by the bot
# ---------------------------------------------------------------------------

def generate_bill(
    input_path: Path,
    output_path: Path,
    bill_number: str,
    bill_date: str,
    company_profile: dict | None = None,
) -> Path:
    """
    Parse input doc/docx, build company info from user's saved profile, render invoice PDF.
    company_profile: dict from CompanyProfile.as_dict() — all fields come from the user's account.
    """
    from app.processors.extractors import extract_text
    from app.config import settings as bot_settings

    company_info = _build_company_info(company_profile or {})
    text = extract_text(input_path)
    data = parse_bill_doc_text(bot_settings.openai_api_key, bot_settings.openai_model, text)
    return generate_bill_pdf(data, bill_number, bill_date, output_path, company_info)
