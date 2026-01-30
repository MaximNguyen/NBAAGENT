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
"""

from nba_betting_agent.db.models import (
    Base,
    HistoricalGameModel,
    HistoricalOddsModel,
    game_dataclass_to_model,
    model_to_game_dataclass,
    model_to_odds_dataclass,
    odds_dataclass_to_model,
)
from nba_betting_agent.db.session import get_database_url, get_session

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
]
