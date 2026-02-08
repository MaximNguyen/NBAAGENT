"""Database session factory and engine configuration.

Provides async database session management with automatic connection handling.
Supports both SQLite (development) and PostgreSQL (production) via environment configuration.
"""

import os
import ssl
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def get_database_url() -> str:
    """Get database URL from environment or use SQLite default.

    Checks DATABASE_URL environment variable first. Converts legacy
    postgres:// URLs to postgresql+asyncpg:// for SQLAlchemy 2.0.

    For development (no env var set), uses SQLite with aiosqlite driver.

    Returns:
        Database URL string ready for SQLAlchemy async engine

    Examples:
        - Development: "sqlite+aiosqlite:///./nba_betting.db"
        - Production: "postgresql+asyncpg://user:pass@host/dbname"
    """
    db_url = os.getenv("DATABASE_URL")

    if db_url:
        # Convert legacy Heroku-style postgres:// to postgresql+asyncpg://
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql+asyncpg://", 1)
        return db_url

    # Default to SQLite for development
    return "sqlite+aiosqlite:///./nba_betting.db"


def create_engine() -> AsyncEngine:
    """Create async engine with hardened configuration.

    Applies connection pool limits, SSL for production PostgreSQL,
    and log parameter hiding to prevent resource exhaustion and
    credential leakage.

    Settings are loaded for pool configuration when available (API server).
    Falls back to defaults when Settings unavailable (CLI, migrations).

    Returns:
        Configured async engine with pool limits, SSL, and hidden parameters

    Pool Configuration:
        - pool_pre_ping=True: Verify connections before using
        - pool_recycle=3600: Recycle connections after 1 hour
        - hide_parameters=True: Hide SQL parameters from logs
        - echo=False: Disable SQL echo in production

    PostgreSQL Production:
        - pool_size: Configurable via DB_POOL_SIZE (default 10)
        - max_overflow: Configurable via DB_MAX_OVERFLOW (default 20)
        - SSL: CERT_REQUIRED with hostname verification when environment=production

    SQLite Development:
        - No pool_size/max_overflow (not supported)
        - No SSL (local file database)
    """
    db_url = get_database_url()
    is_postgres = db_url.startswith("postgresql")

    # Base engine kwargs (always applied)
    engine_kwargs: dict[str, Any] = {
        "pool_pre_ping": True,
        "pool_recycle": 3600,
        "hide_parameters": True,
        "echo": False,
    }

    # Add PostgreSQL-specific configuration
    if is_postgres:
        # Try to load Settings for pool configuration
        # Falls back to defaults if Settings unavailable (CLI/migrations context)
        try:
            from nba_betting_agent.api.config import get_settings
            settings = get_settings()
            pool_size = settings.db_pool_size
            max_overflow = settings.db_max_overflow
            environment = settings.environment
        except Exception:
            # Settings unavailable - use defaults
            pool_size = 10
            max_overflow = 20
            environment = "development"

        engine_kwargs["pool_size"] = pool_size
        engine_kwargs["max_overflow"] = max_overflow

        # Add SSL for production PostgreSQL
        if environment == "production":
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = True
            ssl_context.verify_mode = ssl.CERT_REQUIRED
            engine_kwargs["connect_args"] = {"ssl": ssl_context}

    return create_async_engine(db_url, **engine_kwargs)


# Create async engine with hardened configuration
engine = create_engine()

# Create async session factory
AsyncSessionFactory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Allow access to objects after commit
)


@asynccontextmanager
async def get_session() -> AsyncIterator[AsyncSession]:
    """Async context manager for database sessions.

    Automatically commits on success, rolls back on exception,
    and always closes the session.

    Usage:
        async with get_session() as session:
            result = await session.execute(...)
            await session.commit()  # Optional, auto-commits on exit

    Yields:
        AsyncSession for database operations
    """
    session = AsyncSessionFactory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
