#genai: Sprint 5 / WS-E — typed settings for the WhatsApp adapter.
"""
Loaded via env vars, validated by pydantic-settings. Sensible defaults so the
service boots in the mock BSP even when no credentials are configured (handy
for local dev + CI).
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class WhatsAppSettings(BaseSettings):
    # ── BSP selection ────────────────────────────────────────────────────────
    # Allowed: 'wati' | 'gupshup' | 'mock'. The mock is in-memory only and
    # exists so we can run the service locally without WATI credentials.
    bsp_provider: str = "mock"

    # ── WATI ─────────────────────────────────────────────────────────────────
    wati_api_base: str = "https://app-server.wati.io/api/v1"
    wati_api_token: str = ""
    wati_verify_token: str = ""  # shared secret WATI sends with every webhook

    # ── Gupshup ──────────────────────────────────────────────────────────────
    gupshup_api_base: str = "https://api.gupshup.io/sm/api/v1"
    gupshup_api_key: str = ""
    gupshup_source_number: str = ""  # our WA number in E.164 (sans +)
    gupshup_app_name: str = ""

    # ── Our WhatsApp business number ────────────────────────────────────────
    whatsapp_number_e164: str = ""  # e.g. +918012345678

    # ── DocSeva API ─────────────────────────────────────────────────────────
    api_base_url: str = "http://api:8000"
    api_bot_token: str = ""  # shared secret matching API's BOT_TOKEN
    request_timeout_seconds: float = 60.0

    # ── Redis (session + dedup) ─────────────────────────────────────────────
    redis_url: str = "redis://redis:6379/2"
    session_ttl_seconds: int = 60 * 60  # 1h idle session

    # ── Behaviour ───────────────────────────────────────────────────────────
    log_level: str = "INFO"
    # Maximum file size we accept (in bytes). Matches the API's cap so we can
    # reject upfront and give a clean error to the user.
    max_upload_bytes: int = 15 * 1024 * 1024

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        # Be permissive with environment names — pull from BOT_TOKEN, API_*, etc.
        extra="ignore",
        env_prefix="WA_",
    )


_settings: WhatsAppSettings | None = None


def get_settings() -> WhatsAppSettings:
    """Lazy singleton so importing this module never fails when env is empty."""
    global _settings
    if _settings is None:
        _settings = WhatsAppSettings()
    return _settings
