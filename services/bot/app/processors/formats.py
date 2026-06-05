#genai: Supported sister quotation target formats.
from __future__ import annotations

from enum import Enum


class TargetFormat(str, Enum):
    SV_ENTERPRISES = "sv_enterprises"
    SANMATI = "sanmati"
    NR_SURVEY = "nr_survey"

    @property
    def label(self) -> str:
        mapping = {
            TargetFormat.SV_ENTERPRISES: "SV Enterprises",
            TargetFormat.SANMATI: "Sanmati Enterprises",
            TargetFormat.NR_SURVEY: "NR Survey Instruments",
        }
        return mapping[self]

    @staticmethod
    def parse(text: str) -> "TargetFormat | None":
        normalized = text.lower().strip()
        if "sv" in normalized:
            return TargetFormat.SV_ENTERPRISES
        if "sanmati" in normalized:
            return TargetFormat.SANMATI
        if "nr" in normalized or "survey" in normalized:
            return TargetFormat.NR_SURVEY
        return None

