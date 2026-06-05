"""
#genai: WS-12 — Tests for session-state persistence + recovery.

We can't easily spin up Redis in CI, so we verify:
  * the JSON serialisation/deserialisation helpers round-trip every persistable field,
  * comparison_files survive the round-trip (paths are stored as strings),
  * pending_create_invoice/_quotation survive the round-trip,
  * SessionStore.save() + soft_reset() invariants hold,
  * _ensure_local_file recovery helper correctly reports presence/absence.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.session_store import (
    BotState,
    SessionStore,
    UserSession,
    _PERSISTABLE_FIELDS,
    _session_from_json,
    _session_to_json,
)


class TestJsonRoundTrip:
    def test_empty_session_round_trips(self):
        s = UserSession()
        restored = _session_from_json(_session_to_json(s))
        assert restored.state == BotState.IDLE
        assert restored.is_registered is False

    def test_basic_fields_round_trip(self):
        s = UserSession(
            state=BotState.WAITING_ACTION,
            is_registered=True,
            user_id="user-1",
            org_id="org-1",
            company_profile={"display_name": "Acme"},
            original_filename="foo.docx",
        )
        restored = _session_from_json(_session_to_json(s))
        assert restored.state == BotState.WAITING_ACTION
        assert restored.is_registered is True
        assert restored.user_id == "user-1"
        assert restored.org_id == "org-1"
        assert restored.company_profile == {"display_name": "Acme"}
        assert restored.original_filename == "foo.docx"

    def test_comparison_files_round_trip_with_string_paths(self):
        s = UserSession(
            state=BotState.WAITING_COMPARISON_FILES,
            comparison_total=3,
            comparison_files=[
                {"path": "/tmp/a.pdf", "name": "a.pdf", "minio_key": "inputs/org/123/a.pdf"},
                {"path": "/tmp/b.pdf", "name": "b.pdf", "minio_key": None},
            ],
        )
        restored = _session_from_json(_session_to_json(s))
        assert restored.comparison_total == 3
        assert len(restored.comparison_files) == 2
        assert restored.comparison_files[0]["path"] == "/tmp/a.pdf"
        assert restored.comparison_files[0]["minio_key"] == "inputs/org/123/a.pdf"

    def test_pending_create_invoice_round_trips(self):
        s = UserSession(
            state=BotState.CREATING_INVOICE_CONFIRM,
            pending_create_invoice={
                "bill_to": {"name": "ABC", "address": "Delhi"},
                "items": [{"name": "X", "qty": 1, "unit_cost": 100, "amount": 100, "hsn": "9001"}],
                "gst_rate": 18.0,
                "bill_number": "INV-0001",
                "bill_date": "31-05-2026",
            },
        )
        restored = _session_from_json(_session_to_json(s))
        assert restored.state == BotState.CREATING_INVOICE_CONFIRM
        assert restored.pending_create_invoice["bill_number"] == "INV-0001"
        assert restored.pending_create_invoice["items"][0]["amount"] == 100

    def test_pending_create_quotation_round_trips(self):
        s = UserSession(
            state=BotState.CREATING_QUOTATION_CONFIRM,
            pending_create_quotation={
                "bill_to": {"name": "Q-customer", "address": "X"},
                "items": [{"name": "Service", "qty": 1, "unit_cost": 5000, "amount": 5000, "hsn": ""}],
                "validity_days": 45,
                "payment_terms": "Net 30",
                "delivery_terms": "Within 2 weeks",
                "ref_no": "QT-0007",
                "date": "31/05/2026",
            },
        )
        restored = _session_from_json(_session_to_json(s))
        assert restored.state == BotState.CREATING_QUOTATION_CONFIRM
        assert restored.pending_create_quotation["validity_days"] == 45
        assert restored.pending_create_quotation["payment_terms"] == "Net 30"

    def test_payload_is_valid_json(self):
        """The serialised payload must be valid JSON — Redis stores strings."""
        s = UserSession(
            comparison_files=[{"path": "/tmp/x.pdf", "name": "x.pdf", "minio_key": None}],
            pending_create_invoice={"bill_to": {}, "items": [], "gst_rate": 18.0,
                                    "bill_number": "", "bill_date": ""},
        )
        payload = _session_to_json(s)
        parsed = json.loads(payload)  # would raise if not valid JSON
        assert "comparison_files" in parsed
        assert "pending_create_invoice" in parsed


class TestPersistableFields:
    def test_create_state_fields_are_persistable(self):
        assert "pending_create_invoice" in _PERSISTABLE_FIELDS
        assert "pending_create_quotation" in _PERSISTABLE_FIELDS
        assert "comparison_files" in _PERSISTABLE_FIELDS

    def test_local_paths_are_NOT_persisted(self):
        # These are local-only — file paths don't survive container restarts and
        # are intentionally excluded from persistence.
        assert "pending_file" not in _PERSISTABLE_FIELDS
        assert "pending_sister_template_file" not in _PERSISTABLE_FIELDS
        assert "_replacement_file" not in _PERSISTABLE_FIELDS


class TestSessionStoreInMemory:
    def test_save_and_get_roundtrip(self):
        store = SessionStore(redis_url="")  # in-memory only
        sess = store.get("user-1")
        sess.pending_create_invoice = {"bill_to": {"name": "A"}, "items": [], "gst_rate": 18.0,
                                       "bill_number": "", "bill_date": ""}
        sess.state = BotState.CREATING_INVOICE_BILLTO
        store.save("user-1", sess)
        # In-memory: same instance returned
        again = store.get("user-1")
        assert again is sess

    def test_soft_reset_clears_create_state(self):
        store = SessionStore(redis_url="")
        sess = store.get("user-2")
        sess.pending_create_invoice = {"bill_to": {}, "items": [], "gst_rate": 0.0,
                                       "bill_number": "", "bill_date": ""}
        sess.pending_create_quotation = {"bill_to": {}, "items": [], "validity_days": 30,
                                         "payment_terms": "", "delivery_terms": "",
                                         "ref_no": "", "date": ""}
        sess.state = BotState.CREATING_INVOICE_ITEMS
        store.soft_reset("user-2")
        sess2 = store.get("user-2")
        assert sess2.pending_create_invoice is None
        assert sess2.pending_create_quotation is None
        # No pending_file → goes to IDLE
        assert sess2.state == BotState.IDLE


class TestEnsureLocalFile:
    """`_ensure_local_file` reports whether session.pending_file is still on disk."""

    @pytest.mark.asyncio
    async def test_returns_true_when_file_exists(self, tmp_path: Path):
        from app.bot import _ensure_local_file
        f = tmp_path / "live.pdf"
        f.write_bytes(b"%PDF-1.4\n")
        sess = UserSession(pending_file=f)
        assert await _ensure_local_file(sess) is True

    @pytest.mark.asyncio
    async def test_returns_false_when_file_missing(self, tmp_path: Path):
        from app.bot import _ensure_local_file
        sess = UserSession(pending_file=tmp_path / "gone.pdf")
        assert await _ensure_local_file(sess) is False

    @pytest.mark.asyncio
    async def test_returns_false_when_pending_file_none(self):
        from app.bot import _ensure_local_file
        sess = UserSession(pending_file=None)
        assert await _ensure_local_file(sess) is False
