"""Database layer for NBA betting agent.

Provides SQLAlchemy ORM models, async session management, and
converters between mutable models and frozen dataclasses.

Public exports:
    - Base: SQLAlchemy declarative base
    - HistoricalGameModel: ORM model for games
    - HistoricalOddsModel: ORM model for odds
    - get_session: Async context manager for database sessions
    - get_database_url: Database URL resolver
    - Converter functions for models <-> dataclasses
    - get_games_repository: Convenience function for GamesRepository
    - get_odds_repository: Convenience function for OddsRepository
    - init_database: Initialize database schema
"""

from sqlalchemy.ext.asyncio import AsyncSession

from nba_betting_agent.db.models import (
    Base,
    HistoricalGameModel,
    HistoricalOddsModel,
    game_dataclass_to_model,
    model_to_game_dataclass,
    model_to_odds_dataclass,
    odds_dataclass_to_model,
)
from nba_betting_agent.db.repositories.games import GamesRepository
from nba_betting_agent.db.repositories.odds import OddsRepository
from nba_betting_agent.db.session import get_database_url, get_session


def get_games_repository(session: AsyncSession | None = None) -> GamesRepository:
    """Get GamesRepository instance.

    If session is None, repository will use API fallback mode
    (graceful degradation when database unavailable).

    Args:
        session: Optional async database session

    Returns:
        GamesRepository instance
    """
    return GamesRepository(session)


def get_odds_repository(session: AsyncSession | None = None) -> OddsRepository:
    """Get OddsRepository instance.

    If session is None, repository will use cache-only mode
    (no database persistence).

    Args:
        session: Optional async database session

    Returns:
        OddsRepository instance
    """
    return OddsRepository(session)


async def init_database() -> None:
    """Initialize database connection and verify schema.

    Creates tables if they don't exist (for SQLite).
    Should be called at application startup.
    """
    from nba_betting_agent.db.session import engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


__all__ = [
    "Base",
    "HistoricalGameModel",
    "HistoricalOddsModel",
    "get_session",
    "get_database_url",
    "model_to_game_dataclass",
    "game_dataclass_to_model",
    "model_to_odds_dataclass",
    "odds_dataclass_to_model",
    "get_games_repository",
    "get_odds_repository",
    "init_database",
    "GamesRepository",
    "OddsRepository",
]
