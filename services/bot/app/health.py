"""
#genai: Startup-time health checks for optional/external dependencies.

DocSeva does NOT require LibreOffice for DOCX→PDF — that path is pure-Python
via fpdf2/openpyxl/xlrd. This module verifies that those Python deps are
importable so we can disable a feature cleanly with a friendly message
instead of crashing mid-flow (KI-02).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class HealthReport:
    pdf_export_ok: bool = True
    pdf_export_reason: str = ""

    docxtpl_ok: bool = True
    docxtpl_reason: str = ""

    rembg_ok: bool = True
    rembg_reason: str = ""

    def summary(self) -> str:
        parts: list[str] = []
        if not self.pdf_export_ok:
            parts.append(f"PDF export disabled — {self.pdf_export_reason}")
        if not self.docxtpl_ok:
            parts.append(f"Template engine fallback disabled — {self.docxtpl_reason}")
        if not self.rembg_ok:
            parts.append(f"Background removal disabled — {self.rembg_reason}")
        return " | ".join(parts) if parts else "All optional deps OK."


def check_all() -> HealthReport:
    """Probe optional deps once at startup and cache the result on the instance."""
    report = HealthReport()

    try:
        import fpdf  # noqa: F401
        import openpyxl  # noqa: F401
        import xlrd  # noqa: F401
    except Exception as exc:
        report.pdf_export_ok = False
        report.pdf_export_reason = f"missing dep: {exc}"

    try:
        import docxtpl  # noqa: F401
    except Exception as exc:
        report.docxtpl_ok = False
        report.docxtpl_reason = f"missing dep: {exc}"

    try:
        import rembg  # noqa: F401
    except Exception as exc:
        report.rembg_ok = False
        report.rembg_reason = f"missing dep: {exc}"

    logger.info("Health check: %s", report.summary())
    return report


_cached: HealthReport | None = None


def get_health() -> HealthReport:
    global _cached
    if _cached is None:
        _cached = check_all()
    return _cached
