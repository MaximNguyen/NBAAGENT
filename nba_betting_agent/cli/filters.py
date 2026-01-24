"""Filter and sort logic for betting opportunities.

Provides filtering by EV, confidence, team, and market type,
plus sorting capabilities and filter summary helpers.
"""

from typing import Optional

from nba_betting_agent.agents.analysis_agent.agent import BettingOpportunity


def filter_opportunities(
    opportunities: list[BettingOpportunity],
    min_ev: Optional[float] = None,
    max_ev: Optional[float] = None,
    confidence: Optional[str] = None,
    team: Optional[str] = None,
    market: Optional[str] = None,
) -> list[BettingOpportunity]:
    """Filter betting opportunities by criteria.

    All filters are optional (None = no filter).
    Combines all filters with AND logic.

    Args:
        opportunities: List of BettingOpportunity objects
        min_ev: Minimum EV percentage threshold (inclusive)
        max_ev: Maximum EV percentage threshold (inclusive, for safety caps)
        confidence: Confidence level to match (case-insensitive)
        team: Team code that must appear in matchup (case-insensitive)
        market: Market type to match (h2h, spreads, totals)

    Returns:
        Filtered list of opportunities (may be empty)
    """
    filtered = opportunities

    # Filter by min EV
    if min_ev is not None:
        filtered = [opp for opp in filtered if opp.ev_pct >= min_ev]

    # Filter by max EV
    if max_ev is not None:
        filtered = [opp for opp in filtered if opp.ev_pct <= max_ev]

    # Filter by confidence
    if confidence is not None:
        confidence_lower = confidence.lower()
        filtered = [
            opp for opp in filtered if opp.confidence.lower() == confidence_lower
        ]

    # Filter by team
    if team is not None:
        team_upper = team.upper()
        filtered = [opp for opp in filtered if team_upper in opp.matchup.upper()]

    # Filter by market
    if market is not None:
        filtered = [opp for opp in filtered if opp.market == market]

    return filtered


def sort_opportunities(
    opportunities: list[BettingOpportunity],
    sort_by: str = "ev_pct",
    reverse: bool = True,
) -> list[BettingOpportunity]:
    """Sort betting opportunities by specified field.

    Args:
        opportunities: List of BettingOpportunity objects
        sort_by: Field name to sort by (ev_pct, kelly_bet_pct, our_prob, market_odds)
        reverse: True for descending (default), False for ascending

    Returns:
        Sorted list of opportunities
    """
    # Use getattr with fallback for safety
    return sorted(
        opportunities,
        key=lambda x: getattr(x, sort_by, 0),
        reverse=reverse,
    )


def get_filter_summary(filters: dict) -> str:
    """Generate human-readable filter summary.

    Args:
        filters: Dict of active filters

    Returns:
        Filter summary string (e.g., "min_ev=5.0%, confidence=high")
        Returns empty string if no filters active
    """
    parts = []

    if filters.get("min_ev") is not None:
        parts.append(f"min_ev={filters['min_ev']}%")

    if filters.get("max_ev") is not None:
        parts.append(f"max_ev={filters['max_ev']}%")

    if filters.get("confidence"):
        parts.append(f"confidence={filters['confidence']}")

    if filters.get("team"):
        parts.append(f"team={filters['team']}")

    if filters.get("market"):
        parts.append(f"market={filters['market']}")

    return ", ".join(parts)


def suggest_relaxed_filters(filters: dict) -> str:
    """Suggest how to relax filters when results are empty.

    Args:
        filters: Dict of active filters

    Returns:
        Helpful suggestion string
    """
    suggestions = []

    if filters.get("min_ev"):
        suggestions.append("lower --min-ev")

    if filters.get("confidence"):
        suggestions.append("remove --confidence filter")

    if filters.get("team"):
        suggestions.append("try a different --team")

    if filters.get("market"):
        suggestions.append("try a different --market")

    if not suggestions:
        return "Try adjusting your filters or checking back later for new opportunities"

    return "Try: " + " or ".join(suggestions)
