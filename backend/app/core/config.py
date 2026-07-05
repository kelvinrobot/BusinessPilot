
from __future__ import annotations

import base64
import binascii
from functools import lru_cache
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


_PLACEHOLDER_PREFIXES = ("change-me", "change_me", "placeholder", "example", "your-", "sk-your")
_INSECURE_SECRET_PREFIXES = ("change-me", "change_me", "secret", "placeholder", "example")


def _looks_like_placeholder(value: str) -> bool:
    lower = value.lower()
    return any(lower.startswith(p) for p in _PLACEHOLDER_PREFIXES)


def _is_valid_fernet_key(value: str) -> bool:
    """Return True iff *value* is a 32-byte URL-safe base64-encoded Fernet key."""
    try:
        decoded = base64.urlsafe_b64decode(value.encode())
        return len(decoded) == 32
    except (binascii.Error, ValueError):
        return False


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    #  App
    app_name: str = "BusinessPilot AI"
    environment: Literal["development", "staging", "production", "test"] = "development"
    debug: bool = True
    api_v1_prefix: str = "/api/v1"
    frontend_origin: str = "http://localhost:3000"


    secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 14

    encryption_key: str = ""

    #  Database 

    database_url: str = "sqlite+aiosqlite:///./storage/businesspilot.db"

    #  Qwen / DashScope
    qwen_api_key: str = ""

    dashscope_base_url: str = "https://dashscope-intl.aliyuncs.com/api/v1"

    dashscope_compat_url: str = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"

    qwen_chat_model: str = "qwen-plus"
    qwen_embedding_model: str = "text-embedding-v3"



    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/v1/integrations/google/callback"

    #  Storage 
    storage_dir: str = "./storage/documents"

    #  Computed helpers

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        return self.environment == "development"

    @property
    def google_oauth_configured(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret)

    @property
    def db_scheme(self) -> str:
        """Driver-only portion of DATABASE_URL, safe to log (no credentials)."""
        return self.database_url.split("://")[0]

    #  Field validators 

    @field_validator("encryption_key")
    @classmethod
    def validate_fernet_key_format(cls, v: str) -> str:
        """Validate Fernet key format whenever the value looks like a real key.

        Placeholder strings (e.g. "change-me-fernet-key") are allowed here so
        that .env.example works out of the box in development. The production
        guard in model_validator will catch missing / placeholder keys at startup.
        """
        if not v or _looks_like_placeholder(v):
            return v
        if not _is_valid_fernet_key(v):
            raise ValueError(
                "ENCRYPTION_KEY must be a valid 32-byte URL-safe base64 Fernet key. "
                'Generate one: python -c "from cryptography.fernet import Fernet; '
                'print(Fernet.generate_key().decode())"'
            )
        return v

    #  Production guard 

    @model_validator(mode="after")
    def production_checks(self) -> "Settings":
        """Refuse to start in production with insecure or missing configuration."""
        if self.environment != "production":
            return self

        errors: list[str] = []

        if any(self.secret_key.lower().startswith(p) for p in _INSECURE_SECRET_PREFIXES):
            errors.append(
                "SECRET_KEY contains an insecure placeholder value. "
                'Generate one: python -c "import secrets; print(secrets.token_urlsafe(48))"'
            )

        if not self.encryption_key or _looks_like_placeholder(self.encryption_key):
            errors.append(
                "ENCRYPTION_KEY is required in production and must not be a placeholder. "
                'Generate one: python -c "from cryptography.fernet import Fernet; '
                'print(Fernet.generate_key().decode())"'
            )

        if not self.qwen_api_key or _looks_like_placeholder(self.qwen_api_key):
            errors.append("QWEN_API_KEY is required in production.")

        if self.database_url.startswith("sqlite"):
            errors.append(
                "DATABASE_URL points to SQLite in production. "
                "Switch to: postgresql+asyncpg://user:pass@host:5432/dbname"
            )

        if self.debug:
            errors.append("DEBUG must be False in production (set DEBUG=false).")

        if errors:
            bullet_list = "\n  • ".join(errors)
            raise ValueError(
                f"Invalid production configuration — fix the following before starting:"
                f"\n  • {bullet_list}"
            )

        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
