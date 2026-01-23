"""Vig removal utilities for converting bookmaker odds to fair probabilities.

Uses margin-proportional method (industry standard as of 2026):
1. Convert decimal odds to implied probabilities
2. Sum total probability (will be > 1.0 due to vig/margin)
3. Divide each implied probability by total to get fair probabilities (sum to 1.0)
4. Convert fair probabilities back to decimal odds

Example:
    Standard -110/-110 line (1.909 decimal each):
    - Implied probs: [0.5238, 0.5238] = 104.76% (4.76% vig)
    - Fair probs: [0.50, 0.50] = 100%
    - Fair odds: [2.00, 2.00]
"""

import warnings
from typing import Any

from nba_betting_agent.agents.lines_agent.models import Market


def remove_vig(decimal_odds_list: list[float]) -> tuple[list[float], list[float]]:
    """Remove bookmaker vig using margin-proportional method.

    This is the industry standard approach for calculating fair odds from market
    lines. The bookmaker's margin is removed proportionally based on each
    outcome's implied probability.

    Args:
        decimal_odds_list: List of decimal odds for all outcomes in a market.
            Example: [1.909, 1.909] for standard -110/-110 line

    Returns:
        Tuple of (fair_odds_list, fair_probs_list):
            - fair_odds_list: Decimal odds with vig removed (sum of implied probs = 1.0)
            - fair_probs_list: Fair probabilities for each outcome (sum = 1.0)

    Raises:
        ValueError: If fewer than 2 outcomes (can't calculate vig)
        ValueError: If any odds are <= 0 (invalid)

    Example:
        >>> fair_odds, fair_probs = remove_vig([1.909, 1.909])
        >>> fair_odds
        [2.0, 2.0]
        >>> fair_probs
        [0.5, 0.5]
    """
    # Validate input
    if len(decimal_odds_list) < 2:
        raise ValueError(
            "Need at least 2 outcomes to calculate vig. "
            f"Got {len(decimal_odds_list)} outcome(s)."
        )

    for i, odds in enumerate(decimal_odds_list):
        if odds <= 0:
            raise ValueError(
                f"Decimal odds must be positive. Got {odds} at position {i}."
            )
        if odds > 100.0:
            warnings.warn(
                f"Very high decimal odds ({odds}) at position {i}. "
                "Verify this is not American odds that needs conversion.",
                UserWarning,
                stacklevel=2,
            )

    # Step 1: Convert to implied probabilities
    implied_probs = [1.0 / odds for odds in decimal_odds_list]

    # Step 2: Calculate total probability (will be > 1.0 due to vig)
    total_prob = sum(implied_probs)

    # Step 3: Remove vig proportionally
    # Each probability is divided by total to normalize to 1.0
    fair_probs = [prob / total_prob for prob in implied_probs]

    # Step 4: Convert back to decimal odds
    fair_odds = [1.0 / prob for prob in fair_probs]

    return fair_odds, fair_probs


def get_market_vig(decimal_odds_list: list[float]) -> float:
    """Calculate vig percentage for a market.

    Args:
        decimal_odds_list: List of decimal odds for all outcomes

    Returns:
        Vig percentage (e.g., 4.76 for standard -110/-110)

    Raises:
        ValueError: If fewer than 2 outcomes or invalid odds

    Example:
        >>> get_market_vig([1.909, 1.909])
        4.76
    """
    if len(decimal_odds_list) < 2:
        raise ValueError(
            "Need at least 2 outcomes to calculate vig. "
            f"Got {len(decimal_odds_list)} outcome(s)."
        )

    for odds in decimal_odds_list:
        if odds <= 0:
            raise ValueError(f"Decimal odds must be positive. Got {odds}.")

    # Calculate implied probabilities
    implied_probs = [1.0 / odds for odds in decimal_odds_list]
    total_prob = sum(implied_probs)

    # Vig is the excess probability over 100%
    vig_percentage = (total_prob - 1.0) * 100

    return vig_percentage


def calculate_fair_odds(market: Market) -> dict[str, dict[str, Any]]:
    """Calculate fair odds for all outcomes in a market.

    Integrates with Market model from lines_agent to provide complete
    vig removal analysis for a betting market.

    Args:
        market: Market model with outcomes and their odds

    Returns:
        Dictionary mapping outcome name to analysis:
            {
                "outcome_name": {
                    "fair_odds": float,
                    "fair_prob": float,
                    "market_odds": float,
                    "vig_pct": float
                }
            }

    Example:
        >>> from nba_betting_agent.agents.lines_agent.models import Market, Outcome
        >>> market = Market(
        ...     key="h2h",
        ...     outcomes=[
        ...         Outcome(name="Lakers", price=1.909),
        ...         Outcome(name="Celtics", price=1.909)
        ...     ]
        ... )
        >>> result = calculate_fair_odds(market)
        >>> result["Lakers"]["fair_prob"]
        0.5
    """
    # Extract decimal odds from outcomes
    decimal_odds_list = [outcome.price for outcome in market.outcomes]
    outcome_names = [outcome.name for outcome in market.outcomes]

    # Calculate vig percentage
    vig_pct = get_market_vig(decimal_odds_list)

    # Remove vig to get fair odds
    fair_odds_list, fair_probs_list = remove_vig(decimal_odds_list)

    # Build result dictionary
    result: dict[str, dict[str, Any]] = {}
    for i, name in enumerate(outcome_names):
        result[name] = {
            "fair_odds": fair_odds_list[i],
            "fair_prob": fair_probs_list[i],
            "market_odds": decimal_odds_list[i],
            "vig_pct": vig_pct,
        }

    return result
