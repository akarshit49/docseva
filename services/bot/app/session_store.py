#genai: Session store for multi-user bot state. Redis-backed with in-memory fallback (KI-16).
#genai: WS-2 — added CONFIRMING_FILE_REPLACE state and soft_reset().
from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field, fields
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class BotState(str, Enum):
    # ── Onboarding ───────────────────────────────────────────────────────────
    ONBOARDING_NAME = "onboarding_name"
    ONBOARDING_COMPANY = "onboarding_company"
    ONBOARDING_PHONE = "onboarding_phone"
    ONBOARDING_GSTIN = "onboarding_gstin"
    ONBOARDING_LOGO = "onboarding_logo"

    # ── Registered user flows ────────────────────────────────────────────────
    IDLE = "idle"
    WAITING_ACTION = "waiting_action"
    WAITING_FORMAT = "waiting_format"
    WAITING_PRICE_ADJUST = "waiting_price_adj"
    WAITING_PRICE_CUSTOM = "waiting_price_cust"
    WAITING_RENAME = "waiting_rename"
    WAITING_BILL_META = "waiting_bill_meta"
    WAITING_BILL_TO_DETAILS = "waiting_bill_to_details"
    WAITING_BILL_HSN = "waiting_bill_hsn"
    WAITING_CATALOG_DETAILS = "waiting_catalog_details"
    WAITING_COMPARISON_COUNT = "waiting_comparison_count"
    WAITING_COMPARISON_FILES = "waiting_comparison_files"
    WAITING_COMPARISON_CUSTOM_COUNT = "waiting_comparison_custom_count"   # KI-07
    WAITING_WATERMARK_MODE = "waiting_watermark_mode"                     # KI-13
    WAITING_WATERMARK_TEXT = "waiting_watermark_text"                     # KI-13

    # ── Sister quotation format management ───────────────────────────────────
    WAITING_SISTER_FORMAT_FILE = "waiting_sister_format_file"
    WAITING_SISTER_FORMAT_NAME = "waiting_sister_format_name"

    # ── Profile update ───────────────────────────────────────────────────────
    UPDATING_PROFILE_FIELD = "updating_profile_field"

    # ── WS-2: File replacement confirmation ──────────────────────────────────
    CONFIRMING_FILE_REPLACE = "confirming_file_replace"

    # ── WS-3: Create Invoice / Quotation / PO from scratch ───────────────────
    CREATING_INVOICE_BILLTO = "creating_invoice_billto"
    CREATING_INVOICE_ITEMS = "creating_invoice_items"
    CREATING_INVOICE_MORE_ITEMS = "creating_invoice_more_items"
    CREATING_INVOICE_HSN = "creating_invoice_hsn"
    CREATING_INVOICE_GST_TYPE = "creating_invoice_gst_type"
    CREATING_INVOICE_GST_CUSTOM = "creating_invoice_gst_custom"
    #genai: KI fix — per-item GST sub-flow + ref-no override
    CREATING_INVOICE_GST_PERITEM = "creating_invoice_gst_peritem"
    CREATING_INVOICE_EDIT_REFNO = "creating_invoice_edit_refno"
    CREATING_INVOICE_CONFIRM = "creating_invoice_confirm"
    CREATING_QUOTATION_BILLTO = "creating_quotation_billto"
    CREATING_QUOTATION_ITEMS = "creating_quotation_items"
    CREATING_QUOTATION_TERMS = "creating_quotation_terms"
    CREATING_QUOTATION_EDIT_REFNO = "creating_quotation_edit_refno"
    CREATING_QUOTATION_CONFIRM = "creating_quotation_confirm"


@dataclass
class UserSession:
    state: BotState = BotState.IDLE
    is_registered: bool = False
    user_id: str = ""
    org_id: str = ""
    company_profile: dict = field(default_factory=dict)

    onboarding_name: str = ""
    onboarding_company: str = ""

    pending_file: Path | None = None
    original_filename: str = ""

    pending_quote_data: Any | None = None
    pending_quote_format: Any | None = None
    pending_quote_stem: str = ""

    pending_sister_template_file: Path | None = None

    pending_bill_data: dict | None = None

    comparison_total: int = 0
    comparison_files: list = field(default_factory=list)

    updating_field: str = ""

    pending_watermark_mode: str = ""    # KI-13: "logo" or "text"

    #genai: WS-2 — temporary storage for file replacement flow
    _replacement_file: Path | None = None
    _replacement_filename: str = ""

    #genai: WS-3 — pending create-from-scratch invoice/quotation/PO data
    pending_create_invoice: dict | None = None
    pending_create_quotation: dict | None = None


# ── Persistence helpers ──────────────────────────────────────────────────────

_PERSISTABLE_FIELDS = {
    "state", "is_registered", "user_id", "org_id", "company_profile",
    "onboarding_name", "onboarding_company",
    "original_filename",
    "pending_quote_stem", "pending_bill_data",
    "comparison_total", "updating_field",
    "pending_watermark_mode",
    #genai: WS-12 — persist multi-file flows + create-from-scratch state across restarts
    "comparison_files",
    "pending_create_invoice",
    "pending_create_quotation",
}


def _session_to_json(session: UserSession) -> str:
    """Serialise the safe-to-persist subset of UserSession to JSON."""
    raw = asdict(session)
    data: dict[str, Any] = {}
    for k, v in raw.items():
        if k not in _PERSISTABLE_FIELDS:
            continue
        if isinstance(v, Enum):
            v = v.value
        data[k] = v
    if isinstance(session.state, Enum):
        data["state"] = session.state.value
    return json.dumps(data)


def _session_from_json(payload: str) -> UserSession:
    data = json.loads(payload)
    session = UserSession()
    valid = {f.name for f in fields(UserSession)}
    for k, v in data.items():
        if k not in valid:
            continue
        if k == "state" and isinstance(v, str):
            try:
                v = BotState(v)
            except ValueError:
                v = BotState.IDLE
        setattr(session, k, v)
    return session


class SessionStore:
    """
    In-memory session store backed by Redis when available.
    The Redis layer survives bot restarts (KI-16). Falls back to in-memory only
    if Redis is unreachable.
    """

    _KEY = "docseva:session:{uid}"
    _TTL = 60 * 60 * 24 * 7   # 7 days

    def __init__(self, redis_url: str | None = None) -> None:
        self._sessions: dict[str, UserSession] = {}
        self._redis = None
        url = redis_url or os.environ.get("REDIS_URL", "")
        if url:
            try:
                import redis  # type: ignore
                client = redis.from_url(url, decode_responses=True, socket_timeout=2)
                client.ping()
                self._redis = client
                logger.info("SessionStore: Redis backend enabled at %s", url)
            except Exception as exc:
                logger.warning("SessionStore: Redis unavailable (%s) — using in-memory only", exc)
                self._redis = None

    def get(self, user_id: str) -> UserSession:
        if user_id in self._sessions:
            return self._sessions[user_id]

        if self._redis is not None:
            try:
                payload = self._redis.get(self._KEY.format(uid=user_id))
                if payload:
                    self._sessions[user_id] = _session_from_json(payload)
                    return self._sessions[user_id]
            except Exception as exc:
                logger.warning("Redis get failed: %s", exc)

        self._sessions[user_id] = UserSession()
        return self._sessions[user_id]

    def reset(self, user_id: str) -> UserSession:
        old = self._sessions.get(user_id)
        session = UserSession()
        if old:
            session.is_registered = old.is_registered
            session.user_id = old.user_id
            session.org_id = old.org_id
            session.company_profile = old.company_profile
        self._sessions[user_id] = session
        self._persist(user_id, session)
        return session

    #genai: WS-2 — reset flow state but keep file and registration
    def soft_reset(self, user_id: str) -> UserSession:
        """Reset flow state but keep file and registration. User can retry another action."""
        session = self._sessions.get(user_id)
        if not session:
            return UserSession()
        session.state = BotState.WAITING_ACTION if session.pending_file else BotState.IDLE
        session.pending_bill_data = None
        session.pending_quote_data = None
        session.pending_quote_format = None
        session.pending_quote_stem = ""
        session.comparison_total = 0
        session.comparison_files = []
        session.updating_field = ""
        session.pending_watermark_mode = ""
        session._replacement_file = None
        session._replacement_filename = ""
        #genai: WS-3 — also clear create-from-scratch state on soft_reset
        session.pending_create_invoice = None
        session.pending_create_quotation = None
        self._persist(user_id, session)
        return session

    def save(self, user_id: str, session: UserSession | None = None) -> None:
        """Explicitly persist a session to Redis (called after mutating state)."""
        if session is None:
            session = self._sessions.get(user_id)
            if session is None:
                return
        else:
            self._sessions[user_id] = session
        self._persist(user_id, session)

    def _persist(self, user_id: str, session: UserSession) -> None:
        if self._redis is None:
            return
        try:
            self._redis.setex(
                self._KEY.format(uid=user_id),
                self._TTL,
                _session_to_json(session),
            )
        except Exception as exc:
            logger.warning("Redis save failed: %s", exc)
