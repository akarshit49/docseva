"""
#genai: WS-3 — Create Invoice / Quotation from scratch.

Pure functions used by bot.py to drive the guided-creation flows. Keeping the
parsing + table-rendering helpers out of bot.py keeps that file from growing
unbounded and makes the logic trivially unit-testable.
"""
from __future__ import annotations

from typing import Any

from app.utils import parse_billto_block


# ── Item parsing ─────────────────────────────────────────────────────────────

def _parse_number(s: str, default: float = 0.0) -> float:
    """Parse a number, stripping currency symbols, commas, and whitespace."""
    cleaned = (
        str(s)
        .replace("₹", "")
        .replace("Rs.", "")
        .replace("Rs", "")
        .replace(",", "")
        .strip()
    )
    if not cleaned:
        return default
    try:
        return float(cleaned)
    except ValueError:
        return default


def parse_invoice_items(text: str) -> tuple[list[dict], list[str]]:
    """
    Parse user-entered items.

    Each line:   Name | Qty | UnitPrice | HSN(optional)

    Returns (items, error_lines). Lines that fail validation are reported back
    so the bot can show the user exactly what went wrong instead of silently
    dropping them.
    """
    items: list[dict] = []
    errors: list[str] = []
    for raw_line in text.strip().splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 3:
            errors.append(f"Need at least 3 fields (Name | Qty | Price): `{line[:60]}`")
            continue
        name = parts[0]
        if not name:
            errors.append(f"Item name is empty: `{line[:60]}`")
            continue
        qty = _parse_number(parts[1], default=0)
        unit_cost = _parse_number(parts[2], default=0)
        if qty <= 0 or unit_cost <= 0:
            errors.append(f"Qty and Price must be > 0: `{line[:60]}`")
            continue
        hsn = parts[3].strip() if len(parts) > 3 else ""
        items.append({
            "name": name,
            "qty": qty,
            "unit_cost": unit_cost,
            "hsn": hsn,
            "amount": round(qty * unit_cost, 2),
        })
    return items, errors


# ── HSN code parsing ─────────────────────────────────────────────────────────

def parse_hsn_response(text: str, items: list[dict]) -> tuple[list[dict], list[int]]:
    """
    Parse user-supplied HSN codes in `n: code` format and apply them to items
    (1-indexed). Returns (updated_items, still_missing_indices).
    """
    updates: dict[int, str] = {}
    for line in text.strip().splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        idx_str, _, code = line.partition(":")
        try:
            idx = int(idx_str.strip())
        except ValueError:
            continue
        code = code.strip()
        if code and 1 <= idx <= len(items):
            updates[idx - 1] = code

    new_items = [dict(it) for it in items]
    for i, code in updates.items():
        new_items[i]["hsn"] = code

    missing = [i + 1 for i, it in enumerate(new_items) if not it.get("hsn", "").strip()]
    return new_items, missing


#genai: KI fix — parse "n: rate" lines for the per-item GST sub-flow.
#       Mirrors parse_hsn_response so the UX feels consistent.
def parse_per_item_gst(text: str, items: list[dict]) -> tuple[list[dict], list[int], list[str]]:
    """Parse user-supplied per-item GST rates in `n: rate` format.

    Sets `gst_rate` AND marks items with `_gst_explicit=True`. Returns
    (updated_items, still_missing_item_numbers, error_lines).
    """
    errors: list[str] = []
    new_items = [dict(it) for it in items]
    for raw in text.strip().splitlines():
        line = raw.strip()
        if not line or ":" not in line:
            continue
        idx_str, _, rate_str = line.partition(":")
        try:
            idx = int(idx_str.strip())
        except ValueError:
            errors.append(f"Bad item number: `{line[:40]}`")
            continue
        rate_clean = rate_str.replace("%", "").strip()
        try:
            rate = float(rate_clean)
        except ValueError:
            errors.append(f"Bad rate: `{line[:40]}`")
            continue
        if rate < 0 or rate > 100:
            errors.append(f"Rate {rate} out of range (0-100): `{line[:40]}`")
            continue
        if not (1 <= idx <= len(items)):
            errors.append(f"Item #{idx} doesn't exist: `{line[:40]}`")
            continue
        new_items[idx - 1]["gst_rate"] = rate
        new_items[idx - 1]["_gst_explicit"] = True

    missing = [i + 1 for i, it in enumerate(new_items) if not it.get("_gst_explicit", False)]
    return new_items, missing, errors


# ── BillTo validation (reuses utils.parse_billto_block) ──────────────────────

def parse_customer_block(text: str) -> tuple[dict, list[str]]:
    """
    Parse a Bill-To-style block and validate required fields.
    Returns (data, missing_field_labels).
    """
    parsed = parse_billto_block(text)
    missing = []
    if not parsed.get("name"):
        missing.append("Name")
    if not parsed.get("address"):
        missing.append("Address")
    return parsed, missing


# ── Format / preview helpers ─────────────────────────────────────────────────

def format_items_table(items: list[dict]) -> str:
    """Format items as a compact Markdown-safe code block for Telegram preview."""
    if not items:
        return "_(no items yet)_"
    lines = []
    header = f"{'#':>2}  {'Item':<22}  {'Qty':>5}  {'Price':>10}  {'HSN':<8}"
    lines.append("```")
    lines.append(header)
    lines.append("-" * len(header))
    for i, it in enumerate(items, 1):
        name = (it["name"][:21] + "…") if len(it["name"]) > 22 else it["name"]
        qty = f"{it['qty']:.0f}" if it["qty"] == int(it["qty"]) else f"{it['qty']:.2f}"
        price = f"{it['unit_cost']:,.2f}"
        hsn = it.get("hsn", "") or "-"
        lines.append(f"{i:>2}  {name:<22}  {qty:>5}  {price:>10}  {hsn:<8}")
    lines.append("```")
    return "\n".join(lines)


def compute_totals(items: list[dict], gst_rate: float) -> dict:
    """Compute subtotal/gst/total — mirrors bill_to_make._normalize_bill_data."""
    subtotal = round(sum(float(it.get("amount", 0)) for it in items), 2)
    rate_buckets: dict[float, float] = {}
    for it in items:
        rate = float(it.get("gst_rate", gst_rate))
        rate_buckets[rate] = rate_buckets.get(rate, 0.0) + float(it.get("amount", 0))
    gst_breakdown = [
        {"rate": rate, "taxable": round(amt, 2), "tax": round(amt * rate / 100, 2)}
        for rate, amt in sorted(rate_buckets.items())
    ]
    gst_amount = round(sum(b["tax"] for b in gst_breakdown), 2)
    return {
        "subtotal": subtotal,
        "gst_amount": gst_amount,
        "gst_breakdown": gst_breakdown,
        "total": round(subtotal + gst_amount, 2),
    }


def build_invoice_data(
    bill_to: dict,
    items: list[dict],
    gst_rate: float,
    ship_to: dict | None = None,
) -> dict[str, Any]:
    """
    Build the canonical dict that `bill_to_make.generate_bill_pdf` expects.
    Re-uses the existing renderer so the look & feel is identical to LLM-parsed bills.
    """
    bt = {
        "name": bill_to.get("name", ""),
        "address": bill_to.get("address", ""),
        "gstin": bill_to.get("gstin", ""),
        "state_name": bill_to.get("state", ""),
        "state_code": bill_to.get("state_code", ""),
    }
    st_src = ship_to or bill_to
    st = {
        "name": st_src.get("shipto_name") or st_src.get("name", ""),
        "address": st_src.get("shipto_address") or st_src.get("address", ""),
        "gstin": st_src.get("shipto_gstin") or st_src.get("gstin", ""),
        "state_name": st_src.get("state", ""),
        "state_code": st_src.get("state_code", ""),
    }
    out_items = []
    for i, it in enumerate(items, 1):
        out_items.append({
            "sno": str(i),
            "name": it["name"],
            "hsn": it.get("hsn", ""),
            "qty": it["qty"],
            "unit": "Nos",
            "unit_cost": float(it["unit_cost"]),
            "amount": float(it["amount"]),
            "gst_rate": float(it.get("gst_rate", gst_rate)),
        })
    return {
        "bill_to": bt,
        "ship_to": st,
        "items": out_items,
        "gst_rate": float(gst_rate),
    }


# ── Number-to-words for invoice totals ───────────────────────────────────────

_ONES = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
         "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
         "Seventeen", "Eighteen", "Nineteen"]
_TENS = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]


def _two_digit(n: int) -> str:
    if n < 20:
        return _ONES[n]
    return _TENS[n // 10] + (" " + _ONES[n % 10] if n % 10 else "")


def _three_digit(n: int) -> str:
    if n == 0:
        return ""
    if n < 100:
        return _two_digit(n)
    return _ONES[n // 100] + " Hundred" + (" " + _two_digit(n % 100) if n % 100 else "")


def build_quotation_document(
    bill_to: dict,
    items: list[dict],
    ref_no: str,
    date_str: str,
    valid_until: str,
    subject: str = "Quotation",
) -> Any:
    """Build a `QuoteDocument` for the existing renderers.render() pipeline."""
    from app.processors.models import QuoteDocument, QuoteItem, QuoteSection

    #genai: KI fix — do NOT repeat the recipient name in address_lines.
    #       The renderer prints it once as the "To," heading; including it
    #       here again caused the duplicate-name bug.
    addr_lines: list[str] = []
    addr = bill_to.get("address", "")
    for line in addr.replace(",", "\n").splitlines():
        line = line.strip()
        if line and line.lower() != (bill_to.get("name", "") or "").strip().lower():
            addr_lines.append(line)
    if bill_to.get("gstin"):
        addr_lines.append(f"GSTIN: {bill_to['gstin']}")

    quote_items = []
    for i, it in enumerate(items, 1):
        quote_items.append(
            QuoteItem(
                sno=str(i),
                description=it["name"],
                qty=str(int(it["qty"]) if float(it["qty"]) == int(it["qty"]) else it["qty"]),
                unit_price=float(it["unit_cost"]),
                total=float(it["amount"]),
            )
        )

    section = QuoteSection(name="Items", items=quote_items)
    return QuoteDocument(
        recipient_name=bill_to.get("name", ""),
        recipient_address_lines=addr_lines,
        subject=subject,
        ref_no=ref_no,
        date=date_str,
        valid_until=valid_until,
        sections=[section],
    )


def amount_in_words(amount: float) -> str:
    """Convert amount to Indian-style words (Lakh/Crore). Returns 'Rupees X Only'."""
    n = int(round(amount))
    if n == 0:
        return "Rupees Zero Only"
    parts: list[str] = []
    crore = n // 10000000
    n %= 10000000
    lakh = n // 100000
    n %= 100000
    thousand = n // 1000
    n %= 1000
    hundred = n
    if crore:
        parts.append(_three_digit(crore) + " Crore")
    if lakh:
        parts.append(_three_digit(lakh) + " Lakh")
    if thousand:
        parts.append(_three_digit(thousand) + " Thousand")
    if hundred:
        parts.append(_three_digit(hundred))
    return "Rupees " + " ".join(parts).strip() + " Only"
