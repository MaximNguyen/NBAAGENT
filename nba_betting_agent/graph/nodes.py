"""Node functions for the betting analysis multi-agent graph.

Lines Agent, Stats Agent, and Analysis Agent are fully implemented.
Communication Agent is a stub for Phase 5.
"""

from datetime import datetime, timedelta

from nba_betting_agent.agents.lines_agent.agent import lines_agent_impl
from nba_betting_agent.agents.stats_agent.agent import stats_agent_impl
from nba_betting_agent.agents.analysis_agent.agent import analysis_agent_impl
from nba_betting_agent.graph.state import BettingAnalysisState
from nba_betting_agent.cli.formatters import format_opportunities_table
from nba_betting_agent.cli.filters import filter_opportunities
from rich.console import Console


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
    """Lines Agent: Fetch and analyze betting lines from sportsbooks.

    Implemented in Phase 2 to:
    - Fetch odds from The Odds API (primary source)
    - Identify line discrepancies across books
    - Use circuit breaker pattern for resilience

    Filters out historical games (date < today) and far-future games (date > today + 7 days).

    Args:
        state: Current workflow state

    Returns:
        Partial state update with odds_data and line_discrepancies
    """
    # Check if game is upcoming - skip expensive API call for filtered games
    if not is_game_upcoming(state.get("game_date")):
        return {
            "odds_data": [],
            "line_discrepancies": [],
            "errors": ["Lines Agent: game filtered (historical or too far in future)"],
        }

    # Call real implementation
    return lines_agent_impl(state)


def stats_agent(state: BettingAnalysisState) -> dict:
    """Stats Agent: Gather team and player statistics.

    Implemented in Phase 3 to:
    - Fetch team stats from nba_api (game logs, advanced metrics)
    - Get injury reports from ESPN API
    - Cache data aggressively (24h stats, 1h injuries)
    - Gracefully degrade with stale cache on API failure

    Filters out historical games (date < today) and far-future games (date > today + 7 days).

    Args:
        state: Current workflow state

    Returns:
        Partial state update with team_stats, player_stats, and injuries
    """
    # Check if game is upcoming - skip expensive API calls for filtered games
    if not is_game_upcoming(state.get("game_date")):
        return {
            "team_stats": {},
            "player_stats": {},
            "injuries": [],
            "errors": ["Stats Agent: game filtered (historical or too far in future)"],
        }

    # Call real implementation
    return stats_agent_impl(state)


def analysis_agent(state: BettingAnalysisState) -> dict:
    """Analysis Agent: Calculate probabilities and expected values.

    Implemented in Phase 4 to:
    - Remove vig from odds to calculate fair probabilities
    - Generate calibrated probability estimates
    - Calculate expected value for each betting opportunity
    - Detect sharp book edges and reverse line movement
    - Optionally use LLM for matchup analysis

    Args:
        state: Current workflow state with odds_data, team_stats, injuries

    Returns:
        Partial state update with estimated_probabilities and expected_values
    """
    # Verify we have data from parallel agents
    has_odds = bool(state.get("odds_data"))
    has_stats = bool(state.get("team_stats"))

    if not has_odds:
        return {
            "estimated_probabilities": {},
            "expected_values": [],
            "errors": [
                "Analysis Agent: no odds data available (Lines Agent may have failed)"
            ],
        }

    # Call real implementation
    return analysis_agent_impl(state)


def communication_agent(state: BettingAnalysisState) -> dict:
    """Communication Agent: Format recommendation for user.

    Implemented in Phase 5 to:
    - Format analysis results for CLI output
    - Apply user filters (min_ev, confidence, limit)
    - Include bet recommendations with confidence levels
    - Provide reasoning and data sources

    Args:
        state: Current workflow state with opportunities and filter_params

    Returns:
        Partial state update with recommendation string (Rich-formatted)
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
        # No odds data from Lines Agent
        return {
            "recommendation": "No betting lines available - Lines Agent may have failed or no games scheduled",
            "errors": ["Communication Agent: no odds data available"],
        }

    # Get opportunities from state (populated by Analysis Agent in 05-03)
    opportunities = state.get("opportunities", [])

    if not opportunities:
        return {
            "recommendation": "No betting opportunities found - Analysis Agent found no +EV bets",
            "errors": ["Communication Agent: no opportunities to display"],
        }

    # Get filter parameters from state
    filter_params = state.get("filter_params", {})

    # Apply filters
    filtered_opps = filter_opportunities(
        opportunities,
        min_ev=filter_params.get("min_ev"),
        confidence=filter_params.get("confidence"),
        team=filter_params.get("team"),
        market=filter_params.get("market"),
    )

    # Apply limit if specified
    limit = filter_params.get("limit")
    if limit and limit > 0:
        filtered_opps = filtered_opps[:limit]

    # Handle empty results after filtering
    if not filtered_opps:
        active_filters = {k: v for k, v in filter_params.items() if v is not None}
        if active_filters:
            from nba_betting_agent.cli.filters import get_filter_summary, suggest_relaxed_filters
            filter_summary = get_filter_summary(active_filters)
            suggestion = suggest_relaxed_filters(active_filters)
            return {
                "recommendation": f"No opportunities match your filters ({filter_summary}).\n{suggestion}",
                "errors": ["Communication Agent: all opportunities filtered out"],
            }
        else:
            return {
                "recommendation": "No betting opportunities found after filtering",
                "errors": ["Communication Agent: no opportunities after filters"],
            }

    # Format opportunities table
    active_filters = {k: v for k, v in filter_params.items() if v is not None and k != "limit"}
    table = format_opportunities_table(filtered_opps, active_filters=active_filters)

    # Render table to string using Rich console
    console = Console()
    with console.capture() as capture:
        console.print(table)

    recommendation = capture.get()

    return {
        "recommendation": recommendation,
    }
