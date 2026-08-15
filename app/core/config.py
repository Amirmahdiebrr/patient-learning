"""
app/core/config.py

Central application configuration using Pydantic v2 settings.
All environment-dependent values must be read here, never scattered
across the codebase.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ==========================
    # App
    # ==========================
    APP_NAME: str = "CuraLink Patient Education Platform"
    APP_ENV: str = Field(default="development")  # development | staging | production
    APP_BASE_URL: str = Field(default="http://localhost:8000")
    DEBUG: bool = Field(default=True)

    # ==========================
    # Database
    # ==========================
    DATABASE_URL: str = Field(
        default="postgresql+psycopg://curalink:curalink@localhost:5432/curalink_edu"
    )
    DB_POOL_SIZE: int = Field(default=10)
    DB_MAX_OVERFLOW: int = Field(default=20)

    # ==========================
    # Cache (Redis)
    # ==========================
    REDIS_URL: str = Field(default="redis://localhost:6379/0")

    # ==========================
    # Access Gate (QR-based entry)
    # ==========================
    ACCESS_COOKIE_NAME: str = Field(default="curalink_access_token")
    PATIENT_PROFILE_COOKIE_NAME: str = Field(default="curalink_patient_profile")
    ACCESS_COOKIE_SECRET: str = Field(default="CHANGE_ME_IN_PRODUCTION_ENV")
    ACCESS_TOKEN_BYTES: int = Field(default=32)

    # ==========================
    # CSRF (double-submit cookie, patient forms + admin panel)
    # ==========================
    CSRF_COOKIE_NAME: str = Field(default="curalink_csrf_token")
    ADMIN_CSRF_COOKIE_NAME: str = Field(default="curalink_admin_csrf_token")
    CSRF_HEADER_NAME: str = Field(default="X-CSRF-Token")

    # ==========================
    # AI Patient Assistant
    # ==========================
    AI_PROVIDER: str = Field(default="gapgpt")  # gapgpt | nvidia | deepseek | openai
    AI_MODEL: str = Field(default="deepseek-v4-pro")
    AI_API_URL: str = Field(default="https://integrate.api.nvidia.com/v1/chat/completions")
    AI_API_KEY: str = Field(default="")

    GAPGPT_API_KEY: str = Field(default="")
    GAPGPT_BASE_URL: str = Field(default="https://api.gapgpt.app/v1")
    NVIDIA_API_KEY: str = Field(default="")
    DEEPSEEK_API_KEY: str = Field(default="")
    OPENAI_API_KEY: str = Field(default="")

    # ==========================
    # Admin JWT Auth
    # ==========================
    JWT_SECRET_KEY: str = Field(default="CHANGE_ME_IN_PRODUCTION_ENV")
    JWT_ALGORITHM: str = Field(default="HS256")
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60 * 12)
    ADMIN_TOKEN_COOKIE_NAME: str = Field(default="curalink_admin_token")

    SESSION_SECRET_KEY: str = Field(default="")

    # ==========================
    # Bootstrap (one-time super_admin creation via seed script)
    # ==========================
    BOOTSTRAP_SUPER_ADMIN_EMAIL: str = Field(default="")
    BOOTSTRAP_SUPER_ADMIN_PASSWORD: str = Field(default="")

    # ==========================
    # Media Upload
    # ==========================
    MEDIA_UPLOAD_DIR: str = Field(default="app/static/uploads")
    MEDIA_MAX_UPLOAD_MB: int = Field(default=25)

    # ==========================
    # Field-level encryption (patient PII: national_id, phone, insurance)
    # ==========================
    ENCRYPTION_KEY: str = Field(default="")
    SEARCH_HASH_KEY: str = Field(default="")

    # ==========================
    # Not yet wired - reserved for future integrations
    # ==========================
    SMS_PROVIDER: str = Field(default="console")
    EMAIL_PROVIDER: str = Field(default="console")
    ZARINPAL_MERCHANT_ID: str = Field(default="")
    ZARINPAL_SANDBOX: bool = Field(default=True)
    SMTP_HOST: str = Field(default="")
    SMTP_PORT: int = Field(default=587)
    SMTP_USER: str = Field(default="")
    SMTP_PASSWORD: str = Field(default="")
    SMTP_FROM: str = Field(default="")
    SMTP_USE_TLS: bool = Field(default=True)

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()