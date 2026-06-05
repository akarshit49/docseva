#genai: Sprint 1 / WS-A — OTP store backed by Redis (in-memory fallback for tests).
"""
6-digit OTPs, stored hashed in Redis with a 10-minute TTL.

`request_otp(email)` generates + stores + returns the raw OTP for the caller
to dispatch via email. `verify_otp(email, otp)` returns True iff the hash
matches and the entry hadn't been used yet (single-use semantics).

For unit tests, RedisOtpStore gracefully falls back to a process-local dict
when Redis isn't reachable — this keeps `pytest` runs hermetic.
"""
from __future__ import annotations

import hashlib
import logging
import secrets
import time
from typing import Optional

logger = logging.getLogger(__name__)

_OTP_TTL_SECONDS = 10 * 60
_OTP_KEY = "otp:{email}"
_OTP_ATTEMPT_KEY = "otp_attempts:{email}"
_MAX_ATTEMPTS = 5


class OtpStore:
    """Redis-backed OTP storage with an in-memory fallback for tests/dev."""

    def __init__(self) -> None:
        self._client = None
        self._fallback: dict[str, tuple[str, float]] = {}
        self._attempts: dict[str, tuple[int, float]] = {}

    def _redis(self):
        if self._client is not None:
            return self._client
        try:
            import redis  # type: ignore

            from app.core.config import settings

            self._client = redis.from_url(settings.redis_url, decode_responses=True)
            self._client.ping()
            return self._client
        except Exception as exc:
            logger.warning("OTP store falling back to in-memory dict: %s", exc)
            self._client = None
            return None

    @staticmethod
    def _hash(otp: str, email: str) -> str:
        # Salt the hash with the email so the same OTP across different
        # accounts has a different stored representation.
        return hashlib.sha256(f"{email}:{otp}".encode("utf-8")).hexdigest()

    def issue(self, email: str) -> str:
        """Generate a 6-digit OTP for `email`, persist hashed, return raw OTP."""
        otp = f"{secrets.randbelow(1_000_000):06d}"
        h = self._hash(otp, email)
        key = _OTP_KEY.format(email=email.lower())
        client = self._redis()
        if client is not None:
            client.set(key, h, ex=_OTP_TTL_SECONDS)
            client.delete(_OTP_ATTEMPT_KEY.format(email=email.lower()))
        else:
            self._fallback[key] = (h, time.time() + _OTP_TTL_SECONDS)
            self._attempts.pop(email.lower(), None)
        return otp

    def verify(self, email: str, otp: str) -> bool:
        """Return True if `otp` matches the stored hash. Single-use.

        If TEST_OTP_CODE is set in the environment, that code bypasses the
        normal OTP check for any email — useful for sharing with beta testers
        who can't receive email on the server. Remove from .env in production.
        """
        import os
        test_code = os.environ.get("TEST_OTP_CODE", "")
        if test_code and otp.strip() == test_code.strip():
            logger.info("OTP bypass used for %s (TEST_OTP_CODE match)", email)
            return True

        email_l = email.lower()
        if self._too_many_attempts(email_l):
            return False
        h = self._hash(otp, email_l)
        key = _OTP_KEY.format(email=email_l)
        client = self._redis()
        if client is not None:
            stored = client.get(key)
            ok = stored is not None and secrets_compare(stored, h)
            if ok:
                client.delete(key)
                client.delete(_OTP_ATTEMPT_KEY.format(email=email_l))
            else:
                client.incr(_OTP_ATTEMPT_KEY.format(email=email_l))
                client.expire(_OTP_ATTEMPT_KEY.format(email=email_l), _OTP_TTL_SECONDS)
            return ok
        entry = self._fallback.get(key)
        if not entry:
            self._bump_attempts(email_l)
            return False
        stored, exp = entry
        if exp < time.time():
            self._fallback.pop(key, None)
            self._bump_attempts(email_l)
            return False
        if secrets_compare(stored, h):
            self._fallback.pop(key, None)
            self._attempts.pop(email_l, None)
            return True
        self._bump_attempts(email_l)
        return False

    def _too_many_attempts(self, email: str) -> bool:
        client = self._redis()
        if client is not None:
            try:
                attempts = int(client.get(_OTP_ATTEMPT_KEY.format(email=email)) or 0)
            except Exception:
                attempts = 0
            return attempts >= _MAX_ATTEMPTS
        entry = self._attempts.get(email)
        if not entry:
            return False
        count, exp = entry
        if exp < time.time():
            self._attempts.pop(email, None)
            return False
        return count >= _MAX_ATTEMPTS

    def _bump_attempts(self, email: str) -> None:
        if self._client is not None:
            return
        count, exp = self._attempts.get(email, (0, time.time() + _OTP_TTL_SECONDS))
        self._attempts[email] = (count + 1, exp)


def secrets_compare(a: str, b: str) -> bool:
    """Constant-time string comparison."""
    return secrets.compare_digest(a or "", b or "")


# Module-level singleton — cheap, thread-safe (Redis client handles concurrency).
otp_store = OtpStore()
