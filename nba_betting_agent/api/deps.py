"""Dependency injection for FastAPI routes."""

from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from nba_betting_agent.db.session import AsyncSessionFactory


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """Yield an async database session, auto-closing on completion."""
    session = AsyncSessionFactory()
    try:
        yield session
    finally:
        await session.close()
