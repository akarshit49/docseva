#genai: High-level sister-quotation service — parse input, render output, return QuoteDocument.
from __future__ import annotations

import copy
import random
from pathlib import Path

from app.processors.extractors import extract_text
from app.processors.formats import TargetFormat
from app.processors.llm_parser import parse_quote
from app.processors.models import QuoteDocument, _safe_qty
from app.processors.renderers import render


def convert_with_data(
    input_path: Path,
    target_format: TargetFormat,
    output_path: Path,
    company_profile: dict,
) -> tuple[Path, QuoteDocument]:
    """
    Parse input file, render sister quotation using a built-in format, return (output_path, parsed_doc).
    """
    text = extract_text(input_path)
    quote: QuoteDocument = parse_quote(text)
    render(quote, target_format, output_path, company_profile)
    return output_path, quote


def convert_with_template(
    input_path: Path,
    template_path: Path,
    output_path: Path,
    company_profile: dict,
) -> tuple[Path, QuoteDocument]:
    """
    Parse input file using a user-uploaded format template as guidance.

    Strategy:
      1. Extract text from both the input file and the template.
      2. Try to fill the template with docxtpl if it's a .docx with placeholders.
      3. Otherwise fall back to LLM extraction + the built-in 'detailed' renderer.

    Returns (output_path, QuoteDocument).
    """
    input_text = extract_text(input_path)
    template_text = extract_text(template_path)
    quote: QuoteDocument = parse_quote(input_text, format_reference=template_text)

    if template_path.suffix.lower() == ".docx" and _template_has_placeholders(template_path):
        try:
            _render_with_docxtpl(template_path, quote, company_profile, output_path)
            return output_path, quote
        except Exception:
            # docxtpl failed → fall back to the built-in renderer
            pass

    render(quote, TargetFormat.SV_ENTERPRISES, output_path, company_profile)
    return output_path, quote


def _template_has_placeholders(template_path: Path) -> bool:
    """Quick check for jinja-style placeholders inside a .docx template."""
    try:
        text = extract_text(template_path)
        return ("{{" in text and "}}" in text) or ("{%" in text and "%}" in text)
    except Exception:
        return False


def _render_with_docxtpl(
    template_path: Path,
    quote: QuoteDocument,
    company_profile: dict,
    output_path: Path,
) -> None:
    """Fill a docxtpl-style template with quote data and save to output_path."""
    from docxtpl import DocxTemplate

    doc = DocxTemplate(str(template_path))
    items_ctx = []
    for section in quote.sections:
        for item in section.items:
            items_ctx.append({
                "sno": item.sno,
                "description": item.description,
                "qty": item.qty,
                "unit_price": item.unit_price,
                "total": item.total,
                "section": section.name,
            })

    context = {
        "company": company_profile or {},
        "company_name": (company_profile or {}).get("display_name", ""),
        "company_address": (company_profile or {}).get("address", ""),
        "company_phone": (company_profile or {}).get("phone", ""),
        "company_gstin": (company_profile or {}).get("gstin", ""),
        "client_name": quote.recipient_name,
        "recipient_name": quote.recipient_name,
        "recipient_address": "\n".join(quote.recipient_address_lines or []),
        "subject": quote.subject,
        "ref_no": quote.ref_no,
        "date": quote.date,
        "valid_until": quote.valid_until,
        "items": items_ctx,
        "sections": [
            {
                "name": s.name,
                "items": [
                    {
                        "sno": it.sno,
                        "description": it.description,
                        "qty": it.qty,
                        "unit_price": it.unit_price,
                        "total": it.total,
                    }
                    for it in s.items
                ],
                "subtotal": s.subtotal,
            }
            for s in quote.sections
        ],
        "subtotal": quote.subtotal,
    }
    doc.render(context)
    doc.save(str(output_path))


def adjust_prices(quote: QuoteDocument, pct: float) -> QuoteDocument:
    """
    Return a deep copy of QuoteDocument with all prices adjusted by ~pct%.
    Applies ±2.5% randomisation and rounds to "natural" numbers.

    KI-05: iterates `sections.items` correctly; tolerates non-QuoteDocument
    inputs by raising ValueError (caller can show a friendly message).
    """
    if not hasattr(quote, "sections"):
        raise ValueError("adjust_prices requires a QuoteDocument")

    adjusted = copy.deepcopy(quote)
    for section in adjusted.sections:
        for item in section.items:
            factor = 1.0 + (pct / 100) * random.uniform(0.975, 1.025)
            if item.unit_price:
                item.unit_price = _round_natural(item.unit_price * factor)
            qty = _safe_qty(item.qty)
            item.total = _round_natural(item.unit_price * qty)
    return adjusted


def is_quote_document(obj) -> bool:
    """Best-effort runtime check used by the bot before offering price adjust (KI-05)."""
    return isinstance(obj, QuoteDocument) and bool(getattr(obj, "sections", None))


def _round_natural(value: float) -> float:
    """Round to the nearest 'nice' number (50 or 100 depending on magnitude)."""
    if value < 500:
        return round(value / 10) * 10
    elif value < 5_000:
        return round(value / 50) * 50
    elif value < 50_000:
        return round(value / 100) * 100
    else:
        return round(value / 500) * 500
