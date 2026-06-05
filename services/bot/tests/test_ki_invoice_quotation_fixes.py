#genai: Regression tests for the four invoice/quotation issues reported after
# the WS-3 (create-from-scratch) rollout:
#  1. Per-item GST under "Customize"; rename IGST → Total Tax; editable invoice #
#  2. Quotation: terms below table (not inside), editable ref #, no duplicate
#     company name, GST-applicability note included.
#  3. bill_to_make summary uses "Total Tax" instead of "IGST".
#  4. Sister-quotation caption sent as plain text so DB filenames with
#     underscores can't break Telegram Markdown parsing.
from __future__ import annotations

import inspect
import zipfile
from pathlib import Path

import pytest


# ─── 1A: per-item GST parser ─────────────────────────────────────────────────

def test_parse_per_item_gst_assigns_rates_and_reports_missing():
    from app.processors.create_invoice import parse_per_item_gst

    items = [
        {"name": "A", "qty": 1, "unit_cost": 100, "amount": 100, "hsn": ""},
        {"name": "B", "qty": 1, "unit_cost": 200, "amount": 200, "hsn": ""},
        {"name": "C", "qty": 1, "unit_cost": 50, "amount": 50, "hsn": ""},
    ]
    updated, missing, errors = parse_per_item_gst("1: 5\n2: 12", items)
    assert errors == []
    assert updated[0]["gst_rate"] == 5 and updated[0]["_gst_explicit"] is True
    assert updated[1]["gst_rate"] == 12 and updated[1]["_gst_explicit"] is True
    assert "gst_rate" not in updated[2] or not updated[2].get("_gst_explicit")
    assert missing == [3]


def test_parse_per_item_gst_rejects_bad_input():
    from app.processors.create_invoice import parse_per_item_gst
    items = [{"name": "A", "qty": 1, "unit_cost": 100, "amount": 100}]
    _, _, errors = parse_per_item_gst("1: 500\nfoo: 18\n5: 5", items)
    # 500 out of range, "foo" bad number, "5:" doesn't exist
    assert len(errors) == 3


def test_compute_totals_uses_per_item_rates():
    """Per-item rates must bucket correctly into the breakdown."""
    from app.processors.create_invoice import compute_totals

    items = [
        {"amount": 100, "gst_rate": 5},
        {"amount": 200, "gst_rate": 12},
        {"amount": 100, "gst_rate": 5},
    ]
    totals = compute_totals(items, gst_rate=18)
    rates = sorted([b["rate"] for b in totals["gst_breakdown"]])
    assert rates == [5, 12]
    bucket_5 = next(b for b in totals["gst_breakdown"] if b["rate"] == 5)
    assert bucket_5["taxable"] == 200  # two ₹100 items
    assert bucket_5["tax"] == 10
    assert totals["subtotal"] == 400
    assert totals["gst_amount"] == 10 + 24  # 5% of 200 + 12% of 200


# ─── 1B / 3: IGST → Total Tax in bill_to_make ─────────────────────────────────

def test_bill_to_make_summary_says_total_tax_not_igst(tmp_path):
    """Generate a bill PDF, then assert the output text mentions Total Tax
    and not IGST/CGST/SGST anywhere."""
    from app.processors.bill_to_make import generate_bill_pdf
    import pdfplumber

    data = {
        "bill_to": {"name": "ABC", "address": "X", "gstin": "NA",
                    "state_code": "07", "state_name": "Delhi"},
        "ship_to": {"name": "ABC", "address": "X", "gstin": "NA",
                    "state_code": "07", "state_name": "Delhi"},
        "items": [
            {"sno": "1", "name": "Item-1", "hsn": "9999",
             "unit_cost": 1000, "amount": 1000, "gst_rate": 18},
            {"sno": "2", "name": "Item-2", "hsn": "9999",
             "unit_cost": 500, "amount": 500, "gst_rate": 5},
        ],
        "gst_rate": 18,
    }
    company_info = {
        "name": "BOOBOO TEES", "address": "Bengaluru", "gstin": "29ABCDE1234F1Z5",
        "pan": "", "phone": "", "bank_name": "", "bank_account": "", "bank_ifsc": "",
    }
    out = tmp_path / "bill.pdf"
    generate_bill_pdf(data, "INV-001", "01-06-2026", out, company_info, logo_path=None)
    assert out.exists()

    with pdfplumber.open(str(out)) as pdf:
        full_text = "\n".join((p.extract_text() or "") for p in pdf.pages).upper()

    assert "TOTAL TAX" in full_text
    assert "IGST" not in full_text
    assert "CGST" not in full_text
    assert "SGST" not in full_text


# ─── 1C: invoice keyboard exposes an Edit Invoice # button ───────────────────

def test_invoice_confirm_keyboard_has_edit_refno_button():
    from app.keyboards import invoice_confirm_keyboard
    kb = invoice_confirm_keyboard()
    callbacks = [b.callback_data for row in kb.inline_keyboard for b in row]
    assert "create:edit_refno" in callbacks


def test_quotation_confirm_keyboard_has_edit_refno_button():
    from app.keyboards import quotation_confirm_keyboard
    kb = quotation_confirm_keyboard()
    callbacks = [b.callback_data for row in kb.inline_keyboard for b in row]
    assert "create:edit_refno_q" in callbacks


def test_gst_keyboard_offers_per_item():
    from app.keyboards import gst_rate_keyboard
    kb = gst_rate_keyboard()
    callbacks = [b.callback_data for row in kb.inline_keyboard for b in row]
    assert "create:gst:per_item" in callbacks


# ─── 2A: quotation terms render OUTSIDE the items table ──────────────────────

def test_render_quote_terms_below_table_not_inside(tmp_path):
    """Build a QuoteDocument with terms_list and confirm the bullets appear
    in the document body but NOT inside the items table."""
    from app.processors.formats import TargetFormat
    from app.processors.models import QuoteDocument, QuoteItem, QuoteSection
    from app.processors.renderers import render

    quote = QuoteDocument(
        recipient_name="Acme",
        recipient_address_lines=["Bangalore"],
        subject="Quotation",
        ref_no="QT-0099",
        date="01/06/2026",
        valid_until="01/07/2026",
        sections=[QuoteSection(name="Items", items=[
            QuoteItem(sno="1", description="Rubber", qty="1", unit_price=300, total=300),
        ])],
        terms_list=[
            "Validity: 30 days",
            "Payment: 100% advance",
            "Delivery: Within 7 days",
            "GST will be applicable at the time of invoice as per the prevailing rates.",
        ],
    )
    out = tmp_path / "q.docx"
    render(quote, TargetFormat.SV_ENTERPRISES, out, {"display_name": "BooBoo Tees"})
    assert out.exists()

    with zipfile.ZipFile(str(out)) as zf:
        doc_xml = zf.read("word/document.xml").decode("utf-8")

    # All user-supplied terms must be present in the body
    for t in ["Validity: 30 days", "Payment: 100% advance",
              "Delivery: Within 7 days",
              "GST will be applicable at the time of invoice"]:
        assert t in doc_xml, f"Expected term in DOCX body: {t}"

    # The items table must NOT contain a "Terms" section header row
    assert ">Terms<" not in doc_xml
    # And the terms themselves must not show up as table rows with "₹ 0.00"
    # placeholders (the old broken behaviour).
    assert ">₹ 0.00<" not in doc_xml


# ─── 2B: build_quotation_document no longer doubles the recipient name ───────

def test_build_quotation_document_does_not_double_recipient_name():
    from app.processors.create_invoice import build_quotation_document

    bill_to = {
        "name": "Akarshit enterprises",
        "address": "Akarshit enterprises, Bangalore",  # name accidentally inside addr
        "gstin": "",
        "state": "",
    }
    quote = build_quotation_document(
        bill_to,
        items=[{"name": "X", "qty": 1, "unit_cost": 100, "amount": 100}],
        ref_no="QT-1",
        date_str="01/06/2026",
        valid_until="01/07/2026",
    )
    name_count = sum(
        1 for line in quote.recipient_address_lines
        if line.strip().lower() == "akarshit enterprises"
    )
    assert name_count == 0, (
        "Recipient name should not appear inside address_lines (it's already "
        "the heading); got address_lines=" + repr(quote.recipient_address_lines)
    )


# ─── 4: sister-quotation caption is plain text (no parse_mode) ───────────────

def test_sister_quotation_reply_caption_has_no_parse_mode():
    """Read the source of _convert_with_format_id and assert the reply_document
    call inside it does not pass parse_mode='Markdown' for the caption — a
    regression that broke /history-style underscore filenames."""
    from app import bot

    src = inspect.getsource(bot._convert_with_format_id)
    # Find the reply_document(...) block
    start = src.index("reply_document(")
    end = src.index(")", start)
    block = src[start:end]
    # The fix: caption is plain text, no parse_mode kwarg on the call
    assert "parse_mode" not in block, (
        "Sister-quotation reply_document caption must not use Markdown parse_mode; "
        "DB-stored filenames frequently contain underscores which break parsing."
    )
