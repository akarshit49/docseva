#genai: Premium product-catalog PDF generator with Sanmati Enterprises black/gold branding.
from __future__ import annotations

from pathlib import Path

from fpdf import FPDF

from app.processors.constants import (
    BLACK_RGB,
    DARK_GRAY_RGB,
    GOLD_RGB,
    LIGHT_GRAY_RGB,
    WHITE_RGB,
)

# Defaults (overridden at runtime by company_profile)
CO_NAME = "DocSeva"
CO_ADDRESS = ""
CO_GSTIN = ""
CO_PHONE = ""
# Runtime-injected path to the user's uploaded logo. None means no logo;
#genai: KI fix — never silently fall back to a bundled default logo.
USER_LOGO_PATH: Path | None = None


# ── Internal helpers ─────────────────────────────────────────────────────────

def _s(text: str) -> str:
    """Safely encode text for fpdf2 (Latin-1 only)."""
    return str(text).encode("latin-1", errors="replace").decode("latin-1")


def _img_fit(image_path: Path, max_w: float, max_h: float) -> tuple[float, float, float, float]:
    """
    Return (x_offset_within_box, y_offset_within_box, draw_w, draw_h)
    so the image fits centred inside max_w × max_h preserving aspect ratio.
    """
    from PIL import Image as _PILImage
    img = _PILImage.open(str(image_path))
    iw, ih = img.size
    ratio = iw / ih
    if ratio > max_w / max_h:
        w, h = max_w, max_w / ratio
    else:
        h, w = max_h, max_h * ratio
    return (max_w - w) / 2, (max_h - h) / 2, w, h


# ── Public API ───────────────────────────────────────────────────────────────

def generate_catalog_pdf(
    image_path: Path | None,
    item_name: str,
    price: str | None,
    description: str | None,
    output_path: Path,
) -> Path:
    """
    Render a single-page product catalog PDF.

    Layout (A4 portrait, 210 × 297 mm):
      • Top band  (0–48 mm)   – black, logo + company name
      • Image area (50–178 mm) – gold border, product photo
      • Details   (182–258 mm) – item name, price, description
      • Footer    (265–297 mm) – black band, contact info
    """
    pdf = _CatalogPDF()
    pdf.set_margins(0, 0, 0)
    pdf.set_auto_page_break(False)
    pdf.add_page()

    _draw_header(pdf)
    _draw_image_section(pdf, image_path)
    _draw_details(pdf, item_name, price, description)
    _draw_footer(pdf)

    out = output_path.with_suffix(".pdf")
    pdf.output(str(out))
    return out


# ── Page sections ────────────────────────────────────────────────────────────

def _draw_header(pdf: "FPDF") -> None:
    """Black header band with logo (left, if available) and company name."""
    pdf.set_fill_color(*BLACK_RGB)
    pdf.rect(0, 0, 210, 48, "F")

    #genai: KI fix — only draw the logo if the user provided one. When no logo
    # is configured we centre the company-name block across the full header so
    # there is no awkward empty rectangle where a placeholder image would sit.
    has_logo = USER_LOGO_PATH is not None and Path(USER_LOGO_PATH).exists()
    if has_logo:
        try:
            pdf.image(str(USER_LOGO_PATH), x=6, y=5, w=38, h=38)
        except Exception:
            has_logo = False

    name_x = 50 if has_logo else 10
    name_w = 152 if has_logo else 190

    pdf.set_xy(name_x, 10)
    pdf.set_text_color(*GOLD_RGB)
    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(name_w, 12, _s(CO_NAME), align="C")

    pdf.set_xy(name_x, 26)
    pdf.set_font("Helvetica", "", 12)
    pdf.cell(name_w, 9, "Product Catalog", align="C")

    pdf.set_xy(name_x, 37)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*GOLD_RGB)
    pdf.cell(name_w, 6, "Scientific Instruments Manufacturer & Dealer", align="C")


def _draw_image_section(pdf: "FPDF", image_path: Path | None) -> None:
    """Gold-bordered product image centred in the middle of the page."""
    frame_x, frame_y, frame_w, frame_h = 10, 52, 190, 128
    pad = 3  # mm padding inside gold border

    # Gold border frame
    pdf.set_draw_color(*GOLD_RGB)
    pdf.set_line_width(1.2)
    pdf.rect(frame_x, frame_y, frame_w, frame_h)

    if image_path and image_path.exists():
        try:
            inner_w = frame_w - 2 * pad
            inner_h = frame_h - 2 * pad
            dx, dy, dw, dh = _img_fit(image_path, inner_w, inner_h)
            pdf.image(
                str(image_path),
                x=frame_x + pad + dx,
                y=frame_y + pad + dy,
                w=dw,
                h=dh,
            )
        except Exception:
            _placeholder(pdf, frame_x, frame_y, frame_w, frame_h)
    else:
        _placeholder(pdf, frame_x, frame_y, frame_w, frame_h)

    # Thin gold separator below image area
    pdf.set_draw_color(*GOLD_RGB)
    pdf.set_line_width(0.8)
    pdf.line(10, frame_y + frame_h + 3, 200, frame_y + frame_h + 3)


def _placeholder(pdf: "FPDF", x: float, y: float, w: float, h: float) -> None:
    pdf.set_fill_color(*LIGHT_GRAY_RGB)
    pdf.rect(x, y, w, h, "F")
    pdf.set_xy(x, y + h / 2 - 5)
    pdf.set_font("Helvetica", "I", 13)
    pdf.set_text_color(*DARK_GRAY_RGB)
    pdf.cell(w, 10, "[Product Image]", align="C")


def _draw_details(
    pdf: "FPDF",
    item_name: str,
    price: str | None,
    description: str | None,
) -> None:
    """Item name, price and description below the image."""
    start_y = 186

    # Item name
    pdf.set_xy(10, start_y)
    pdf.set_font("Helvetica", "B", 17)
    pdf.set_text_color(*BLACK_RGB)
    pdf.multi_cell(190, 10, _s(item_name))
    cur_y = pdf.get_y() + 2

    # Price
    if price:
        pdf.set_xy(10, cur_y)
        pdf.set_font("Helvetica", "B", 14)
        pdf.set_text_color(*GOLD_RGB)
        pdf.cell(190, 9, _s(f"Price: {price}"))
        cur_y = pdf.get_y() + 9 + 3

    # Description
    if description and cur_y < 258:
        pdf.set_xy(10, cur_y)
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(*DARK_GRAY_RGB)
        # Limit height so we don't overflow into the footer
        max_lines = max(1, int((258 - cur_y) / 6))
        lines = _wrap_text(description, max_chars=90)[:max_lines]
        for ln in lines:
            pdf.set_xy(10, pdf.get_y())
            pdf.cell(190, 6, _s(ln))
            pdf.ln(6)


def _draw_footer(pdf: "FPDF") -> None:
    """Black footer band with contact information in gold."""
    pdf.set_fill_color(*BLACK_RGB)
    pdf.rect(0, 265, 210, 32, "F")

    pdf.set_text_color(*GOLD_RGB)

    pdf.set_xy(0, 271)
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(210, 7, _s(f"{CO_NAME} \u2014 Manufacturer & Dealer of Scientific Instruments"), align="C")

    pdf.set_xy(0, 280)
    pdf.set_font("Helvetica", "", 8)
    pdf.cell(210, 6, _s(f"Ph: {CO_PHONE}  |  GSTIN: {CO_GSTIN}"), align="C")

    pdf.set_xy(0, 288)
    pdf.cell(210, 6, _s(CO_ADDRESS), align="C")


# ── Utilities ────────────────────────────────────────────────────────────────

def _wrap_text(text: str, max_chars: int = 80) -> list[str]:
    words = str(text).split()
    lines, cur = [], ""
    for word in words:
        if len(cur) + len(word) + 1 <= max_chars:
            cur = (cur + " " + word).strip()
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


class _CatalogPDF(FPDF):
    pass


def generate_catalog(
    image_path: Path | None,
    output_path: Path,
    item_name: str,
    description: str | None = None,
    price: str | None = None,
    company_profile: dict | None = None,
    logo_path: Path | None = None,
) -> Path:
    """Public entry point used by the bot — injects company profile then calls generate_catalog_pdf.

    #genai: KI fix — logo_path is now required to come from the user (or stay
    None). We deliberately do not fall back to a bundled default in production.
    """
    global CO_NAME, CO_ADDRESS, CO_GSTIN, CO_PHONE, USER_LOGO_PATH
    if company_profile:
        CO_NAME = company_profile.get("display_name") or CO_NAME
        addr_parts = [
            company_profile.get("address") or "",
            company_profile.get("city") or "",
            company_profile.get("state") or "",
        ]
        CO_ADDRESS = ", ".join(p for p in addr_parts if p) or CO_ADDRESS
        CO_GSTIN = company_profile.get("gstin") or CO_GSTIN
        CO_PHONE = company_profile.get("phone") or CO_PHONE
    USER_LOGO_PATH = logo_path
    return generate_catalog_pdf(image_path, item_name, price, description, output_path)
