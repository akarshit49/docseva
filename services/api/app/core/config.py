#genai: Centralised settings loaded from environment variables.
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Postgres
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "docseva"
    postgres_user: str = "docseva"
    postgres_password: str = "docseva_secret_change_in_prod"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # MinIO / S3
    minio_endpoint: str = "localhost:9000"
    #genai: WS-1 fix — public endpoint used to sign URLs that clients hit directly
    minio_public_endpoint: str = ""
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin_secret_change_in_prod"
    minio_bucket_uploads: str = "docseva-uploads"
    minio_bucket_outputs: str = "docseva-outputs"
    minio_bucket_assets: str = "docseva-assets"
    minio_use_ssl: bool = False
    presigned_url_expiry: int = 86400   # seconds

    # Security
    api_secret_key: str = "change_this_to_a_long_random_string_in_production"
    api_bot_token: str = "internal_bot_api_token_change_in_prod"

    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # Plans
    free_plan_docs_per_month: int = 20
    starter_plan_docs_per_month: int = 100
    pro_plan_docs_per_month: int = 500
    business_plan_docs_per_month: int = 99999

    # Misc
    document_retention_days: int = 30
    environment: str = "development"
    log_level: str = "INFO"


settings = Settings()
