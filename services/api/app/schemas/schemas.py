#genai: Pydantic request/response schemas for the API.
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, field_validator


# ── Auth / Registration ───────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    telegram_user_id: str
    name: str
    company_name: str
    email: str | None = None
    phone: str | None = None


#genai: Sprint 5 / WS-E — channel-aware registration for bots.
class ChannelRegisterRequest(BaseModel):
    """
    Idempotent register/login keyed by `(channel, handle)`. Used by every bot
    adapter (Telegram, WhatsApp, future). If a `ChannelLink` exists we return
    the existing user; otherwise we provision a new org + user + link.
    """
    channel: str  # 'telegram' | 'whatsapp' | 'email'
    handle: str   # tg user id, E164 phone, or email
    name: str
    company_name: str
    phone: str | None = None
    email: str | None = None
    # Most bots can self-verify the handle (Telegram returns a verified user id;
    # WhatsApp BSPs prove possession of the phone number). Default True.
    verified: bool = True


class UserOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    email: str | None
    phone: str | None
    role: str
    telegram_user_id: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class OrganizationOut(BaseModel):
    id: uuid.UUID
    name: str
    plan: str
    plan_status: str
    docs_used_this_cycle: int
    docs_limit_per_cycle: int
    created_at: datetime

    model_config = {"from_attributes": True}


class AuthResponse(BaseModel):
    user: UserOut
    organization: OrganizationOut
    is_new: bool


# ── Company Profile ───────────────────────────────────────────────────────────

class CompanyProfileUpdate(BaseModel):
    display_name: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    pincode: str | None = None
    gstin: str | None = None
    pan: str | None = None
    phone: str | None = None
    email: str | None = None
    website: str | None = None
    bank_name: str | None = None
    bank_account: str | None = None
    bank_ifsc: str | None = None
    invoice_prefix: str | None = None
    #genai: WS-3/WS-4 — user-configurable prefixes for PO and Quotation numbering
    po_prefix: str | None = None
    quotation_prefix: str | None = None


class CompanyProfileOut(BaseModel):
    display_name: str | None
    address: str | None
    city: str | None
    state: str | None
    pincode: str | None
    gstin: str | None
    pan: str | None
    phone: str | None
    email: str | None
    website: str | None
    bank_name: str | None
    bank_account: str | None
    bank_ifsc: str | None
    logo_key: str | None
    logo_url: str | None = None    # presigned URL, populated by route
    invoice_prefix: str
    invoice_counter: int
    #genai: WS-3/WS-4 — counters exposed for auto-numbering generated docs
    po_prefix: str
    po_counter: int
    quotation_prefix: str
    quotation_counter: int

    model_config = {"from_attributes": True}


#genai: WS-3 — atomic counter increment, returns new value
class IncrementCounterRequest(BaseModel):
    counter_type: str  # 'invoice' | 'po' | 'quotation'


class IncrementCounterResponse(BaseModel):
    counter_type: str
    new_value: int


# ── Documents ─────────────────────────────────────────────────────────────────

class DocumentLogRequest(BaseModel):
    feature: str
    original_filename: str | None = None
    output_filename: str | None = None
    output_file_key: str | None = None
    #genai: WS-12 — original input persisted to MinIO for durability
    input_file_key: str | None = None
    #genai: WS-6 — link to source document for workflow chaining
    source_document_id: str | None = None
    #genai: WS-3 — document_type: 'invoice' | 'quotation' | 'po' | 'sister_quotation' | etc.
    document_type: str | None = None
    metadata: dict[str, Any] = {}
    status: str = "completed"
    error_message: str | None = None


class DocumentOut(BaseModel):
    id: uuid.UUID
    feature: str
    status: str
    original_filename: str | None
    output_filename: str | None
    output_file_key: str | None
    input_file_key: str | None = None
    source_document_id: uuid.UUID | None = None
    document_type: str | None = None
    download_url: str | None = None    # presigned URL
    created_at: datetime
    expires_at: datetime | None

    model_config = {"from_attributes": True}


#genai: WS-8 — full metadata payload, used by the edit flow (route uses model's `doc_metadata`)
class DocumentMetadataOut(BaseModel):
    id: uuid.UUID
    feature: str
    document_type: str | None
    parsed_data: dict[str, Any] = {}
    output_filename: str | None
    output_file_key: str | None
    created_at: datetime


# ── Quota ─────────────────────────────────────────────────────────────────────

class QuotaStatus(BaseModel):
    plan: str
    docs_used: int
    docs_limit: int
    docs_remaining: int
    quota_ok: bool


# ── Sister Formats ────────────────────────────────────────────────────────────

class SisterFormatOut(BaseModel):
    id: uuid.UUID
    name: str
    original_filename: str
    file_key: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Web Auth (Sprint 1 / WS-A) ────────────────────────────────────────────────


class WebOtpRequest(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, v: str) -> str:
        v = (v or "").strip().lower()
        if not v or "@" not in v:
            raise ValueError("Invalid email.")
        return v


class WebOtpVerify(BaseModel):
    email: str
    otp: str
    name: str | None = None
    company_name: str | None = None

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, v: str) -> str:
        return (v or "").strip().lower()

    @field_validator("otp")
    @classmethod
    def _normalize_otp(cls, v: str) -> str:
        v = (v or "").strip()
        if not v.isdigit() or len(v) != 6:
            raise ValueError("OTP must be 6 digits.")
        return v


class WebRefreshRequest(BaseModel):
    refresh_token: str


class WebTokens(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int = 3600


class WebAuthResponse(BaseModel):
    user: UserOut
    organization: OrganizationOut
    tokens: WebTokens
    is_new: bool


class MeResponse(BaseModel):
    user: UserOut
    organization: OrganizationOut
    company_profile: CompanyProfileOut | None = None


# ── Channel Links (Sprint 1 / WS-A) ───────────────────────────────────────────


class ChannelLinkOut(BaseModel):
    id: uuid.UUID
    channel: str
    handle: str
    verified_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ChannelLinkStartRequest(BaseModel):
    """Web → API: ask for a short-lived linking token for a channel."""

    channel: str  # 'telegram' | 'whatsapp'


class ChannelLinkStartResponse(BaseModel):
    channel: str
    token: str
    expires_in: int
    # For telegram, a `https://t.me/<bot>?start=link_<token>` URL the user clicks.
    # For whatsapp, the unique code the user replies with on WA.
    deep_link: str | None = None


class ChannelLinkConfirmRequest(BaseModel):
    """Bot → API: redeem a linking token + bind the handle."""

    token: str
    handle: str
    channel: str | None = None


# ── /process/<feature> envelope (Sprint 1 / WS-C scaffolding) ─────────────────


class ProcessQuota(BaseModel):
    used: int
    limit: int


class ProcessResponse(BaseModel):
    """Channel-neutral response from POST /api/v1/process/<feature>."""

    document_id: uuid.UUID | None = None
    output_filename: str | None = None
    output_url: str | None = None
    input_url: str | None = None
    parsed_data: dict[str, Any] = {}
    needs_confirmation: bool = False
    quota: ProcessQuota | None = None
