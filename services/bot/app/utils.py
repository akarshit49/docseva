"""
#genai: Pure-function utilities shared between bot.py and the test suite.
No heavy dependencies — safe to import anywhere.
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

# ── Date parsing ─────────────────────────────────────────────────────────────

_DATE_FORMATS = [
    "%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y",
    "%d-%m-%y", "%d/%m/%y", "%d.%m.%y",
    "%Y-%m-%d", "%Y/%m/%d",
    "%d %b %Y", "%d %B %Y", "%b %d %Y", "%B %d %Y",
]


def parse_date(date_str: str) -> str | None:
    """Parse a date string in any common format. Returns DD-MM-YYYY or None."""
    if not date_str:
        return None
    for fmt in _DATE_FORMATS:
        try:
            dt = datetime.strptime(date_str.strip(), fmt)
            if not (2000 <= dt.year <= 2099):
                continue
            return dt.strftime("%d-%m-%Y")
        except ValueError:
            continue
    return None


# ── Blank detection ──────────────────────────────────────────────────────────

_BILL_EMPTY = {
    "", "na", "n/a", "n.a.", "none", "unknown", "nil",
    "-", "not available", "not provided",
}


def is_blank(val: str) -> bool:
    """Return True if val is empty, NA, N/A, None, nil, etc."""
    if val is None:
        return True
    return str(val).strip().lower() in _BILL_EMPTY


# ── BillTo block parsing (KI-11) ─────────────────────────────────────────────

_BILLTO_KEY_ALIASES = {
    "name": ("name", "billto name", "bill to name", "bill_to_name", "company", "company name"),
    "address": ("address", "billto address", "bill to address", "bill_to_address", "addr"),
    "gstin": ("gstin", "gst", "gst no", "gstno", "gst_no", "gst number"),
    "state": ("state", "state name", "billto state", "bill to state"),
    "shipto_name": ("shipto name", "ship to name", "ship_to_name", "deliver to name"),
    "shipto_address": ("shipto address", "ship to address", "ship_to_address", "deliver to address", "delivery address"),
    "shipto_gstin": ("shipto gstin", "ship to gstin", "ship_to_gstin"),
}


def _normalise_key(k: str) -> str:
    """lowercase, strip, collapse internal whitespace."""
    return re.sub(r"\s+", " ", k.strip().lower())


def parse_billto_block(text: str) -> dict:
    """
    Parse a user-supplied BillTo block of the form:
        Name: ABC Pvt Ltd
        Address: 45 MG Road, Delhi
        GSTIN: 07ABCDE1234F1Z5
        State: Delhi
        ShipTo Name: ...
        ShipTo Address: ...

    Returns a dict with canonical keys: name, address, gstin, state,
    shipto_name, shipto_address, shipto_gstin. Missing values are "".
    Case-insensitive, whitespace-tolerant.
    """
    raw: dict[str, str] = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        raw[_normalise_key(key)] = val.strip()

    result = {canonical: "" for canonical in _BILLTO_KEY_ALIASES}
    for canonical, aliases in _BILLTO_KEY_ALIASES.items():
        for alias in aliases:
            if alias in raw and raw[alias]:
                result[canonical] = raw[alias]
                break
    return result


# ── History date formatting (KI-08) ──────────────────────────────────────────

def format_history_date(iso_str: str) -> str:
    """
    Convert an ISO 8601 timestamp like '2024-05-31T10:45:00+00:00' to a
    readable '31 May 2024' string. Returns the original (truncated) string
    if parsing fails.
    """
    if not iso_str:
        return ""
    try:
        cleaned = iso_str.rstrip("Z")
        dt = datetime.fromisoformat(cleaned)
        return dt.strftime("%d %b %Y")
    except Exception:
        return iso_str[:10]


# ── Per-user tmp path isolation (KI-15) ──────────────────────────────────────

_TMP_ROOT = Path("/tmp/docseva")


def user_tmp_path(user_id: str | int, filename: str, root: Path | None = None) -> Path:
    """
    Build a temp-file path isolated per user:  /tmp/docseva/<uid>/<filename>.
    Two users renaming files to the same name will not collide.
    """
    base = root or _TMP_ROOT
    safe_uid = re.sub(r"[^A-Za-z0-9_-]+", "_", str(user_id))[:32] or "anon"
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", filename)
    # Collapse any traversal artefacts before truncating.
    safe_name = re.sub(r"\.{2,}", "_", safe_name).strip("._-") or "file"
    safe_name = safe_name[:120]
    path = base / safe_uid / safe_name
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


# ── Text chunking (KI-10) ────────────────────────────────────────────────────

def chunk_text(text: str, max_chars: int = 6000, overlap: int = 200) -> list[str]:
    """
    Split long text into roughly `max_chars`-sized chunks with `overlap`
    characters of context between consecutive chunks. Splits on paragraph
    boundaries when possible to keep semantic content together.
    """
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + max_chars, n)
        if end < n:
            # Prefer a paragraph break, then a sentence break
            split = text.rfind("\n\n", start, end)
            if split == -1 or split <= start + max_chars // 2:
                split = text.rfind(". ", start, end)
            if split != -1 and split > start + max_chars // 2:
                end = split + 2
        chunks.append(text[start:end])
        if end >= n:
            break
        start = max(end - overlap, start + 1)
    return chunks


# ── File-size limits (KI-06) ─────────────────────────────────────────────────

MAX_UPLOAD_BYTES = 15 * 1024 * 1024  # 15 MB


def is_file_size_ok(size_bytes: int | None) -> tuple[bool, str]:
    """
    Returns (ok, message). If size exceeds MAX_UPLOAD_BYTES, returns a
    user-friendly rejection message.
    """
    if size_bytes is None:
        return True, ""
    if size_bytes > MAX_UPLOAD_BYTES:
        mb = size_bytes / (1024 * 1024)
        return False, (
            f"⚠️ File is too large ({mb:.1f} MB).\n"
            f"Maximum supported size is {MAX_UPLOAD_BYTES // (1024 * 1024)} MB."
        )
    return True, ""
