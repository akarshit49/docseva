"""
#genai: Unit tests for session store — BotState enum, UserSession defaults, SessionStore CRUD.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ── BotState enum ─────────────────────────────────────────────────────────────

class TestBotState:
    """TC-STATE-*: All expected states exist and are string-compatible."""

    def test_all_critical_states_exist(self):
        from app.session_store import BotState
        expected = [
            "IDLE", "WAITING_ACTION", "WAITING_RENAME", "WAITING_BILL_META",
            "WAITING_BILL_HSN", "WAITING_BILL_TO_DETAILS",
            "WAITING_SISTER_FORMAT_FILE", "WAITING_SISTER_FORMAT_NAME",
            "WAITING_PRICE_ADJUST", "WAITING_PRICE_CUSTOM",
            "WAITING_CATALOG_DETAILS", "UPDATING_PROFILE_FIELD",
            "WAITING_COMPARISON_COUNT", "WAITING_COMPARISON_FILES",
        ]
        state_names = {s.name for s in BotState}
        for name in expected:
            assert name in state_names, f"BotState.{name} is missing"

    def test_states_are_strings(self):
        from app.session_store import BotState
        for state in BotState:
            assert isinstance(state.value, str)

    def test_onboarding_states_have_prefix(self):
        from app.session_store import BotState
        onboarding = [s for s in BotState if s.value.startswith("onboarding_")]
        assert len(onboarding) > 0, "No onboarding states found"


# ── UserSession defaults ──────────────────────────────────────────────────────

class TestUserSession:
    """TC-SESSION-*: Default field values are safe and correct."""

    def test_default_state_is_idle(self):
        from app.session_store import BotState, UserSession
        s = UserSession()
        assert s.state == BotState.IDLE

    def test_pending_file_is_none(self):
        from app.session_store import UserSession
        s = UserSession()
        assert s.pending_file is None

    def test_comparison_files_is_empty_list(self):
        from app.session_store import UserSession
        s = UserSession()
        assert s.comparison_files == []

    def test_company_profile_is_empty_dict(self):
        from app.session_store import UserSession
        s = UserSession()
        assert isinstance(s.company_profile, dict)

    def test_pending_bill_data_is_none(self):
        from app.session_store import UserSession
        s = UserSession()
        assert s.pending_bill_data is None

    def test_pending_sister_template_file_is_none(self):
        from app.session_store import UserSession
        s = UserSession()
        assert s.pending_sister_template_file is None


# ── SessionStore ──────────────────────────────────────────────────────────────

class TestSessionStore:
    """TC-STORE-*: In-memory CRUD for user sessions."""

    @pytest.fixture()
    def store(self):
        from app.session_store import SessionStore
        return SessionStore()

    def test_get_creates_fresh_session(self, store):
        s = store.get("user1")
        from app.session_store import BotState
        assert s.state == BotState.IDLE

    def test_get_returns_same_object(self, store):
        s1 = store.get("user1")
        s2 = store.get("user1")
        assert s1 is s2

    def test_reset_clears_state(self, store):
        from app.session_store import BotState
        s = store.get("user1")
        s.state = BotState.WAITING_BILL_META
        store.reset("user1")
        s2 = store.get("user1")
        assert s2.state == BotState.IDLE

    def test_reset_clears_pending_file(self, store, tmp_path):
        s = store.get("user1")
        s.pending_file = tmp_path / "test.docx"
        store.reset("user1")
        assert store.get("user1").pending_file is None

    def test_different_users_isolated(self, store):
        from app.session_store import BotState
        store.get("user_a").state = BotState.WAITING_BILL_META
        assert store.get("user_b").state == BotState.IDLE

    def test_reset_unknown_user_is_safe(self, store):
        # Should not raise
        store.reset("never_seen_user")
