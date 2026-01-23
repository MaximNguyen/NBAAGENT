"""Sharp vs soft book comparison for detecting market inefficiencies.

Sharp books (Pinnacle, Circa, Bookmaker) set efficient lines close to true
probabilities. Soft books (DraftKings, FanDuel, etc.) cater to recreational
bettors and may offer mispriced lines.

Comparing soft book odds to sharp book odds reveals potential value opportunities.
If a soft book offers better odds than the sharp market price, it indicates
a potential +EV betting opportunity.
"""

from dataclasses import dataclass
from typing import Optional

from nba_betting_agent.agents.analysis_agent.vig_removal import remove_vig
from nba_betting_agent.agents.lines_agent.models import GameOdds

# Sharp books (efficient markets, treat as "true" odds)
SHARP_BOOKS = {"pinnacle", "circa", "bookmaker"}

# Soft books (recreational, potentially mispriced)
SOFT_BOOKS = {"draftkings", "fanduel", "betmgm", "caesars", "pointsbet"}


@dataclass
class SharpSoftComparison:
    """Comparison between sharp and soft book odds for an outcome.

    Attributes:
        sharp_book: Sharp book used as reference (e.g., "pinnacle")
        soft_book: Soft book being compared (e.g., "draftkings")
        outcome_name: Name of the outcome (e.g., "Boston Celtics")
        sharp_odds: Sharp book decimal odds
        soft_odds: Soft book decimal odds
        sharp_fair_prob: Sharp book fair probability (vig removed)
        soft_implied_prob: Soft book implied probability (with vig)
        edge_pct: Edge percentage (positive = soft book more generous)
        is_value: True if soft book offers better odds than sharp
    """

    sharp_book: str
    soft_book: str
    outcome_name: str
    sharp_odds: float
    soft_odds: float
    sharp_fair_prob: float
    soft_implied_prob: float
    edge_pct: float
    is_value: bool


def compare_sharp_soft(
    sharp_odds: list[float],
    soft_odds: list[float],
    outcome_names: list[str],
    sharp_book: str = "sharp",
    soft_book: str = "soft",
) -> list[SharpSoftComparison]:
    """Compare sharp book odds vs soft book odds to find edges.

    Args:
        sharp_odds: List of decimal odds from sharp book for all outcomes
        soft_odds: List of decimal odds from soft book for all outcomes
        outcome_names: Names of outcomes (e.g., ["Home", "Away"])
        sharp_book: Sharp book identifier (for labeling)
        soft_book: Soft book identifier (for labeling)

    Returns:
        List of SharpSoftComparison objects, one per outcome

    Example:
        >>> # Pinnacle: -108/-108, DraftKings: -105/-115
        >>> comparisons = compare_sharp_soft(
        ...     sharp_odds=[1.926, 1.926],
        ...     soft_odds=[1.952, 1.870],
        ...     outcome_names=["Home", "Away"]
        ... )
        >>> comparisons[0].edge_pct  # Home has positive edge
        1.35
    """
    # Calculate fair odds for sharp book (remove vig)
    sharp_fair_odds, sharp_fair_probs = remove_vig(sharp_odds)

    # Calculate implied probabilities for soft book (keep vig - that's what bettor pays)
    soft_implied_probs = [1.0 / odds for odds in soft_odds]

    comparisons = []
    for i, name in enumerate(outcome_names):
        # Edge calculation:
        # Positive edge = soft book offers better price than sharp fair odds
        # Compare soft implied prob vs sharp fair prob
        # Lower implied prob = better odds for bettor
        edge_pct = ((sharp_fair_probs[i] - soft_implied_probs[i]) / sharp_fair_probs[i]) * 100

        is_value = edge_pct > 0  # Soft book offers better than sharp fair

        comparisons.append(
            SharpSoftComparison(
                sharp_book=sharp_book,
                soft_book=soft_book,
                outcome_name=name,
                sharp_odds=sharp_odds[i],
                soft_odds=soft_odds[i],
                sharp_fair_prob=sharp_fair_probs[i],
                soft_implied_prob=soft_implied_probs[i],
                edge_pct=edge_pct,
                is_value=is_value,
            )
        )

    return comparisons


def find_soft_book_edges(
    game_odds: GameOdds,
    market_key: str = "h2h",
    min_edge_pct: float = 1.0,
) -> list[SharpSoftComparison]:
    """Find value opportunities in soft books compared to sharp books.

    Args:
        game_odds: Complete odds for a game from all bookmakers
        market_key: Market type to analyze ("h2h", "spreads", or "totals")
        min_edge_pct: Minimum edge percentage to return (default 1.0%)

    Returns:
        List of edges found, sorted by edge_pct descending.
        Returns empty list if no sharp book available.

    Example:
        >>> edges = find_soft_book_edges(game_odds, market_key="h2h", min_edge_pct=1.0)
        >>> for edge in edges:
        ...     print(f"{edge.outcome_name} at {edge.soft_book}: {edge.edge_pct:.2f}% edge")
    """
    # Find first available sharp book
    sharp_bookmaker = None
    for bookmaker in game_odds.bookmakers:
        if bookmaker.key in SHARP_BOOKS:
            sharp_bookmaker = bookmaker
            break

    if not sharp_bookmaker:
        # No sharp book available - can't compare
        return []

    # Find the requested market in sharp book
    sharp_market = None
    for market in sharp_bookmaker.markets:
        if market.key == market_key:
            sharp_market = market
            break

    if not sharp_market:
        # Sharp book doesn't have this market
        return []

    # Extract sharp odds
    sharp_odds = [outcome.price for outcome in sharp_market.outcomes]
    outcome_names = [outcome.name for outcome in sharp_market.outcomes]

    # Compare against each soft book
    all_comparisons = []
    for bookmaker in game_odds.bookmakers:
        if bookmaker.key not in SOFT_BOOKS:
            continue

        # Find matching market
        soft_market = None
        for market in bookmaker.markets:
            if market.key == market_key:
                soft_market = market
                break

        if not soft_market:
            continue

        # Extract soft odds (match order to sharp odds by outcome name)
        soft_odds_dict = {outcome.name: outcome.price for outcome in soft_market.outcomes}

        # Match outcomes between sharp and soft books
        matched_soft_odds = []
        matched_outcome_names = []
        for name in outcome_names:
            if name in soft_odds_dict:
                matched_soft_odds.append(soft_odds_dict[name])
                matched_outcome_names.append(name)

        if len(matched_soft_odds) != len(sharp_odds):
            # Outcomes don't match - skip this soft book
            continue

        # Compare
        comparisons = compare_sharp_soft(
            sharp_odds=sharp_odds,
            soft_odds=matched_soft_odds,
            outcome_names=matched_outcome_names,
            sharp_book=sharp_bookmaker.key,
            soft_book=bookmaker.key,
        )

        all_comparisons.extend(comparisons)

    # Filter by minimum edge and sort descending
    edges = [c for c in all_comparisons if c.edge_pct >= min_edge_pct]
    edges.sort(key=lambda x: x.edge_pct, reverse=True)

    return edges


def get_best_odds(
    game_odds: GameOdds,
    market_key: str,
    outcome_name: str,
) -> tuple[str, float]:
    """Find bookmaker offering best odds for a specific outcome.

    Args:
        game_odds: Complete odds for a game
        market_key: Market type ("h2h", "spreads", "totals")
        outcome_name: Outcome to find best odds for

    Returns:
        Tuple of (bookmaker_key, best_odds)
        Returns ("", 0.0) if outcome not found

    Example:
        >>> book, odds = get_best_odds(game_odds, "h2h", "Boston Celtics")
        >>> print(f"Best odds at {book}: {odds}")
    """
    best_bookmaker = ""
    best_odds = 0.0

    for bookmaker in game_odds.bookmakers:
        # Find market
        market = None
        for m in bookmaker.markets:
            if m.key == market_key:
                market = m
                break

        if not market:
            continue

        # Find outcome
        for outcome in market.outcomes:
            if outcome.name == outcome_name:
                if outcome.price > best_odds:
                    best_odds = outcome.price
                    best_bookmaker = bookmaker.key
                break

    return best_bookmaker, best_odds
