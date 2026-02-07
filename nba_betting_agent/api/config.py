"""Configuration management for NBA Betting Agent API.

Settings are loaded from environment variables using pydantic-settings.
Required secrets cause immediate application crash if missing (fail-fast startup).
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Required secrets (app crashes at startup if missing):
    - JWT_SECRET_KEY: Secret key for JWT signing (min 32 chars)
    - DASHBOARD_PASSWORD_HASH: Bcrypt hash of dashboard password

    Optional settings (have defaults):
    - JWT_ALGORITHM: Algorithm for JWT signing (default: HS256)
    - ACCESS_TOKEN_EXPIRE_MINUTES: Access token lifetime (default: 60)
    - REFRESH_TOKEN_EXPIRE_DAYS: Refresh token lifetime (default: 7)
    - ENVIRONMENT: Runtime environment (default: development)
    """

    # Required secrets - app crashes if missing
    jwt_secret_key: str = Field(
        ...,
        min_length=32,
        description="Secret key for JWT signing. Generate with: openssl rand -hex 32"
    )
    dashboard_password_hash: str = Field(
        ...,
        description="Bcrypt hash of dashboard password"
    )

    # Optional settings with defaults
    jwt_algorithm: str = Field(default="HS256")
    access_token_expire_minutes: int = Field(default=60, ge=5, le=1440)
    refresh_token_expire_days: int = Field(default=7, ge=1, le=30)
    environment: str = Field(default="development")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance (singleton).

    Cached to avoid re-reading environment variables on every call.
    Settings are loaded once at startup and reused throughout application lifetime.

    Returns:
        Settings instance with validated configuration

    Raises:
        ValidationError: If required secrets are missing or invalid
    """
    return Settings()
