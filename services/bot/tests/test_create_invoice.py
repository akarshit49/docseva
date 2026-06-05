"""
#genai: WS-3 — Tests for the Create-from-Scratch invoice/quotation flow.

Covers:
  * Pure parsers (parse_invoice_items, parse_hsn_response, parse_customer_block)
  * Total computation and amount-in-words
  * build_invoice_data shape (compatible with bill_to_make.generate_bill_pdf)
  * Full conversational flow happy path through cmd_create + button + text
  * Edge cases: zero-amount items, missing HSN, invalid number, "skip HSN"
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.asyncio


# ── Imports & helpers ────────────────────────────────────────────────────────

from app.processors.create_invoice import (
    amount_in_words,
    build_invoice_data,
    build_quotation_document,
    compute_totals,
    format_items_table,
    parse_customer_block,
    parse_hsn_response,
    parse_invoice_items,
)


def _make_update(user_id: int = 555, text: str = ""):
    update = MagicMock()
    update.effective_user.id = user_id
    update.message = MagicMock()
    update.message.text = text
    update.message.reply_text = AsyncMock()
    update.message.reply_document = AsyncMock()
    update.message.document = None
    update.callback_query = None
    return update


def _make_callback(user_id: int = 555, data: str = ""):
    update = MagicMock()
    update.effective_user.id = user_id
    query = MagicMock()
    query.answer = AsyncMock()
    query.data = data
    query.edit_message_text = AsyncMock()
    query.edit_message_reply_markup = AsyncMock()
    query.message = MagicMock()
    query.message.reply_text = AsyncMock()
    query.message.reply_document = AsyncMock()
    update.callback_query = query
    update.message = None
    return update


def _ctx():
    return MagicMock()


def _mock_auth(allowed: bool = True):
    async def _auth(update):
        return allowed
    return patch("app.bot._require_auth", side_effect=_auth)


# ── Pure parsers ─────────────────────────────────────────────────────────────

class TestParseInvoiceItems:
    def test_basic_three_items(self):
        text = (
            "Digital Thermometer | 2 | 4500 | 9025\n"
            "pH Meter | 1 | 12000 | 9027\n"
            "Calibration Service | 1 | 2000"
        )
        items, errors = parse_invoice_items(text)
        assert errors == []
        assert len(items) == 3
        assert items[0]["name"] == "Digital Thermometer"
        assert items[0]["qty"] == 2
        assert items[0]["unit_cost"] == 4500.0
        assert items[0]["amount"] == 9000.0
        assert items[0]["hsn"] == "9025"
        assert items[2]["hsn"] == ""

    def test_strips_currency_and_commas(self):
        text = "Widget | 3 | ₹1,250.50 | 9001"
        items, errors = parse_invoice_items(text)
        assert errors == []
        assert items[0]["unit_cost"] == 1250.50
        assert items[0]["amount"] == 3751.50

    def test_rejects_zero_qty(self):
        text = "Bad Item | 0 | 100\nGood Item | 2 | 50"
        items, errors = parse_invoice_items(text)
        assert len(items) == 1
        assert items[0]["name"] == "Good Item"
        assert len(errors) == 1
        assert "Qty and Price" in errors[0]

    def test_rejects_too_few_fields(self):
        text = "Just a name\nProper | 1 | 100"
        items, errors = parse_invoice_items(text)
        assert len(items) == 1
        assert len(errors) == 1
        assert "3 fields" in errors[0]

    def test_skips_blank_lines(self):
        text = "\n\nItem | 1 | 100\n   \n"
        items, errors = parse_invoice_items(text)
        assert len(items) == 1
        assert errors == []

    def test_invalid_number_treated_as_zero_and_rejected(self):
        text = "Item | abc | 100\nGood | 1 | 50"
        items, errors = parse_invoice_items(text)
        # qty=0 (default), so it's rejected by the >0 check
        assert len(items) == 1
        assert items[0]["name"] == "Good"


class TestParseHsnResponse:
    def test_applies_codes_to_missing_items(self):
        items = [
            {"name": "A", "qty": 1, "unit_cost": 100, "amount": 100, "hsn": ""},
            {"name": "B", "qty": 1, "unit_cost": 200, "amount": 200, "hsn": "9999"},
            {"name": "C", "qty": 1, "unit_cost": 300, "amount": 300, "hsn": ""},
        ]
        updated, missing = parse_hsn_response("1: 1111\n3: 3333", items)
        assert updated[0]["hsn"] == "1111"
        assert updated[1]["hsn"] == "9999"
        assert updated[2]["hsn"] == "3333"
        assert missing == []

    def test_partial_fill_returns_remaining_missing(self):
        items = [
            {"name": "A", "qty": 1, "unit_cost": 100, "amount": 100, "hsn": ""},
            {"name": "B", "qty": 1, "unit_cost": 200, "amount": 200, "hsn": ""},
        ]
        updated, missing = parse_hsn_response("1: 1234", items)
        assert updated[0]["hsn"] == "1234"
        assert missing == [2]

    def test_ignores_out_of_range_index(self):
        items = [{"name": "A", "qty": 1, "unit_cost": 100, "amount": 100, "hsn": ""}]
        updated, missing = parse_hsn_response("5: 9999\n1: 1111", items)
        assert updated[0]["hsn"] == "1111"
        assert missing == []

    def test_does_not_mutate_original(self):
        items = [{"name": "A", "qty": 1, "unit_cost": 100, "amount": 100, "hsn": ""}]
        original = items[0].copy()
        parse_hsn_response("1: 9999", items)
        assert items[0] == original


class TestParseCustomerBlock:
    def test_complete_block(self):
        text = (
            "Name: Roorkee Scientific\n"
            "Address: 12 Civil Lines, Roorkee\n"
            "GSTIN: 05AABCR1234A1Z5\n"
            "State: Uttarakhand"
        )
        parsed, missing = parse_customer_block(text)
        assert missing == []
        assert parsed["name"] == "Roorkee Scientific"
        assert parsed["address"] == "12 Civil Lines, Roorkee"
        assert parsed["gstin"] == "05AABCR1234A1Z5"

    def test_missing_name_reported(self):
        parsed, missing = parse_customer_block("Address: somewhere")
        assert "Name" in missing

    def test_missing_address_reported(self):
        parsed, missing = parse_customer_block("Name: ABC")
        assert "Address" in missing


# ── Totals & display helpers ─────────────────────────────────────────────────

class TestComputeTotals:
    def test_uniform_gst(self):
        items = [
            {"name": "A", "qty": 1, "unit_cost": 1000, "amount": 1000},
            {"name": "B", "qty": 2, "unit_cost": 500, "amount": 1000},
        ]
        totals = compute_totals(items, 18)
        assert totals["subtotal"] == 2000.0
        assert totals["gst_amount"] == 360.0
        assert totals["total"] == 2360.0
        assert len(totals["gst_breakdown"]) == 1
        assert totals["gst_breakdown"][0]["rate"] == 18

    def test_per_item_gst(self):
        items = [
            {"name": "A", "qty": 1, "unit_cost": 1000, "amount": 1000, "gst_rate": 5},
            {"name": "B", "qty": 1, "unit_cost": 1000, "amount": 1000, "gst_rate": 18},
        ]
        totals = compute_totals(items, 18)
        assert totals["subtotal"] == 2000.0
        # 1000*5% + 1000*18% = 50 + 180 = 230
        assert totals["gst_amount"] == 230.0
        assert totals["total"] == 2230.0
        assert len(totals["gst_breakdown"]) == 2


class TestAmountInWords:
    @pytest.mark.parametrize("amount,expected_contains", [
        (0, "Zero"),
        (1, "One"),
        (19, "Nineteen"),
        (123, "Hundred"),
        (1000, "Thousand"),
        (100000, "Lakh"),
        (10000000, "Crore"),
    ])
    def test_landmark_amounts(self, amount, expected_contains):
        assert expected_contains in amount_in_words(amount)

    def test_complex_amount(self):
        out = amount_in_words(2375425)
        assert "Lakh" in out
        assert "Thousand" in out
        assert out.startswith("Rupees")
        assert out.endswith("Only")


class TestFormatItemsTable:
    def test_empty_items_shows_placeholder(self):
        assert "no items" in format_items_table([]).lower()

    def test_includes_each_item_name(self):
        items = [
            {"name": "Widget A", "qty": 1, "unit_cost": 100, "amount": 100, "hsn": "1234"},
            {"name": "Gadget B", "qty": 2, "unit_cost": 200, "amount": 400, "hsn": ""},
        ]
        out = format_items_table(items)
        assert "Widget A" in out
        assert "Gadget B" in out
        assert "1,234" in out or "1234" in out


# ── build_invoice_data ───────────────────────────────────────────────────────

class TestBuildInvoiceData:
    def test_matches_bill_to_make_schema(self):
        items = [{"name": "X", "qty": 2, "unit_cost": 1500, "amount": 3000, "hsn": "9025"}]
        bill_to = {"name": "ABC", "address": "Delhi", "gstin": "07ABC", "state": "Delhi"}
        data = build_invoice_data(bill_to, items, 18.0)
        # bill_to keys match what _normalize_bill_data expects
        assert data["bill_to"]["name"] == "ABC"
        assert data["bill_to"]["state_name"] == "Delhi"
        assert data["ship_to"]["name"] == "ABC"  # falls back to bill_to
        assert len(data["items"]) == 1
        assert data["items"][0]["sno"] == "1"
        assert data["items"][0]["hsn"] == "9025"
        assert data["items"][0]["amount"] == 3000

    def test_renders_through_bill_to_make(self, tmp_path):
        """Real-renderer integration: confirm the structure works with generate_bill_pdf."""
        from app.processors.bill_to_make import generate_bill_pdf, _build_company_info
        items = [
            {"name": "Item A", "qty": 1, "unit_cost": 1000, "amount": 1000, "hsn": "9025"},
            {"name": "Item B", "qty": 2, "unit_cost": 500, "amount": 1000, "hsn": "9027"},
        ]
        bill_to = {
            "name": "Test Customer",
            "address": "12 Test Road",
            "gstin": "07TESTGSTIN1Z5",
            "state": "Delhi",
        }
        data = build_invoice_data(bill_to, items, 18.0)
        company = _build_company_info({"display_name": "DocSeva Test"})
        out = tmp_path / "test_invoice.pdf"
        generate_bill_pdf(data, "INV-0001", "31-05-2026", out, company)
        assert out.exists() and out.stat().st_size > 1000  # non-trivial PDF


# ── Quotation builder ────────────────────────────────────────────────────────

class TestBuildQuotationDocument:
    def test_constructs_quote_document(self):
        bill_to = {"name": "ABC", "address": "Delhi", "gstin": "07XYZ"}
        items = [
            {"name": "Service A", "qty": 1, "unit_cost": 5000, "amount": 5000, "hsn": ""},
        ]
        quote = build_quotation_document(bill_to, items, "QT-0001",
                                          "31/05/2026", "30/06/2026", subject="Project Quote")
        assert quote.ref_no == "QT-0001"
        assert quote.recipient_name == "ABC"
        assert quote.subject == "Project Quote"
        assert len(quote.sections) == 1
        assert quote.sections[0].items[0].description == "Service A"
        assert quote.sections[0].items[0].unit_price == 5000.0


# ── End-to-end conversational flow ───────────────────────────────────────────

class TestCreateInvoiceFlow:
    """High-level: walk through the entire happy path with mocked Telegram + API."""

    async def test_cmd_create_resets_session_and_shows_menu(self):
        from app.bot import cmd_create, store
        update = _make_update(user_id=777, text="/create")
        with _mock_auth():
            await cmd_create(update, _ctx())
        assert update.message.reply_text.called
        # The session is reset back to IDLE; create_menu_keyboard appears
        from app.session_store import BotState
        assert store.get("777").state == BotState.IDLE
        call_kwargs = update.message.reply_text.call_args
        assert "Create a New Document" in call_kwargs.args[0]

    async def test_create_invoice_button_advances_to_billto(self):
        from app.bot import handle_callback, store
        from app.session_store import BotState
        store.reset("888")
        update = _make_callback(user_id=888, data="create:invoice")
        await handle_callback(update, _ctx())
        assert store.get("888").state == BotState.CREATING_INVOICE_BILLTO

    async def test_billto_then_items_then_continue_to_hsn(self):
        from app.bot import handle_text, handle_callback, store
        from app.session_store import BotState
        store.reset("999")
        # 1) start invoice flow
        cb = _make_callback(user_id=999, data="create:invoice")
        await handle_callback(cb, _ctx())
        # 2) supply BillTo
        billto = _make_update(user_id=999, text=(
            "Name: Roorkee Scientific\nAddress: 12 Civil Lines\nGSTIN: 05AABCR1234A1Z5\nState: Uttarakhand"
        ))
        await handle_text(billto, _ctx())
        sess = store.get("999")
        assert sess.state == BotState.CREATING_INVOICE_ITEMS
        assert sess.pending_create_invoice["bill_to"]["name"] == "Roorkee Scientific"

        # 3) supply items (one without HSN to trigger HSN step)
        items = _make_update(user_id=999, text=(
            "Digital Thermometer | 2 | 4500 | 9025\n"
            "pH Meter | 1 | 12000 | 9027\n"
            "Calibration Service | 1 | 2000"
        ))
        await handle_text(items, _ctx())
        sess = store.get("999")
        assert sess.state == BotState.CREATING_INVOICE_ITEMS
        assert len(sess.pending_create_invoice["items"]) == 3

        # 4) tap Continue
        cont = _make_callback(user_id=999, data="create:continue")
        await handle_callback(cont, _ctx())
        # one item lacked HSN, so we should land in HSN state
        assert store.get("999").state == BotState.CREATING_INVOICE_HSN

    async def test_hsn_skip_jumps_to_gst(self):
        from app.bot import handle_callback, store
        from app.session_store import BotState
        store.reset("aaa")
        # bootstrap session
        sess = store.get("aaa")
        sess.pending_create_invoice = {
            "bill_to": {"name": "X", "address": "Y"},
            "items": [{"name": "A", "qty": 1, "unit_cost": 100, "amount": 100, "hsn": ""}],
            "gst_rate": 18.0, "bill_number": "", "bill_date": "",
        }
        sess.state = BotState.CREATING_INVOICE_HSN
        skip = _make_callback(user_id="aaa", data="create:hsn_skip")
        await handle_callback(skip, _ctx())
        assert store.get("aaa").state == BotState.CREATING_INVOICE_GST_TYPE

    async def test_gst_rate_selection_advances_to_confirm(self):
        from app.bot import handle_callback, store
        from app.session_store import BotState
        store.reset("bbb")
        sess = store.get("bbb")
        sess.pending_create_invoice = {
            "bill_to": {"name": "X", "address": "Y", "gstin": "", "state": ""},
            "items": [{"name": "A", "qty": 1, "unit_cost": 1000, "amount": 1000, "hsn": "9001"}],
            "gst_rate": 18.0, "bill_number": "", "bill_date": "",
        }
        sess.company_profile = {"invoice_prefix": "TEST", "invoice_counter": 42}
        sess.state = BotState.CREATING_INVOICE_GST_TYPE

        with patch("app.bot._refresh_profile", new=AsyncMock(return_value=sess.company_profile)):
            cb = _make_callback(user_id="bbb", data="create:gst:12")
            await handle_callback(cb, _ctx())

        sess = store.get("bbb")
        assert sess.state == BotState.CREATING_INVOICE_CONFIRM
        assert sess.pending_create_invoice["gst_rate"] == 12.0
        assert sess.pending_create_invoice["bill_number"] == "TEST-0042"

    async def test_custom_gst_invalid_input_rejected(self):
        from app.bot import handle_text, store
        from app.session_store import BotState
        store.reset("ccc")
        sess = store.get("ccc")
        sess.state = BotState.CREATING_INVOICE_GST_CUSTOM
        sess.pending_create_invoice = {
            "bill_to": {"name": "X", "address": "Y"},
            "items": [{"name": "A", "qty": 1, "unit_cost": 100, "amount": 100, "hsn": "9001"}],
            "gst_rate": 0.0, "bill_number": "", "bill_date": "",
        }
        upd = _make_update(user_id="ccc", text="banana")
        await handle_text(upd, _ctx())
        # remains in custom-gst state, did not change
        assert store.get("ccc").state == BotState.CREATING_INVOICE_GST_CUSTOM

    async def test_cancel_resets_session(self):
        from app.bot import handle_callback, store
        from app.session_store import BotState
        store.reset("ddd")
        sess = store.get("ddd")
        sess.state = BotState.CREATING_INVOICE_BILLTO
        sess.pending_create_invoice = {"bill_to": {}, "items": [], "gst_rate": 0.0,
                                       "bill_number": "", "bill_date": ""}
        cb = _make_callback(user_id="ddd", data="create:cancel")
        await handle_callback(cb, _ctx())
        sess = store.get("ddd")
        assert sess.state == BotState.IDLE
        assert sess.pending_create_invoice is None

    async def test_full_generate_invokes_bill_pdf_and_logs(self, tmp_path, monkeypatch):
        """The 'Generate' button calls increment_counter, renders, logs, replies with doc."""
        from app.bot import handle_callback, store
        from app.session_store import BotState
        store.reset("eee")
        sess = store.get("eee")
        sess.org_id = "test-org"
        sess.company_profile = {"display_name": "DocSeva Test",
                                "invoice_prefix": "INV", "invoice_counter": 1,
                                "gstin": "27TEST", "phone": "9999"}
        sess.pending_create_invoice = {
            "bill_to": {"name": "ABC Corp", "address": "12 Test Rd", "gstin": "07ABC", "state": "Delhi"},
            "items": [
                {"name": "Item A", "qty": 1, "unit_cost": 1000, "amount": 1000, "hsn": "9001"},
            ],
            "gst_rate": 18.0, "bill_number": "INV-0001", "bill_date": "31-05-2026",
        }
        sess.state = BotState.CREATING_INVOICE_CONFIRM

        with patch("app.bot.api_client.increment_counter", return_value=99), \
             patch("app.bot.api_client.increment_quota"), \
             patch("app.bot.api_client.log_document", return_value={"id": "doc-1"}), \
             patch("app.bot._check_quota", return_value=(True, "")), \
             patch("app.bot._refresh_profile", new=AsyncMock(return_value=sess.company_profile)), \
             patch("app.bot._upload_output_file", new=AsyncMock(return_value="outputs/test/doc/file.pdf")), \
             patch("app.bot._download_user_logo", new=AsyncMock(return_value=None)), \
             patch("app.bot._user_tmp", side_effect=lambda u, n: tmp_path / n):
            cb = _make_callback(user_id="eee", data="create:generate")
            await handle_callback(cb, _ctx())

        # session reset after success
        assert store.get("eee").state == BotState.IDLE
        # bot replied with a document
        assert cb.callback_query.message.reply_document.called
        # the file was actually produced
        produced = list(tmp_path.glob("*.pdf"))
        assert len(produced) == 1
        assert produced[0].stat().st_size > 500


# ── Quotation flow (lighter coverage — same machinery) ───────────────────────

class TestCreateQuotationFlow:
    async def test_quotation_full_flow_to_confirm(self):
        from app.bot import handle_callback, handle_text, store
        from app.session_store import BotState
        store.reset("qqq")

        with patch("app.bot._refresh_profile", new=AsyncMock(return_value={
                "display_name": "Tester", "quotation_prefix": "QT", "quotation_counter": 7})):
            # 1) /create -> quotation
            await handle_callback(_make_callback(user_id="qqq", data="create:quotation"), _ctx())
            assert store.get("qqq").state == BotState.CREATING_QUOTATION_BILLTO

            # 2) BillTo
            await handle_text(_make_update(user_id="qqq", text=(
                "Name: XYZ Buyer\nAddress: 10 Park Street"
            )), _ctx())
            assert store.get("qqq").state == BotState.CREATING_QUOTATION_ITEMS

            # 3) Items
            await handle_text(_make_update(user_id="qqq", text=(
                "Service A | 1 | 5000\nService B | 2 | 2500"
            )), _ctx())
            assert store.get("qqq").state == BotState.CREATING_QUOTATION_TERMS

            # 4) Terms = default
            await handle_text(_make_update(user_id="qqq", text="default"), _ctx())
            sess = store.get("qqq")
            assert sess.state == BotState.CREATING_QUOTATION_CONFIRM
            assert sess.pending_create_quotation["ref_no"] == "QT-0007"
            assert sess.pending_create_quotation["validity_days"] == 30

    async def test_quotation_custom_terms_parsed(self):
        from app.bot import handle_text, store
        from app.session_store import BotState
        store.reset("rrr")
        sess = store.get("rrr")
        sess.state = BotState.CREATING_QUOTATION_TERMS
        sess.pending_create_quotation = {
            "bill_to": {"name": "X", "address": "Y"},
            "items": [{"name": "A", "qty": 1, "unit_cost": 100, "amount": 100, "hsn": ""}],
            "validity_days": 30, "payment_terms": "100% advance",
            "delivery_terms": "Within 7 days", "ref_no": "", "date": "",
        }
        with patch("app.bot._refresh_profile", new=AsyncMock(return_value={
                "quotation_prefix": "QT", "quotation_counter": 1})):
            await handle_text(_make_update(user_id="rrr", text=(
                "Validity: 60 days\nPayment: 50% advance + 50% on delivery\nDelivery: 2 weeks"
            )), _ctx())
        sess = store.get("rrr")
        assert sess.pending_create_quotation["validity_days"] == 60
        assert sess.pending_create_quotation["payment_terms"] == "50% advance + 50% on delivery"
        assert sess.pending_create_quotation["delivery_terms"] == "2 weeks"
