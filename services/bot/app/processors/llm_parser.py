#genai: LLM-powered quotation parser with strict JSON schema.
from __future__ import annotations

import json

from openai import OpenAI

from app.processors.models import QuoteDocument, QuoteItem, QuoteSection


def parse_quotation_text(
    api_key: str,
    model: str,
    raw_text: str,
    format_reference: str = "",
) -> QuoteDocument:
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is missing.")

    client = OpenAI(api_key=api_key)

    format_guidance = (
        f"\nFormat guidance (example of the target format structure):\n{format_reference}"
        if format_reference
        else "\nNo specific format reference provided — use a clean professional quotation structure."
    )

    prompt = f"""
You are a quotation extraction engine.
Extract the quotation from the input text into JSON.
Recalculate each item total as qty * unit_price and ignore source totals when conflicting.
Return JSON only — no markdown, no explanation.

Output schema:
{{
  "recipient_name": "string",
  "recipient_address_lines": ["string"],
  "subject": "string",
  "ref_no": "string",
  "date": "string",
  "valid_until": "string",
  "sections": [
    {{
      "name": "string",
      "items": [
        {{
          "sno": "1.",
          "description": "string",
          "qty": "01",
          "unit_price": 1000.0
        }}
      ]
    }}
  ]
}}
{format_guidance}

Input quotation text:
{raw_text}
"""

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )
    content = response.choices[0].message.content or ""
    payload = _extract_json(content)
    return _to_quote_document(payload)


def _extract_json(content: str) -> dict:
    stripped = content.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        stripped = stripped.replace("json", "", 1).strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("Model response did not contain JSON.")
    return json.loads(stripped[start : end + 1])


def _to_quote_document(payload: dict) -> QuoteDocument:
    sections: list[QuoteSection] = []
    for section in payload.get("sections", []):
        items: list[QuoteItem] = []
        for idx, item in enumerate(section.get("items", []), start=1):
            qty_text = str(item.get("qty", "01"))
            unit_price = float(item.get("unit_price", 0))
            qty_num = _safe_qty(qty_text)
            items.append(
                QuoteItem(
                    sno=item.get("sno", f"{idx}."),
                    description=item.get("description", "").strip(),
                    qty=qty_text,
                    unit_price=unit_price,
                    total=round(qty_num * unit_price, 2),
                )
            )
        sections.append(QuoteSection(name=section.get("name", "GENERAL"), items=items))

    return QuoteDocument(
        recipient_name=payload.get("recipient_name", "Client"),
        recipient_address_lines=payload.get("recipient_address_lines", []),
        subject=payload.get("subject", "required items"),
        ref_no=payload.get("ref_no", ""),
        date=payload.get("date", ""),
        valid_until=payload.get("valid_until", ""),
        sections=sections,
    )


def _safe_qty(qty_text: str) -> float:
    normalized = qty_text.lower().replace("set", "").strip()
    try:
        return float(normalized)
    except ValueError:
        return 1.0


def parse_quote(raw_text: str, format_reference: str = "") -> QuoteDocument:
    """Parse a quotation using the LLM. Optionally pass extracted template text as format_reference."""
    from app.config import settings as bot_settings
    return parse_quotation_text(
        api_key=bot_settings.openai_api_key,
        model=bot_settings.openai_model,
        raw_text=raw_text,
        format_reference=format_reference,
    )
