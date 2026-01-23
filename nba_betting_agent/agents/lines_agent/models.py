"""Pydantic models for normalized odds data.

All odds are stored in decimal format for consistent calculations.
Decimal odds represent total payout per unit staked (e.g., 2.0 = $2 total on $1 bet).
"""

import warnings
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, field_validator


class Outcome(BaseModel):
    """Single betting outcome (e.g., team to win, over/under point).

    Attributes:
        name: Outcome identifier (team name, "Over", "Under", etc.)
        price: Decimal odds (always >= 1.0, represents total payout per unit)
        point: Point value for spreads/totals (e.g., -3.5, 220.5), None for h2h
    """

    name: str
    price: float
    point: float | None = None

    @field_validator("price")
    @classmethod
    def validate_decimal_odds(cls, v: float) -> float:
        """Validate that decimal odds are reasonable.

        Args:
            v: The price/odds value to validate

        Returns:
            The validated price

        Raises:
            ValueError: If odds are less than 1.0 (mathematically impossible)
        """
        if v < 1.0:
            raise ValueError(
                f"Decimal odds must be >= 1.0 (got {v}). "
                "Decimal odds represent total payout, so minimum is 1.0 (break even)."
            )
        if v > 100.0:
            warnings.warn(
                f"Suspiciously high decimal odds: {v}. "
                "Verify this isn't American odds that need conversion.",
                UserWarning,
            )
        return v


class Market(BaseModel):
    """Betting market type with outcomes.

    Attributes:
        key: Market type identifier
            - "h2h": Head-to-head (moneyline)
            - "spreads": Point spread betting
            - "totals": Over/under total points
        outcomes: List of possible outcomes for this market
    """

    key: Literal["h2h", "spreads", "totals"]
    outcomes: list[Outcome]


class BookmakerOdds(BaseModel):
    """Odds from a single sportsbook for a game.

    Attributes:
        key: Sportsbook identifier (e.g., "draftkings", "fanduel")
        title: Display name (e.g., "DraftKings", "FanDuel")
        markets: Available markets with their odds
        last_update: When these odds were last updated
    """

    key: str
    title: str
    markets: list[Market]
    last_update: datetime


class GameOdds(BaseModel):
    """Complete odds for a single NBA game across all sportsbooks.

    This is the primary data structure for odds data, containing all
    available betting lines from multiple sportsbooks for comparison.

    Attributes:
        id: Unique game identifier (from source API)
        sport_key: Sport identifier (e.g., "basketball_nba")
        commence_time: Scheduled game start time
        home_team: Home team name
        away_team: Away team name
        bookmakers: List of sportsbooks with their odds for this game
    """

    id: str
    sport_key: str
    commence_time: datetime
    home_team: str
    away_team: str
    bookmakers: list[BookmakerOdds]
