#genai: Sprint 1 / WS-B — channel-neutral, user-facing error copy.
"""
Single source of truth for error codes + messages. Every channel (web,
telegram, whatsapp) consumes the same `ApiError` envelope and just renders
`user_message`. No more "except Exception: pass" — every failure path is
mapped to a code in this module.
"""
from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, status
from pydantic import BaseModel


class ApiError(BaseModel):
    """Channel-neutral error envelope returned by /process/<feature> and friends."""

    code: str
    user_message: str
    retryable: bool = False
    details: dict | None = None


@dataclass(frozen=True)
class _ErrorDef:
    code: str
    user_message: str
    retryable: bool
    http_status: int


_CATALOG: dict[str, _ErrorDef] = {
    "E001": _ErrorDef(
        code="E001",
        user_message="We couldn't read all the data from your document. The format may be unusual.",
        retryable=False,
        http_status=status.HTTP_422_UNPROCESSABLE_ENTITY,
    ),
    "E002": _ErrorDef(
        code="E002",
        user_message="The AI couldn't understand the document. Try a clearer file or different format.",
        retryable=True,
        http_status=status.HTTP_422_UNPROCESSABLE_ENTITY,
    ),
    "E003": _ErrorDef(
        code="E003",
        user_message="The file appears to be empty or corrupted.",
        retryable=False,
        http_status=status.HTTP_400_BAD_REQUEST,
    ),
    "E004": _ErrorDef(
        code="E004",
        user_message="You've used your monthly quota — upgrade to continue.",
        retryable=False,
        http_status=status.HTTP_402_PAYMENT_REQUIRED,
    ),
    "E005": _ErrorDef(
        code="E005",
        user_message="We couldn't reach our server. Please try again in a moment.",
        retryable=True,
        http_status=status.HTTP_503_SERVICE_UNAVAILABLE,
    ),
    "E006": _ErrorDef(
        code="E006",
        user_message="That file is too large. Maximum size is 15 MB.",
        retryable=False,
        http_status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
    ),
    "E007": _ErrorDef(
        code="E007",
        user_message="That file type isn't supported here.",
        retryable=False,
        http_status=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
    ),
    "E008": _ErrorDef(
        code="E008",
        user_message="Processing took too long. Try a smaller file or split it.",
        retryable=True,
        http_status=status.HTTP_504_GATEWAY_TIMEOUT,
    ),
    "E009": _ErrorDef(
        code="E009",
        user_message="Something went wrong. Your file is still loaded — try another action.",
        retryable=True,
        http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    ),
    "E010": _ErrorDef(
        code="E010",
        user_message="We couldn't open your saved format template. Please re-upload it.",
        retryable=False,
        http_status=status.HTTP_422_UNPROCESSABLE_ENTITY,
    ),
}


def build_error(code: str, details: dict | None = None) -> ApiError:
    """Look up `code` and return a channel-neutral `ApiError`."""
    spec = _CATALOG.get(code) or _CATALOG["E009"]
    return ApiError(
        code=spec.code,
        user_message=spec.user_message,
        retryable=spec.retryable,
        details=details,
    )


def raise_api_error(code: str, details: dict | None = None) -> None:
    """Raise FastAPI HTTPException whose body is the `ApiError`."""
    err = build_error(code, details=details)
    spec = _CATALOG.get(code, _CATALOG["E009"])
    raise HTTPException(status_code=spec.http_status, detail=err.model_dump())


def http_status_for(code: str) -> int:
    """Expose the HTTP status mapped to `code` (useful for tests)."""
    return _CATALOG.get(code, _CATALOG["E009"]).http_status
