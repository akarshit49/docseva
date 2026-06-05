#genai: LLM-based GST invoice validator — math, totals, HSN codes, rate cross-check.
from __future__ import annotations

import json
import re

_SYSTEM_PROMPT = """\
You are an expert Indian GST invoice auditor. Analyse the invoice text carefully.

TASK: Extract all invoice data and validate three things:
1. MATH  — For every line item, verify: gst_amount = taxable_amount × gst_rate / 100 (allow ±2 rupee rounding).
   Also verify: grand_total = total_taxable + total_gst.
2. HSN   — Is each HSN/SAC code a real, valid Indian GST code?
3. MATCH — Does the HSN code actually match the product description?
           Does the GST rate match the standard rate for that HSN?

REFERENCE (partial — use your full training knowledge):
  9023 → 18%  (Instruments/apparatus for demonstrational purposes)
  9024 → 18%  (Testing machines — hardness, tensile, etc.)
  9025 → 18%  (Thermometers, hydrometers, pyrometers)
  9026 → 18%  (Flow / level measuring instruments)
  9027 → 18%  (Physical/chemical analysis instruments)
  9030 → 18%  (Oscilloscopes, signal generators)
  9031 → 18%  (Measuring/checking instruments NES)
  7326 → 18%  (Other articles of iron or steel)
  8479 → 18%  (Machines with individual functions)
  998719 → 18%  (Maintenance & repair services)
  3004 → 5%   (Medicines)
  0101–2400 → 0–5%  (Agricultural goods)

Return ONLY a single valid JSON object — no markdown fences, no commentary:
{
  "invoice_no": "...",
  "date": "...",
  "supplier": "...",
  "items": [
    {
      "sno": "1",
      "description": "...",
      "hsn": "...",
      "taxable_amount": 0.0,
      "gst_rate": 18.0,
      "gst_invoiced": 0.0,
      "gst_correct": 0.0,
      "total_invoiced": 0.0,
      "total_correct": 0.0,
      "math_ok": true,
      "hsn_valid": true,
      "hsn_matches_product": true,
      "gst_rate_correct": true,
      "issues": []
    }
  ],
  "totals": {
    "total_taxable_invoiced": 0.0,
    "total_gst_invoiced": 0.0,
    "grand_total_invoiced": 0.0,
    "total_gst_correct": 0.0,
    "totals_match": true,
    "issues": []
  },
  "overall_valid": true,
  "error_count": 0,
  "summary": "All calculations correct. HSN codes valid and appropriate."
}
"""


_CHUNK_THRESHOLD = 8000


def validate_gst_invoice(
    api_key: str,
    model: str,
    invoice_text: str,
) -> dict:
    """
    Call OpenAI to extract and validate all GST-related fields in the invoice.
    For long invoices (>8000 chars) the text is chunked, validated in parallel,
    and the per-item results are merged (KI-10).
    """
    from openai import OpenAI
    from app.utils import chunk_text

    client = OpenAI(api_key=api_key)

    if len(invoice_text) <= _CHUNK_THRESHOLD:
        return _validate_chunk(client, model, invoice_text)

    chunks = chunk_text(invoice_text, max_chars=_CHUNK_THRESHOLD, overlap=300)
    results = [_validate_chunk(client, model, ch) for ch in chunks]
    return _merge_validation_results(results)


def _validate_chunk(client, model: str, text: str) -> dict:
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": f"Validate this invoice:\n\n{text}"},
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )
    return json.loads(resp.choices[0].message.content)


def _merge_validation_results(results: list[dict]) -> dict:
    """Combine validation dicts from multiple chunks into one report."""
    if not results:
        return {"items": [], "totals": {}, "overall_valid": True, "error_count": 0, "summary": ""}

    base = dict(results[0])
    seen_keys: set[str] = set()
    merged_items: list[dict] = []
    for r in results:
        for item in r.get("items", []):
            key = (
                str(item.get("sno", "")),
                str(item.get("description", "")),
                str(item.get("hsn", "")),
            )
            sig = "|".join(key)
            if sig and sig in seen_keys:
                continue
            seen_keys.add(sig)
            merged_items.append(item)
    base["items"] = merged_items

    totals = {
        "total_taxable_invoiced": sum(float(it.get("taxable_amount", 0)) for it in merged_items),
        "total_gst_invoiced": sum(float(it.get("gst_invoiced", 0)) for it in merged_items),
        "grand_total_invoiced": sum(float(it.get("total_invoiced", 0)) for it in merged_items),
        "total_gst_correct": sum(float(it.get("gst_correct", 0)) for it in merged_items),
        "totals_match": all(it.get("math_ok", True) for it in merged_items),
        "issues": [],
    }
    base["totals"] = totals
    base["error_count"] = sum(1 for it in merged_items if not all([
        it.get("math_ok", True),
        it.get("hsn_valid", True),
        it.get("hsn_matches_product", True),
        it.get("gst_rate_correct", True),
    ]))
    base["overall_valid"] = base["error_count"] == 0
    base["summary"] = (
        f"Validated {len(merged_items)} items across {len(results)} chunks; "
        f"{base['error_count']} issue(s) found."
    )
    return base


def format_validation_report(result: dict) -> str:
    """
    Format the validation dict into a Telegram-friendly plain-text report
    with emoji status indicators.
    """
    lines: list[str] = []

    def _add(text: str = "") -> None:
        lines.append(text)

    _add("🧮 GST Validation Report")
    _add("=" * 36)

    if result.get("invoice_no"):
        _add(f"Invoice : {result['invoice_no']}")
    if result.get("date"):
        _add(f"Date    : {result['date']}")
    if result.get("supplier"):
        _add(f"Supplier: {result['supplier']}")
    _add()

    for item in result.get("items", []):
        all_ok = all([
            item.get("math_ok", True),
            item.get("hsn_valid", True),
            item.get("hsn_matches_product", True),
            item.get("gst_rate_correct", True),
        ])
        icon = "✅" if all_ok else "❌"
        desc = str(item.get("description", ""))[:50]
        _add(f"{icon} Item {item.get('sno', '')}: {desc}")

        hsn = item.get("hsn", "N/A")
        hsn_icon = "✓" if item.get("hsn_valid") else "✗"
        _add(f"   HSN {hsn} {hsn_icon}" + ("" if item.get("hsn_valid") else " (Invalid code)"))

        if not item.get("hsn_matches_product"):
            _add(f"   ⚠️  HSN may not match product description")
        if not item.get("gst_rate_correct"):
            _add(f"   ⚠️  GST rate {item.get('gst_rate')}% may be wrong for HSN {hsn}")

        taxable = item.get("taxable_amount", 0)
        rate = item.get("gst_rate", 18)
        inv = item.get("gst_invoiced", 0)
        correct = item.get("gst_correct", 0)
        math_icon = "✓" if item.get("math_ok") else "✗"
        _add(f"   Math: Rs.{taxable:,.2f} x {rate:.0f}% = Rs.{correct:,.2f}  |  Invoiced: Rs.{inv:,.2f} {math_icon}")

        for issue in item.get("issues", []):
            _add(f"   ⚠️  {issue}")
        _add()

    totals = result.get("totals", {})
    t_icon = "✅" if totals.get("totals_match") else "❌"
    _add(f"{t_icon} Totals")
    _add(f"   Taxable   : Rs.{totals.get('total_taxable_invoiced', 0):,.2f}")
    _add(f"   GST       : Rs.{totals.get('total_gst_invoiced', 0):,.2f}  " + (
        "(✓ matches sum of items)" if totals.get("totals_match") else
        f"(✗ correct = Rs.{totals.get('total_gst_correct', 0):,.2f})"
    ))
    _add(f"   Grand Total: Rs.{totals.get('grand_total_invoiced', 0):,.2f}")
    for issue in totals.get("issues", []):
        _add(f"   ⚠️  {issue}")
    _add()

    if result.get("overall_valid"):
        _add("🎉 OVERALL: Invoice is VALID — No errors found.")
    else:
        n = result.get("error_count", "?")
        _add(f"🚨 OVERALL: {n} error(s) found — see highlighted items above.")
    if result.get("summary"):
        _add()
        _add(f"Summary: {result['summary']}")

    return "\n".join(lines)


def validate_invoice(invoice_text: str) -> str:
    """Public entry point — validates GST invoice text and returns a formatted report string."""
    from app.config import settings as bot_settings
    result = validate_gst_invoice(bot_settings.openai_api_key, bot_settings.openai_model, invoice_text)
    return format_validation_report(result)
