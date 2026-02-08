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
        default="",
        description="Bcrypt hash of dashboard password (legacy single-user, optional)"
    )

    # Optional settings with defaults
    jwt_algorithm: str = Field(default="HS256")
    access_token_expire_minutes: int = Field(default=60, ge=5, le=1440)
    refresh_token_expire_days: int = Field(default=7, ge=1, le=30)
    environment: str = Field(default="development")

    # Google OAuth
    google_client_id: str = Field(default="", description="Google OAuth2 client ID")
    google_client_secret: str = Field(default="", description="Google OAuth2 client secret")

    # Email (Resend)
    resend_api_key: str = Field(default="", description="Resend API key for email sending")
    resend_from_email: str = Field(default="noreply@sportagent.lol", description="From address for emails")

    # Frontend
    frontend_url: str = Field(default="http://localhost:5173", description="Frontend URL for email links")

    # Email verification
    email_verification_token_expire_hours: int = Field(default=24, ge=1, le=168)

    # Database pool configuration
    db_pool_size: int = Field(
        default=10,
        ge=5,
        le=50,
        description="SQLAlchemy connection pool size"
    )
    db_max_overflow: int = Field(
        default=20,
        ge=0,
        le=100,
        description="Max overflow connections beyond pool_size"
    )
    db_pool_recycle: int = Field(
        default=3600,
        ge=300,
        le=86400,
        description="Seconds before recycling a connection"
    )

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
