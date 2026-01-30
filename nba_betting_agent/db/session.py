"""Database session factory and engine configuration.

Provides async database session management with automatic connection handling.
Supports both SQLite (development) and PostgreSQL (production) via environment configuration.
"""

import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import (
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


# Create async engine with connection verification
engine = create_async_engine(
    get_database_url(),
    pool_pre_ping=True,  # Verify connections before using
    echo=False,  # Quiet by default, set echo=True for SQL debugging
)

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
