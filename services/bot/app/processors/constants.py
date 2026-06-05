#genai: Runtime constants — colours, default company info, and bundled logo.
from __future__ import annotations

from pathlib import Path


# ── Logo path resolution ─────────────────────────────────────────────────────
# Logo is baked into the Docker image at /app/assets/logo.png at build time.
# In test environments it falls back to the repo's assets/ directory.

def _resolve_logo() -> Path:
    candidates = [Path("/app/assets/logo.png")]
    for n in range(3, 7):
        try:
            candidates.append(Path(__file__).resolve().parents[n] / "assets" / "logo.png")
        except IndexError:
            continue
    return next((p for p in candidates if p.exists()), candidates[0])


LOGO_PATH: Path = _resolve_logo()


# ── Default company info (used as last-resort fallback only) ─────────────────
# These exist so that processors can `from constants import CO_NAME` without
# crashing when no `company_profile` dict is provided at runtime.
CO_NAME = "Your Company"
CO_ADDRESS = ""
CO_PHONE = ""
CO_GSTIN = ""


# ── Brand colours ────────────────────────────────────────────────────────────
GOLD_RGB = (201, 168, 76)
BLACK_RGB = (0, 0, 0)
WHITE_RGB = (255, 255, 255)
DARK_GRAY_RGB = (60, 60, 60)
LIGHT_GRAY_RGB = (240, 240, 240)

GOLD_HEX = "C9A84C"
DARK_NAVY_HEX = "1F4E79"
WHITE_HEX = "FFFFFF"
LIGHT_GREEN_HEX = "E2EFDA"
LIGHT_RED_HEX = "FCE4D6"
LIGHT_BLUE_HEX = "EBF3FB"
LIGHT_GRAY_HEX = "F5F5F5"
