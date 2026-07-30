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
    # Cache (Redis) - used for QR access-point lookups only in phase 1
    # ==========================
    REDIS_URL: str = Field(default="redis://localhost:6379/0")

    # ==========================
    # Access Gate (QR-based entry)
    # ==========================
    ACCESS_COOKIE_NAME: str = Field(default="curalink_access_token")
    PATIENT_PROFILE_COOKIE_NAME: str = Field(default="curalink_patient_profile")
    ACCESS_COOKIE_SECRET: str = Field(default="CHANGE_ME_IN_PRODUCTION_ENV")
    ACCESS_TOKEN_BYTES: int = Field(default=32)  # length of raw random QR token before encoding

    # ==========================
    # AI Patient Assistant
    # ==========================
    AI_API_URL: str = Field(default="https://integrate.api.nvidia.com/v1/chat/completions")
    AI_API_KEY: str = Field(default="")
    AI_MODEL: str = Field(default="deepseek-ai/deepseek-v4-pro")

    # ==========================
    # Admin JWT Auth
    # ==========================
    JWT_SECRET_KEY: str = Field(default="CHANGE_ME_IN_PRODUCTION_ENV")
    JWT_ALGORITHM: str = Field(default="HS256")
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60 * 12)

# ==========================
    # Bootstrap (one-time super_admin creation via seed script)
    # ==========================
    BOOTSTRAP_SUPER_ADMIN_EMAIL: str = Field(default="")
    BOOTSTRAP_SUPER_ADMIN_PASSWORD: str = Field(default="")

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()