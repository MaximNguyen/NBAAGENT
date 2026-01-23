"""Lines Agent - Fetches and normalizes odds from sportsbooks.

This module provides:
- Pydantic models for odds data (GameOdds, BookmakerOdds, Market, Outcome)
- Odds format conversion functions (american_to_decimal, decimal_to_implied_probability)
- Normalization utilities for consistent odds representation
"""

from nba_betting_agent.agents.lines_agent.models import (
    Outcome,
    Market,
    BookmakerOdds,
    GameOdds,
)
from nba_betting_agent.agents.lines_agent.normalizer import (
    american_to_decimal,
    decimal_to_implied_probability,
    normalize_odds,
)

__all__ = [
    # Models
    "Outcome",
    "Market",
    "BookmakerOdds",
    "GameOdds",
    # Normalizer functions
    "american_to_decimal",
    "decimal_to_implied_probability",
    "normalize_odds",
]
