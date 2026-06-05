"""
#genai: Sprint 1/2 — shared pytest fixtures.

We avoid spinning up Postgres/Redis/MinIO in unit tests by swapping in SQLite
(file-backed for SQLAlchemy + JSONB compat) and the in-memory fallbacks built
into our otp/channels stores.

For tests that need the full stack, mark them with `@pytest.mark.integration`.
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def event_loop():
    """Provide a fresh event loop per test for `pytest-asyncio`-style usage."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
