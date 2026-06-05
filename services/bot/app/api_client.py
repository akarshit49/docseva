#genai: HTTP client for the DocSeva API service — auth, quota, document logging.
#genai: WS-9 — added tenacity retry on transient network errors.
#genai: Sprint 2 / WS-D — adds `process()` for the unified /api/v1/process/<feature> endpoint.
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Iterable

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import settings

logger = logging.getLogger(__name__)

_HEADERS = {"X-Bot-Token": settings.api_bot_token}
_BASE = settings.api_base_url.rstrip("/")
_TIMEOUT = 60.0  # processing may be slower than chatty ops

#genai: WS-9 — retry transient network errors up to 3 attempts
_RETRY = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=5),
    retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException)),
    reraise=True,
)


class ApiError(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status = status


def _raise(resp: httpx.Response) -> None:
    if not resp.is_success:
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:
            detail = resp.text
        raise ApiError(resp.status_code, detail)


# ── Auth ──────────────────────────────────────────────────────────────────────

@_RETRY
def register_or_login(
    telegram_user_id: str,
    name: str,
    company_name: str,
    email: str | None = None,
    phone: str | None = None,
) -> dict:
    """Create or fetch user. Returns AuthResponse dict."""
    with httpx.Client(headers=_HEADERS, timeout=_TIMEOUT) as c:
        resp = c.post(
            f"{_BASE}/api/v1/auth/register",
            json={
                "telegram_user_id": str(telegram_user_id),
                "name": name,
                "company_name": company_name,
                "email": email,
                "phone": phone,
            },
        )
    _raise(resp)
    return resp.json()


@_RETRY
def get_quota(telegram_user_id: str) -> dict:
    with httpx.Client(headers=_HEADERS, timeout=_TIMEOUT) as c:
        resp = c.get(f"{_BASE}/api/v1/auth/quota/{telegram_user_id}")
    _raise(resp)
    return resp.json()


@_RETRY
def increment_quota(telegram_user_id: str) -> None:
    with httpx.Client(headers=_HEADERS, timeout=_TIMEOUT) as c:
        resp = c.post(f"{_BASE}/api/v1/auth/quota/{telegram_user_id}/increment")
    _raise(resp)


# ── Company Profile ───────────────────────────────────────────────────────────

@_RETRY
def get_company_profile(telegram_user_id: str) -> dict | None:
    with httpx.Client(headers=_HEADERS, timeout=_TIMEOUT) as c:
        resp = c.get(f"{_BASE}/api/v1/profile/{telegram_user_id}")
    if resp.status_code == 404:
        return None
    _raise(resp)
    return resp.json()


@_RETRY
def update_company_profile(telegram_user_id: str, data: dict) -> dict:
    with httpx.Client(headers=_HEADERS, timeout=_TIMEOUT) as c:
        resp = c.put(f"{_BASE}/api/v1/profile/{telegram_user_id}", json=data)
    _raise(resp)
    return resp.json()


@_RETRY
def upload_company_logo(telegram_user_id: str, file_path: Path) -> dict:
    with open(file_path, "rb") as fh:
        files = {"file": (file_path.name, fh, "image/png")}
        with httpx.Client(headers=_HEADERS, timeout=60.0) as c:
            resp = c.post(f"{_BASE}/api/v1/profile/{telegram_user_id}/logo", files=files)
    _raise(resp)
    return resp.json()


# ── Document Logging ──────────────────────────────────────────────────────────

@_RETRY
def get_documents(telegram_user_id: str, limit: int = 10) -> list:
    """Fetch last N documents for a user."""
    with httpx.Client(headers=_HEADERS, timeout=_TIMEOUT) as c:
        resp = c.get(f"{_BASE}/api/v1/documents/{telegram_user_id}", params={"limit": limit})
    if resp.status_code == 404:
        return []
    _raise(resp)
    return resp.json()


@_RETRY
def log_document(
    telegram_user_id: str,
    feature: str,
    original_filename: str | None = None,
    output_filename: str | None = None,
    output_file_key: str | None = None,
    #genai: WS-12 / WS-6 / WS-3 — new optional fields for input persistence + chaining + typing
    input_file_key: str | None = None,
    source_document_id: str | None = None,
    document_type: str | None = None,
    metadata: dict | None = None,
    status: str = "completed",
    error_message: str | None = None,
) -> dict:
    with httpx.Client(headers=_HEADERS, timeout=_TIMEOUT) as c:
        resp = c.post(
            f"{_BASE}/api/v1/documents/{telegram_user_id}",
            json={
                "feature": feature,
                "original_filename": original_filename,
                "output_filename": output_filename,
                "output_file_key": output_file_key,
                "input_file_key": input_file_key,
                "source_document_id": source_document_id,
                "document_type": document_type,
                "metadata": metadata or {},
                "status": status,
                "error_message": error_message,
            },
        )
    _raise(resp)
    return resp.json()


#genai: WS-3 — atomic counter increment for invoice/po/quotation
@_RETRY
def increment_counter(telegram_user_id: str, counter_type: str) -> int:
    """Increment the named counter and return its new value. counter_type ∈ {invoice, po, quotation}."""
    with httpx.Client(headers=_HEADERS, timeout=_TIMEOUT) as c:
        resp = c.post(
            f"{_BASE}/api/v1/profile/{telegram_user_id}/increment-counter",
            json={"counter_type": counter_type},
        )
    _raise(resp)
    return int(resp.json()["new_value"])


# ── Sister Formats ────────────────────────────────────────────────────────────

@_RETRY
def list_sister_formats(telegram_user_id: str) -> list[dict]:
    """Return saved sister-quotation format templates for the user's org."""
    with httpx.Client(headers=_HEADERS, timeout=_TIMEOUT) as c:
        resp = c.get(f"{_BASE}/api/v1/sister-formats/{telegram_user_id}")
    if resp.status_code == 404:
        return []
    _raise(resp)
    return resp.json()


@_RETRY
def upload_sister_format(telegram_user_id: str, name: str, file_path: Path) -> dict:
    """Upload a new format template. Returns the SisterFormatOut dict."""
    with open(file_path, "rb") as fh:
        files = {"file": (file_path.name, fh, "application/octet-stream")}
        with httpx.Client(headers=_HEADERS, timeout=60.0) as c:
            resp = c.post(
                f"{_BASE}/api/v1/sister-formats/{telegram_user_id}",
                params={"name": name},
                files=files,
            )
    _raise(resp)
    return resp.json()


@_RETRY
def delete_sister_format(telegram_user_id: str, format_id: str) -> None:
    """Delete a sister-quotation format template by ID."""
    with httpx.Client(headers=_HEADERS, timeout=_TIMEOUT) as c:
        resp = c.delete(f"{_BASE}/api/v1/sister-formats/{telegram_user_id}/{format_id}")
    _raise(resp)


@_RETRY
def get_sister_format_file_key(telegram_user_id: str, format_id: str) -> dict:
    """Return the MinIO file_key for a format template."""
    with httpx.Client(headers=_HEADERS, timeout=_TIMEOUT) as c:
        resp = c.get(f"{_BASE}/api/v1/sister-formats/{telegram_user_id}/{format_id}/download")
    _raise(resp)
    return resp.json()


# ── Generic /process/<feature> (Sprint 2 / WS-C) ──────────────────────────────


def _process_headers(telegram_user_id: str) -> dict[str, str]:
    """Headers that identify the *end user* on the channel for the API."""
    return {
        "X-Bot-Token": settings.api_bot_token,
        "X-User-Id": str(telegram_user_id),
        "X-Channel": "telegram",
    }


@_RETRY
def process(
    telegram_user_id: str,
    feature: str,
    file: Path | None = None,
    files: Iterable[Path] | None = None,
    params: dict | None = None,
    format_id: str | None = None,
    mode: str = "final",
) -> dict:
    """
    Call POST /api/v1/process/<feature>.

    Returns the ProcessResponse dict (document_id, output_url, parsed_data, ...).
    Bots use this instead of running processors locally.
    """
    form_data: dict[str, Any] = {"mode": mode}
    if params:
        form_data["params"] = json.dumps(params)
    if format_id:
        form_data["format_id"] = format_id

    multi_files: list[tuple[str, tuple[str, bytes, str]]] = []
    if file is not None:
        multi_files.append(
            ("file", (file.name, file.read_bytes(), "application/octet-stream"))
        )
    if files:
        for p in files:
            multi_files.append(
                ("files", (p.name, p.read_bytes(), "application/octet-stream"))
            )

    with httpx.Client(headers=_process_headers(telegram_user_id), timeout=_TIMEOUT) as c:
        resp = c.post(
            f"{_BASE}/api/v1/process/{feature}",
            data=form_data,
            files=multi_files or None,
        )
    _raise(resp)
    return resp.json()


@_RETRY
def download_url_to(path: Path, url: str) -> Path:
    """Download a presigned URL to `path`. Used after `process()` returns an output_url."""
    with httpx.Client(timeout=_TIMEOUT) as c:
        resp = c.get(url)
    resp.raise_for_status()
    path.write_bytes(resp.content)
    return path
