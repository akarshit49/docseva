#genai: AI-powered background removal via rembg (U2-Net), returns PNG.
from __future__ import annotations

from pathlib import Path


def remove_background(image_path: Path, output_path: Path) -> Path:
    """
    Remove the background from an equipment/product image using rembg.

    The U2-Net model is downloaded automatically on first use (~170 MB).
    Subsequent calls are fast.

    Args:
        image_path:  Source image (PNG / JPG / JPEG / WEBP / HEIC / etc.)
        output_path: Destination path — suffix is forced to .png.

    Returns:
        Path to the background-free PNG.
    """
    _register_heif()

    try:
        from rembg import remove
    except ImportError as exc:
        raise RuntimeError(
            "rembg is not installed. Run: pip install rembg"
        ) from exc

    with open(str(image_path), "rb") as fh:
        raw = fh.read()

    result = remove(raw)

    out = output_path.with_suffix(".png")
    with open(str(out), "wb") as fh:
        fh.write(result)

    return out


def _register_heif() -> None:
    try:
        from pillow_heif import register_heif_opener
        register_heif_opener()
    except ImportError:
        pass
