"""
#genai: Sprint 1 — verify the new auth surface (JWT, OTP, error catalog).

These are pure-Python unit tests that don't require Postgres/Redis/MinIO. They
exercise the pieces of WS-A/WS-B that other workstreams build on top of.
"""
from __future__ import annotations

import os
import time
import uuid

import pytest


def test_otp_store_issues_and_verifies_once():
    """OTP must be 6 digits, verify once, then be unusable."""
    from app.core.otp import OtpStore

    store = OtpStore()
    otp = store.issue("alice@example.com")
    assert otp.isdigit() and len(otp) == 6

    # First verify succeeds...
    assert store.verify("alice@example.com", otp) is True
    # ...second use of the same OTP fails (single-use).
    assert store.verify("alice@example.com", otp) is False


def test_otp_store_rejects_wrong_otp():
    from app.core.otp import OtpStore

    store = OtpStore()
    store.issue("bob@example.com")
    assert store.verify("bob@example.com", "000000") is False


def test_otp_store_locks_out_after_too_many_attempts():
    from app.core.otp import OtpStore

    store = OtpStore()
    real = store.issue("carol@example.com")
    for _ in range(5):
        store.verify("carol@example.com", "000000")
    # Even the right OTP is now blocked.
    assert store.verify("carol@example.com", real) is False


def test_jwt_round_trip():
    from app.core.jwt import create_access_token, decode_access_token

    user_id = uuid.uuid4()
    org_id = uuid.uuid4()
    token = create_access_token(user_id=user_id, org_id=org_id)
    payload = decode_access_token(token)
    assert payload["sub"] == str(user_id)
    assert payload["org_id"] == str(org_id)
    assert payload["type"] == "access"


def test_jwt_decode_rejects_garbage():
    from app.core.jwt import TokenError, decode_access_token

    with pytest.raises(TokenError):
        decode_access_token("not-a-jwt")


def test_jwt_decode_rejects_wrong_type():
    """A refresh token (or any non-access JWT) must not be accepted as access."""
    from jose import jwt

    from app.core.config import settings
    from app.core.jwt import TokenError, decode_access_token

    bad = jwt.encode(
        {"sub": "x", "org_id": "y", "type": "refresh"},
        settings.api_secret_key,
        algorithm="HS256",
    )
    with pytest.raises(TokenError):
        decode_access_token(bad)


def test_refresh_token_hash_is_deterministic():
    from app.core.jwt import create_refresh_token, hash_refresh_token

    raw, h, exp = create_refresh_token()
    assert h == hash_refresh_token(raw)
    assert exp.timestamp() > time.time()


def test_error_catalog_has_all_codes():
    from app.core.error_messages import build_error, http_status_for

    for code in (f"E00{i}" for i in range(1, 10)):
        err = build_error(code)
        assert err.code == code
        assert err.user_message
        assert 400 <= http_status_for(code) < 600
    # E010 too.
    err = build_error("E010")
    assert err.code == "E010"


def test_unknown_code_falls_back_to_E009():
    from app.core.error_messages import build_error

    err = build_error("ZZZ")
    assert err.code == "E009"
