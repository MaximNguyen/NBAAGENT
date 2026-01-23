"""Lines Agent - Fetches odds from The Odds API with circuit breaker resilience.

This module provides the main entry points for the Lines Agent:
- collect_odds: Async function that fetches odds and finds discrepancies
- lines_agent_impl: Sync wrapper for LangGraph node execution

Circuit breaker pattern ensures graceful degradation when API fails.
In future phases, scrapers will be added with the same pattern.
"""

import asyncio
import os

from circuitbreaker import circuit, CircuitBreakerError
from dotenv import load_dotenv

from nba_betting_agent.agents.lines_agent.api.odds_api import OddsAPIClient
from nba_betting_agent.agents.lines_agent.discrepancy import find_discrepancies
from nba_betting_agent.agents.lines_agent.models import GameOdds


# Circuit breaker for API calls
# Opens after 3 failures, recovers after 5 minutes (300 seconds)
# In future phases, scrapers will use the same pattern for fallback
@circuit(failure_threshold=3, recovery_timeout=300)
async def fetch_from_api() -> tuple[list[GameOdds], list[str]]:
    """Fetch odds from The Odds API with circuit breaker protection.

    Returns:
        Tuple of (list of GameOdds, list of warning messages)

    Raises:
        ValueError: If ODDS_API_KEY is not configured
        CircuitBreakerError: If circuit is open due to repeated failures
    """
    client = OddsAPIClient()
    games = await client.get_nba_odds()
    errors = []

    # Warn about low credits
    if client.remaining_credits is not None and client.remaining_credits < 50:
        errors.append(f"Warning: Only {client.remaining_credits} API credits remaining")

    return games, errors


async def collect_odds(game_date: str | None, teams: list[str]) -> dict:
    """Collect odds from all sources with graceful degradation.

    Currently uses The Odds API only. In future phases, scrapers
    will be added with circuit breaker fallback to API.

    Args:
        game_date: ISO date string (YYYY-MM-DD) or None
        teams: List of team names to filter by (empty = all teams)

    Returns:
        Dict with keys:
        - odds_data: List of game odds dicts
        - line_discrepancies: List of discrepancy dicts
        - errors: List of error/warning messages
        - sources_succeeded: List of successful source names
        - sources_failed: List of failed source names
    """
    result = {
        "odds_data": [],
        "line_discrepancies": [],
        "errors": [],
        "sources_succeeded": [],
        "sources_failed": [],
    }

    # Ensure env vars loaded
    load_dotenv()

    # Check if API key is configured before trying
    if not os.getenv("ODDS_API_KEY"):
        result["errors"].append(
            "Lines Agent: ODDS_API_KEY not configured - set in .env file"
        )
        result["sources_failed"].append("odds_api")
        return result

    try:
        games, api_errors = await fetch_from_api()
        result["errors"].extend(api_errors)
        result["sources_succeeded"].append("odds_api")

        # Convert GameOdds to dict for state storage
        for game in games:
            # Filter by teams if specified
            if teams:
                game_teams = {game.home_team.lower(), game.away_team.lower()}
                # Check if any requested team is in the game teams
                team_match = any(
                    any(t.lower() in team_name for team_name in game_teams)
                    for t in teams
                )
                if not team_match:
                    continue

            result["odds_data"].append(game.model_dump(mode="json"))

            # Find discrepancies for this game
            discrepancies = find_discrepancies(game)
            for d in discrepancies:
                result["line_discrepancies"].append({
                    "game_id": d.game_id,
                    "market": d.market,
                    "outcome": d.outcome,
                    "point": d.point,
                    "best_book": d.best_odds_book,
                    "best_odds": d.best_odds,
                    "worst_book": d.worst_odds_book,
                    "worst_odds": d.worst_odds,
                    "implied_diff_pct": d.implied_prob_diff,
                })

    except CircuitBreakerError:
        result["errors"].append(
            "Lines Agent: circuit breaker open, API temporarily unavailable"
        )
        result["sources_failed"].append("odds_api")

    except ValueError as e:
        # API key error (already checked above, but just in case)
        result["errors"].append(f"Lines Agent: {e}")
        result["sources_failed"].append("odds_api")

    except Exception as e:
        result["errors"].append(f"Lines Agent: {type(e).__name__}: {e}")
        result["sources_failed"].append("odds_api")

    return result


def lines_agent_impl(state: dict) -> dict:
    """Lines Agent implementation for LangGraph node.

    Wraps async collect_odds in asyncio.run for sync graph execution.

    Args:
        state: Current workflow state dict

    Returns:
        Dict with partial state update containing:
        - odds_data: List of game odds
        - line_discrepancies: List of discrepancies found
        - errors: List of error/warning messages
    """
    game_date = state.get("game_date")
    teams = state.get("teams", [])

    # Run async function in sync context
    # Use asyncio.get_event_loop().run_until_complete for nested event loop compatibility
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is not None:
        # Already in async context - create new loop in thread
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, collect_odds(game_date, teams))
            result = future.result()
    else:
        result = asyncio.run(collect_odds(game_date, teams))

    return {
        "odds_data": result["odds_data"],
        "line_discrepancies": result["line_discrepancies"],
        "errors": result["errors"],
    }
