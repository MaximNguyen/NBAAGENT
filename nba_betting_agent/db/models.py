"""SQLAlchemy ORM models for historical NBA data storage.

Defines mutable database models that mirror the frozen dataclasses in ml.data.schema.
Includes converter functions to transform between models and frozen dataclasses.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Index, Boolean, DateTime, Float, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

if TYPE_CHECKING:
    from nba_betting_agent.ml.data.schema import HistoricalGame, HistoricalOdds


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass


class HistoricalGameModel(Base):
    """SQLAlchemy model for completed NBA games.

    Matches the frozen HistoricalGame dataclass but with mutable fields.
    The home_win, spread, and total fields are stored (not computed) to
    avoid database-level computation complexity.

    Indexes:
        - (season, game_date): For efficient season-based queries
        - (home_team, away_team, game_date): For team matchup history
    """

    __tablename__ = "historical_games"

    game_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    game_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    season: Mapped[str] = mapped_column(String(20), nullable=False)
    home_team: Mapped[str] = mapped_column(String(10), nullable=False)
    away_team: Mapped[str] = mapped_column(String(10), nullable=False)
    home_score: Mapped[int] = mapped_column(Integer, nullable=False)
    away_score: Mapped[int] = mapped_column(Integer, nullable=False)
    home_win: Mapped[bool] = mapped_column(Boolean, nullable=False)
    spread: Mapped[float] = mapped_column(Float, nullable=False)
    total: Mapped[float] = mapped_column(Float, nullable=False)

    __table_args__ = (
        Index("ix_historical_games_season_date", "season", "game_date"),
        Index(
            "ix_historical_games_teams_date", "home_team", "away_team", "game_date"
        ),
    )


class HistoricalOddsModel(Base):
    """SQLAlchemy model for betting odds snapshots.

    Matches the frozen HistoricalOdds dataclass but with mutable fields
    and an auto-incrementing primary key.

    Indexes:
        - (game_id, timestamp): For efficient odds history by game
        - (game_date, bookmaker): For bookmaker availability queries
        - (market, outcome, game_date): For market-specific queries
    """

    __tablename__ = "historical_odds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    game_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    game_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    bookmaker: Mapped[str] = mapped_column(String(50), nullable=False)
    market: Mapped[str] = mapped_column(String(20), nullable=False)
    outcome: Mapped[str] = mapped_column(String(50), nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    point: Mapped[float | None] = mapped_column(Float, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    __table_args__ = (
        Index("ix_historical_odds_game_timestamp", "game_id", "timestamp"),
        Index("ix_historical_odds_date_bookmaker", "game_date", "bookmaker"),
        Index("ix_historical_odds_market_outcome_date", "market", "outcome", "game_date"),
    )


# Converter functions between models and frozen dataclasses


def model_to_game_dataclass(model: HistoricalGameModel) -> "HistoricalGame":
    """Convert SQLAlchemy model to frozen HistoricalGame dataclass.

    Args:
        model: HistoricalGameModel instance from database

    Returns:
        Immutable HistoricalGame dataclass
    """
    from nba_betting_agent.ml.data.schema import HistoricalGame

    # Create game with only init fields (home_win, spread, total computed)
    # But we need to override the computed values with stored values
    game = object.__new__(HistoricalGame)
    object.__setattr__(game, "game_id", model.game_id)
    object.__setattr__(game, "game_date", model.game_date)
    object.__setattr__(game, "season", model.season)
    object.__setattr__(game, "home_team", model.home_team)
    object.__setattr__(game, "away_team", model.away_team)
    object.__setattr__(game, "home_score", model.home_score)
    object.__setattr__(game, "away_score", model.away_score)
    object.__setattr__(game, "home_win", model.home_win)
    object.__setattr__(game, "spread", model.spread)
    object.__setattr__(game, "total", model.total)
    return game


def game_dataclass_to_model(dc: "HistoricalGame") -> HistoricalGameModel:
    """Convert frozen HistoricalGame dataclass to SQLAlchemy model.

    Args:
        dc: Immutable HistoricalGame dataclass

    Returns:
        Mutable HistoricalGameModel for database operations
    """
    return HistoricalGameModel(
        game_id=dc.game_id,
        game_date=dc.game_date,
        season=dc.season,
        home_team=dc.home_team,
        away_team=dc.away_team,
        home_score=dc.home_score,
        away_score=dc.away_score,
        home_win=dc.home_win,
        spread=dc.spread,
        total=dc.total,
    )


def model_to_odds_dataclass(model: HistoricalOddsModel) -> "HistoricalOdds":
    """Convert SQLAlchemy model to frozen HistoricalOdds dataclass.

    Args:
        model: HistoricalOddsModel instance from database

    Returns:
        Immutable HistoricalOdds dataclass
    """
    from nba_betting_agent.ml.data.schema import HistoricalOdds

    return HistoricalOdds(
        game_id=model.game_id,
        game_date=model.game_date,
        bookmaker=model.bookmaker,
        market=model.market,
        outcome=model.outcome,
        price=model.price,
        point=model.point,
        timestamp=model.timestamp,
    )


def odds_dataclass_to_model(dc: "HistoricalOdds") -> HistoricalOddsModel:
    """Convert frozen HistoricalOdds dataclass to SQLAlchemy model.

    Args:
        dc: Immutable HistoricalOdds dataclass

    Returns:
        Mutable HistoricalOddsModel for database operations
    """
    return HistoricalOddsModel(
        game_id=dc.game_id,
        game_date=dc.game_date,
        bookmaker=dc.bookmaker,
        market=dc.market,
        outcome=dc.outcome,
        price=dc.price,
        point=dc.point,
        timestamp=dc.timestamp,
    )
