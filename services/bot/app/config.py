#genai: Bot service configuration from environment.
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class BotSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    telegram_bot_token: str
    openai_api_key: str
    openai_model: str = "gpt-4o-mini"

    api_base_url: str = "http://api:8000"
    api_bot_token: str = "internal_bot_api_token_change_in_prod"

    minio_endpoint: str = "minio:9000"
    #genai: Public endpoint used in presigned URLs — must be reachable by the end user's device.
    # In local dev set to your machine's LAN IP (e.g. 192.168.1.10:9000).
    # In production set to the public MinIO domain (e.g. files.docseva.in).
    # Defaults to minio_endpoint when not set.
    minio_public_endpoint: str = ""
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin_secret_change_in_prod"
    minio_bucket_outputs: str = "docseva-outputs"
    minio_bucket_uploads: str = "docseva-uploads"
    minio_bucket_assets: str = "docseva-assets"
    minio_use_ssl: bool = False
    presigned_url_expiry: int = 86400

    redis_url: str = "redis://redis:6379/0"
    environment: str = "development"
    log_level: str = "INFO"


settings = BotSettings()
