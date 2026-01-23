"""Line discrepancy detection across sportsbooks.

Identifies odds differences between bookmakers that may indicate:
1. Value betting opportunities (bookmaker disagrees with market consensus)
2. Arbitrage opportunities (guaranteed profit when sum of implied probs < 1.0)

Discrepancies are flagged when implied probability differs by >= 2% across books.
"""

from dataclasses import dataclass
from collections import defaultdict

from .models import GameOdds
from .normalizer import decimal_to_implied_probability


@dataclass
class LineDiscrepancy:
    """Detected odds discrepancy for a single outcome across bookmakers.

    Attributes:
        game_id: Unique game identifier
        market: Market type (h2h, spreads, totals)
        outcome: Outcome identifier (team name, "Over", "Under", etc.)
        point: Point value for spreads/totals, None for h2h
        best_odds_book: Bookmaker with best (highest) odds
        best_odds: Best decimal odds (highest value = best for bettor)
        worst_odds_book: Bookmaker with worst (lowest) odds
        worst_odds: Worst decimal odds (lowest value)
        implied_prob_diff: Difference in implied probability (percentage points)
        is_arbitrage: True if this is part of an arbitrage opportunity
    """

    game_id: str
    market: str
    outcome: str
    point: float | None
    best_odds_book: str
    best_odds: float
    worst_odds_book: str
    worst_odds: float
    implied_prob_diff: float
    is_arbitrage: bool = False


def find_discrepancies(
    game_odds: GameOdds, min_diff_pct: float = 2.0
) -> list[LineDiscrepancy]:
    """Find odds discrepancies across bookmakers for a game.

    Scans all markets and outcomes, identifying where different sportsbooks
    offer significantly different odds. A discrepancy indicates potential
    value - one book may be mispriced.

    Args:
        game_odds: Complete odds data for a game across all bookmakers
        min_diff_pct: Minimum implied probability difference to report
                      (in percentage points, e.g., 2.0 means 2%)

    Returns:
        List of LineDiscrepancy objects for outcomes meeting the threshold

    Example:
        >>> # DraftKings: Celtics 1.65 (60.6% implied)
        >>> # FanDuel: Celtics 1.75 (57.1% implied)
        >>> # Difference: 3.5 percentage points -> flagged as discrepancy
    """
    discrepancies: list[LineDiscrepancy] = []

    # Collect outcomes by (market, outcome_name, point) across all bookmakers
    # Structure: {(market_key, outcome_name, point): [(book_key, book_title, price), ...]}
    outcomes_by_key: dict[tuple[str, str, float | None], list[tuple[str, str, float]]] = (
        defaultdict(list)
    )

    for bookmaker in game_odds.bookmakers:
        for market in bookmaker.markets:
            for outcome in market.outcomes:
                key = (market.key, outcome.name, outcome.point)
                outcomes_by_key[key].append(
                    (bookmaker.key, bookmaker.title, outcome.price)
                )

    # Analyze each outcome that has prices from multiple bookmakers
    for (market_key, outcome_name, point), book_prices in outcomes_by_key.items():
        if len(book_prices) < 2:
            # Need at least 2 bookmakers to compare
            continue

        # Find best and worst odds
        # Best odds = highest decimal odds (better payout for bettor)
        # Worst odds = lowest decimal odds
        best_book_key, best_book_title, best_price = max(book_prices, key=lambda x: x[2])
        worst_book_key, worst_book_title, worst_price = min(
            book_prices, key=lambda x: x[2]
        )

        # Calculate implied probability difference
        best_implied = decimal_to_implied_probability(best_price)
        worst_implied = decimal_to_implied_probability(worst_price)

        # Difference in percentage points
        # worst_implied > best_implied because lower odds = higher implied prob
        diff_pct = (worst_implied - best_implied) * 100

        if diff_pct >= min_diff_pct:
            discrepancies.append(
                LineDiscrepancy(
                    game_id=game_odds.id,
                    market=market_key,
                    outcome=outcome_name,
                    point=point,
                    best_odds_book=best_book_title,
                    best_odds=best_price,
                    worst_odds_book=worst_book_title,
                    worst_odds=worst_price,
                    implied_prob_diff=round(diff_pct, 2),
                    is_arbitrage=False,
                )
            )

    return discrepancies


def check_arbitrage(outcomes: list[tuple[str, float]]) -> tuple[bool, float]:
    """Check if arbitrage opportunity exists for a set of outcomes.

    Arbitrage exists when the sum of implied probabilities for the best
    available odds on each side is less than 1.0 (100%). This means a
    bettor can guarantee profit regardless of the result.

    Args:
        outcomes: List of (outcome_name, best_decimal_odds) tuples
                  Should include all mutually exclusive outcomes for a market

    Returns:
        Tuple of:
        - bool: True if arbitrage opportunity exists
        - float: Margin percentage (negative = profit, positive = loss)
                 e.g., -2.5 means 2.5% guaranteed profit

    Example:
        >>> # Best odds: Team A @ 2.15 (46.5%), Team B @ 1.95 (51.3%)
        >>> # Total: 97.8% < 100% -> arbitrage exists
        >>> check_arbitrage([("Team A", 2.15), ("Team B", 1.95)])
        (True, -2.2)
    """
    if not outcomes:
        return (False, 0.0)

    # Sum implied probabilities
    total_implied = sum(
        decimal_to_implied_probability(odds) for _, odds in outcomes
    )

    # Convert to percentage and calculate margin
    # margin < 0 means arbitrage exists
    margin_pct = (total_implied - 1.0) * 100

    is_arb = margin_pct < 0

    return (is_arb, round(margin_pct, 2))


def find_best_odds_per_outcome(
    game_odds: GameOdds, market_key: str
) -> dict[str, tuple[str, float, float | None]]:
    """Find best available odds for each outcome in a market.

    Useful for checking arbitrage - need best odds on each side.

    Args:
        game_odds: Complete odds data for a game
        market_key: Market to analyze (h2h, spreads, totals)

    Returns:
        Dict mapping outcome name to (bookmaker_title, best_odds, point)
    """
    best_odds: dict[str, tuple[str, float, float | None]] = {}

    for bookmaker in game_odds.bookmakers:
        for market in bookmaker.markets:
            if market.key != market_key:
                continue

            for outcome in market.outcomes:
                # Create unique key for outcome (name + point for spreads/totals)
                outcome_key = (
                    f"{outcome.name}:{outcome.point}"
                    if outcome.point is not None
                    else outcome.name
                )

                if outcome_key not in best_odds or outcome.price > best_odds[outcome_key][1]:
                    best_odds[outcome_key] = (
                        bookmaker.title,
                        outcome.price,
                        outcome.point,
                    )

    return best_odds
