#genai: Sprint 5 — pytest fixtures for the WhatsApp adapter.
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

# Make `app.*` importable when pytest is invoked from the service folder.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
def _isolate_session_store(monkeypatch):
    """
    Reset the global `SessionStore` between tests so per-user state doesn't
    bleed across cases. We also force the redis client to None so the store
    runs purely in-memory.
    """
    from app import session_store

    session_store._reset_for_tests()
    yield
    session_store._reset_for_tests()


@pytest.fixture
def mock_bsp():
    from app.bsp.mock import MockBsp

    return MockBsp()
