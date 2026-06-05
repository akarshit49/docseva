#genai: Watermark an image with the company logo or a text string.
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def add_watermark(
    image_path: Path,
    output_path: Path,
    opacity: float = 0.30,
    size_fraction: float = 0.38,
    logo_path: Path | None = None,
    text: str | None = None,
    mode: str = "logo",
) -> Path:
    """
    Stamp the company logo or a text string as a translucent, centred watermark.

    Args:
        image_path:    Source image (any format Pillow understands).
        output_path:   Destination — suffix will be forced to .png.
        opacity:       0.0–1.0 — how visible the watermark is (default 30%).
        size_fraction: Watermark width as a fraction of the shorter image side.
        logo_path:     Path to the user's uploaded logo. Required when mode='logo';
                       no bundled default is used in production.
        text:          If mode='text', the text to stamp.
        mode:          'logo' or 'text'.

    Returns:
        Path to the watermarked PNG.
    """
    _register_heif()

    base = Image.open(str(image_path)).convert("RGBA")
    if mode == "text" and text:
        watermarked = _apply_text_watermark(base, text, opacity, size_fraction)
    else:
        #genai: KI fix — no bundled-logo fallback. If user picked logo mode
        # without a logo we render a text watermark using the file stem so
        # the operation still succeeds visibly.
        if logo_path is None or not Path(logo_path).exists():
            watermarked = _apply_text_watermark(base, (text or image_path.stem)[:40] or "WATERMARK", opacity, size_fraction)
        else:
            watermarked = _apply_logo_watermark(base, Path(logo_path), opacity, size_fraction)

    out = output_path.with_suffix(".png")
    watermarked.save(str(out), "PNG")
    return out


def _apply_logo_watermark(base: Image.Image, logo_path: Path, opacity: float, size_fraction: float) -> Image.Image:
    bw, bh = base.size

    logo_path = Path(logo_path)
    if not logo_path.exists():
        # Fall back to a text watermark using the file's stem so we always produce *something*
        return _apply_text_watermark(base, "WATERMARK", opacity, size_fraction)

    logo = Image.open(str(logo_path)).convert("RGBA")
    target = int(min(bw, bh) * size_fraction)
    logo = logo.resize((target, target), Image.LANCZOS)
    lw, lh = logo.size

    r, g, b, a = logo.split()
    a = a.point(lambda px: int(px * opacity))
    logo.putalpha(a)

    pos_x = (bw - lw) // 2
    pos_y = (bh - lh) // 2

    watermarked = base.copy()
    watermarked.paste(logo, (pos_x, pos_y), logo)
    return watermarked


def _apply_text_watermark(base: Image.Image, text: str, opacity: float, size_fraction: float) -> Image.Image:
    bw, bh = base.size
    overlay = Image.new("RGBA", (bw, bh), (255, 255, 255, 0))
    draw = ImageDraw.Draw(overlay)

    target = max(20, int(min(bw, bh) * size_fraction / 6))
    font = _load_font(target)
    text_bbox = draw.textbbox((0, 0), text, font=font)
    tw = text_bbox[2] - text_bbox[0]
    th = text_bbox[3] - text_bbox[1]
    px = (bw - tw) // 2
    py = (bh - th) // 2

    alpha = int(255 * opacity)
    draw.text((px, py), text, fill=(80, 80, 80, alpha), font=font)
    return Image.alpha_composite(base, overlay)


def _load_font(size: int) -> ImageFont.ImageFont:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/Library/Fonts/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size=size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def _register_heif() -> None:
    """Enable HEIC/HEIF support if pillow-heif is installed."""
    try:
        from pillow_heif import register_heif_opener
        register_heif_opener()
    except ImportError:
        pass
