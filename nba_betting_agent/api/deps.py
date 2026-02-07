"""Dependency injection for FastAPI routes."""

from typing import Annotated, AsyncIterator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from nba_betting_agent.api.config import Settings, get_settings
from nba_betting_agent.db.session import AsyncSessionFactory


def get_app_settings() -> Settings:
    """Get application settings for FastAPI dependency injection.

    Wraps the cached get_settings() singleton for use with FastAPI's Depends().

    Returns:
        Settings instance with validated configuration
    """
    return get_settings()


# Type alias for Settings dependency injection
SettingsDep = Annotated[Settings, Depends(get_app_settings)]


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """Yield an async database session, auto-closing on completion."""
    session = AsyncSessionFactory()
    try:
        yield session
    finally:
        await session.close()
