#genai: Quotation data structures.
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class QuoteItem:
    sno: str
    description: str
    qty: str
    unit_price: float
    total: float


@dataclass
class QuoteSection:
    name: str
    items: List[QuoteItem] = field(default_factory=list)

    @property
    def subtotal(self) -> float:
        return sum(item.unit_price * _safe_qty(item.qty) for item in self.items)


@dataclass
class QuoteDocument:
    recipient_name: str
    recipient_address_lines: List[str]
    subject: str
    ref_no: str
    date: str
    valid_until: str
    sections: List[QuoteSection] = field(default_factory=list)
    #genai: KI fix — terms shown after the items table (not inside it).
    #       When empty, renderers fall back to a sensible static list.
    terms_list: List[str] = field(default_factory=list)

    @property
    def subtotal(self) -> float:
        return sum(section.subtotal for section in self.sections)


def _safe_qty(qty_text: str) -> float:
    normalized = qty_text.lower().replace("set", "").strip()
    if not normalized:
        return 1.0
    try:
        return float(normalized)
    except ValueError:
        return 1.0

