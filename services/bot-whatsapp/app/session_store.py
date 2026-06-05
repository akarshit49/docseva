#genai: Sprint 5 / WS-E — Redis-backed (with in-memory fallback) session store.
"""
Key schema:
  docseva:wa:session:<e164>     → JSON session blob (TTL = WA_SESSION_TTL_SECONDS)
  docseva:wa:dedup:<message_id> → '1' (TTL 24h) — webhook idempotency

Falls back to a plain dict when Redis isn't reachable so unit tests and dev
boxes don't need Redis. Production always wires Redis.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any

try:
    import redis.asyncio as redis  # type: ignore
except ImportError:  # pragma: no cover
    redis = None  # type: ignore

from app.config import get_settings

logger = logging.getLogger(__name__)


class SessionStore:
    def __init__(self) -> None:
        self._memory: dict[str, tuple[float, str]] = {}
        self._dedup_memory: dict[str, float] = {}
        self._client = None
        if redis is not None:
            try:
                self._client = redis.from_url(
                    get_settings().redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                )
            except Exception as exc:  # pragma: no cover
                logger.warning("Redis init failed; using in-memory fallback (%s)", exc)
                self._client = None

    # ── Sessions ────────────────────────────────────────────────────────────

    async def get(self, e164: str) -> dict[str, Any]:
        key = f"docseva:wa:session:{e164}"
        ttl = get_settings().session_ttl_seconds
        if self._client is not None:
            try:
                raw = await self._client.get(key)
                if not raw:
                    return _empty()
                data = json.loads(raw)
                return data if isinstance(data, dict) else _empty()
            except Exception as exc:  # pragma: no cover
                logger.warning("Redis get failed; falling back: %s", exc)
        entry = self._memory.get(key)
        if not entry:
            return _empty()
        expires_at, raw = entry
        if time.time() > expires_at:
            self._memory.pop(key, None)
            return _empty()
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else _empty()
        except Exception:
            return _empty()
        # Unreachable; ttl unused branch keeps linter happy.
        _ = ttl

    async def put(self, e164: str, data: dict[str, Any]) -> None:
        key = f"docseva:wa:session:{e164}"
        ttl = get_settings().session_ttl_seconds
        raw = json.dumps(data, separators=(",", ":"), default=str)
        if self._client is not None:
            try:
                await self._client.set(key, raw, ex=ttl)
                return
            except Exception as exc:  # pragma: no cover
                logger.warning("Redis set failed; falling back: %s", exc)
        self._memory[key] = (time.time() + ttl, raw)

    async def clear(self, e164: str) -> None:
        key = f"docseva:wa:session:{e164}"
        if self._client is not None:
            try:
                await self._client.delete(key)
                return
            except Exception:  # pragma: no cover
                pass
        self._memory.pop(key, None)

    # ── Dedup (webhook idempotency) ─────────────────────────────────────────

    async def seen(self, message_id: str) -> bool:
        if not message_id:
            return False
        key = f"docseva:wa:dedup:{message_id}"
        if self._client is not None:
            try:
                # SET key 1 NX EX 86400 — returns None when key existed.
                created = await self._client.set(key, "1", ex=86400, nx=True)
                return not bool(created)
            except Exception as exc:  # pragma: no cover
                logger.warning("Redis dedup failed; in-memory: %s", exc)
        now = time.time()
        # Sweep old entries (cheap, runs once per call).
        expired = [k for k, exp in self._dedup_memory.items() if exp < now]
        for k in expired:
            self._dedup_memory.pop(k, None)
        if key in self._dedup_memory:
            return True
        self._dedup_memory[key] = now + 86400
        return False


def _empty() -> dict[str, Any]:
    return {"step": "idle"}


_singleton: SessionStore | None = None


def get_session_store() -> SessionStore:
    global _singleton
    if _singleton is None:
        _singleton = SessionStore()
    return _singleton


# Test seam: lets tests reset the global before each run.
def _reset_for_tests() -> None:  # pragma: no cover
    global _singleton
    _singleton = None
