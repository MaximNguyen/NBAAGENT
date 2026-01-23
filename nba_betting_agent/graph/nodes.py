"""Node functions for the betting analysis multi-agent graph.

These are stub implementations that will be replaced with real implementations
in later phases. Each node represents an agent in the workflow.
"""

from datetime import datetime, timedelta

from nba_betting_agent.graph.state import BettingAnalysisState


def is_game_upcoming(game_date: str | None) -> bool:
    """Check if game is upcoming (today or within next 7 days).

    Historical games (past) and far-future games (> 7 days) are filtered out.

    Args:
        game_date: ISO date string (YYYY-MM-DD) or None

    Returns:
        True if game is today <= date <= today + 7 days, False otherwise
    """
    if not game_date:
        return False

    try:
        date = datetime.fromisoformat(game_date).date()
    except (ValueError, AttributeError):
        return False

    today = datetime.now().date()
    max_future = today + timedelta(days=7)

    return today <= date <= max_future


def lines_agent(state: BettingAnalysisState) -> dict:
    """Lines Agent: Scrape and analyze betting lines from sportsbooks.

    Will be implemented in Phase 2 to:
    - Scrape odds from 5 sportsbooks (DraftKings, FanDuel, BetMGM, Caesars, BetRivers)
    - Identify line discrepancies across books
    - Return structured odds data

    Filters out historical games (date < today) and far-future games (date > today + 7 days).

    Args:
        state: Current workflow state

    Returns:
        Partial state update with odds_data and line_discrepancies
    """
    # Check if game is upcoming
    if not is_game_upcoming(state.get("game_date")):
        return {
            "odds_data": [],
            "line_discrepancies": [],
            "errors": ["Lines Agent: game filtered (historical or too far in future)"],
        }

    return {
        "odds_data": [{"book": "stub", "line": "stub"}],
        "line_discrepancies": [],
        "errors": ["Lines Agent: stub implementation"],
    }


def stats_agent(state: BettingAnalysisState) -> dict:
    """Stats Agent: Gather team and player statistics.

    Will be implemented in Phase 3 to:
    - Scrape team stats from Basketball Reference
    - Get player stats and injury reports
    - Return structured performance data

    Filters out historical games (date < today) and far-future games (date > today + 7 days).

    Args:
        state: Current workflow state

    Returns:
        Partial state update with team_stats, player_stats, and injuries
    """
    # Check if game is upcoming
    if not is_game_upcoming(state.get("game_date")):
        return {
            "team_stats": {},
            "player_stats": {},
            "injuries": [],
            "errors": ["Stats Agent: game filtered (historical or too far in future)"],
        }

    return {
        "team_stats": {"stub": "data"},
        "player_stats": {"stub": "data"},
        "injuries": [],
        "errors": ["Stats Agent: stub implementation"],
    }


def analysis_agent(state: BettingAnalysisState) -> dict:
    """Analysis Agent: Calculate probabilities and expected values.

    Will be implemented in Phase 4 to:
    - Use external projections as baseline (FiveThirtyEight, etc.)
    - Apply AI-driven adjustments
    - Calculate expected values for each betting opportunity
    - Filter for positive EV bets

    Args:
        state: Current workflow state with odds_data, team_stats, player_stats

    Returns:
        Partial state update with estimated_probabilities and expected_values
    """
    # Verify parallel nodes completed (both odds_data and team_stats should exist)
    has_odds = bool(state.get("odds_data"))
    has_stats = bool(state.get("team_stats"))

    return {
        "estimated_probabilities": {"stub": 0.5},
        "expected_values": [{"bet": "stub", "ev": 0.0}],
        "errors": [
            f"Analysis Agent: stub implementation (received odds={has_odds}, stats={has_stats})"
        ],
    }


def communication_agent(state: BettingAnalysisState) -> dict:
    """Communication Agent: Format recommendation for user.

    Will be implemented in Phase 5 to:
    - Format analysis results for CLI output
    - Include bet recommendations with confidence levels
    - Provide reasoning and data sources

    Args:
        state: Current workflow state with expected_values

    Returns:
        Partial state update with recommendation string
    """
    # Check if game was filtered
    odds_data = state.get("odds_data", [])
    if not odds_data:
        # Check if it was filtered vs other issue
        errors = state.get("errors", [])
        filtered_errors = [e for e in errors if "filtered" in e.lower()]
        if filtered_errors:
            return {
                "recommendation": "No games found - game date is historical or too far in future (> 7 days)",
                "errors": ["Communication Agent: game was filtered"],
            }

    return {
        "recommendation": "Stub recommendation: No bets analyzed yet",
        "errors": ["Communication Agent: stub implementation"],
    }
