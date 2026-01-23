"""Odds format conversion and normalization utilities.

Converts between different odds formats:
- American: +200, -150 (US betting standard)
- Decimal: 3.0, 1.67 (European/Australian standard)
- Implied Probability: 0.33, 0.60 (mathematical probability)

All internal storage uses decimal format for consistent calculations.
"""


def american_to_decimal(american_odds: int) -> float:
    """Convert American odds to decimal odds.

    American odds use positive and negative values:
    - Positive (+200): Amount won on $100 bet
    - Negative (-200): Amount needed to bet to win $100

    Decimal odds represent total payout per unit staked.

    Args:
        american_odds: American format odds (e.g., +200, -150, +100)

    Returns:
        Decimal odds (always >= 1.0)

    Examples:
        >>> american_to_decimal(200)   # +200
        3.0
        >>> american_to_decimal(-200)  # -200
        1.5
        >>> american_to_decimal(100)   # +100 (even money)
        2.0
        >>> american_to_decimal(-110)  # Standard vig line
        1.9090909090909092
    """
    if american_odds > 0:
        # Positive odds: (odds / 100) + 1
        # +200 means win $200 on $100 = $300 total on $100 = 3.0
        return (american_odds / 100) + 1
    else:
        # Negative odds: (100 / abs(odds)) + 1
        # -200 means risk $200 to win $100 = $300 on $200 = 1.5
        return (100 / abs(american_odds)) + 1


def decimal_to_implied_probability(decimal_odds: float) -> float:
    """Convert decimal odds to implied probability.

    Implied probability is the break-even win rate. Note that
    bookmaker odds include vig (margin), so implied probabilities
    across all outcomes typically sum to > 100%.

    Args:
        decimal_odds: Decimal format odds (must be >= 1.0)

    Returns:
        Implied probability as a decimal (0.0 to 1.0)

    Examples:
        >>> decimal_to_implied_probability(2.0)
        0.5
        >>> round(decimal_to_implied_probability(1.5), 3)
        0.667
        >>> round(decimal_to_implied_probability(3.0), 3)
        0.333
    """
    return 1 / decimal_odds


def normalize_odds(price: float | int, odds_format: str = "american") -> float:
    """Normalize any odds format to decimal.

    This is the primary entry point for odds normalization. All external
    data should pass through this function before storage.

    Args:
        price: The odds value in the specified format
        odds_format: Format of the input odds ("american" or "decimal")

    Returns:
        Decimal odds (always >= 1.0)

    Raises:
        ValueError: If odds_format is not recognized

    Examples:
        >>> normalize_odds(-200, "american")
        1.5
        >>> normalize_odds(200, "american")
        3.0
        >>> normalize_odds(2.5, "decimal")
        2.5
    """
    if odds_format == "decimal":
        return float(price)
    elif odds_format == "american":
        return american_to_decimal(int(price))
    else:
        raise ValueError(
            f"Unknown odds format: '{odds_format}'. "
            "Supported formats: 'american', 'decimal'"
        )
