#genai: Sprint 1 / WS-A — JWT issuance & verification for the Web channel.
"""
JWT helpers used by the web channel (and any future SDK clients).

Access tokens are short-lived (1h) stateless JWTs. Refresh tokens are random
opaque strings whose hash is stored in `web_sessions`; verifying a refresh
requires hitting the DB. This split lets us revoke individual devices/sessions
without invalidating every access token in flight.
"""
from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from app.core.config import settings

_ALGO = "HS256"
_ACCESS_TTL_SECONDS = 60 * 60          # 1 hour
_REFRESH_TTL_SECONDS = 60 * 60 * 24 * 30  # 30 days


class TokenError(Exception):
    """Raised when a token is invalid, expired, or malformed."""


def create_access_token(*, user_id: uuid.UUID, org_id: uuid.UUID) -> str:
    """Issue a stateless JWT for a logged-in web user."""
    now = datetime.now(tz=timezone.utc)
    payload = {
        "sub": str(user_id),
        "org_id": str(org_id),
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=_ACCESS_TTL_SECONDS)).timestamp()),
    }
    return jwt.encode(payload, settings.api_secret_key, algorithm=_ALGO)


def decode_access_token(token: str) -> dict:
    """Return the payload or raise TokenError."""
    try:
        payload = jwt.decode(token, settings.api_secret_key, algorithms=[_ALGO])
    except JWTError as exc:
        raise TokenError(str(exc)) from exc
    if payload.get("type") != "access":
        raise TokenError("Wrong token type.")
    return payload


def create_refresh_token() -> tuple[str, str, datetime]:
    """
    Generate a random refresh token. Returns (raw, hash, expires_at).
    Store `hash` in the DB and hand `raw` to the client.
    """
    raw = secrets.token_urlsafe(48)
    h = hash_refresh_token(raw)
    expires_at = datetime.now(tz=timezone.utc) + timedelta(seconds=_REFRESH_TTL_SECONDS)
    return raw, h, expires_at


def hash_refresh_token(raw: str) -> str:
    """SHA-256 hex of the refresh token. Cheap, fixed-length, suitable for lookups."""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
