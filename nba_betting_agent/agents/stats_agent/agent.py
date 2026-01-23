"""Stats Agent - Gathers NBA statistics and injury data with caching.

This module provides the main entry points for the Stats Agent:
- collect_stats: Async function that fetches team stats and injuries
- stats_agent_impl: Sync wrapper for LangGraph node execution

Data sources:
- nba_api: Team game logs and advanced metrics
- ESPN API: Current injury reports

Caching strategy:
- Team stats: 24-hour TTL, 48-hour stale max
- Injuries: 1-hour TTL, 4-hour stale max
"""

import asyncio
import concurrent.futures

from nba_betting_agent.agents.stats_agent.nba_client import NBAStatsClient
from nba_betting_agent.agents.stats_agent.espn_injuries import ESPNInjuriesClient
from nba_betting_agent.agents.stats_agent.cache import StatsCache


async def collect_stats(
    teams: list[str], odds_data: list[dict] | None = None
) -> dict:
    """Collect team stats and injuries for specified teams.

    Args:
        teams: List of team abbreviations to fetch stats for.
               If empty and odds_data provided, extracts teams from odds.
        odds_data: Optional odds data to extract team names from

    Returns:
        Dict with keys:
        - team_stats: Dict of team abbreviation -> TeamStats dict
        - injuries: List of InjuryReport dicts
        - errors: List of error/warning messages
    """
    result = {
        "team_stats": {},
        "player_stats": {},  # Empty in Phase 3 (team-focused)
        "injuries": [],
        "errors": [],
    }

    # If no teams specified but odds_data available, extract teams
    if not teams and odds_data:
        teams = _extract_teams_from_odds(odds_data)

    if not teams:
        result["errors"].append("Stats Agent: no teams to fetch stats for")
        return result

    # Normalize team names to abbreviations
    team_abbrs = _normalize_team_names(teams)

    if not team_abbrs:
        result["errors"].append(f"Stats Agent: could not resolve team names: {teams}")
        return result

    # Initialize clients with shared cache
    cache = StatsCache()
    nba_client = NBAStatsClient(cache=cache)
    espn_client = ESPNInjuriesClient(cache=cache)

    # Fetch team stats
    for abbr in team_abbrs:
        stats, errors = await nba_client.get_team_stats(abbr)
        result["errors"].extend(errors)

        if stats:
            # Get advanced metrics and merge
            advanced, adv_errors = await nba_client.get_advanced_metrics(abbr)
            result["errors"].extend(adv_errors)

            stats_dict = stats.model_dump(mode="json")
            if advanced:
                stats_dict["advanced"] = advanced.model_dump(mode="json")

            result["team_stats"][abbr] = stats_dict

    # Fetch injuries for all teams
    injuries, injury_errors = await espn_client.get_injuries_for_teams(team_abbrs)
    result["errors"].extend(injury_errors)
    result["injuries"] = [inj.model_dump(mode="json") for inj in injuries]

    return result


def _extract_teams_from_odds(odds_data: list[dict]) -> list[str]:
    """Extract team names from odds data."""
    teams = set()
    for game in odds_data:
        if "home_team" in game:
            teams.add(game["home_team"])
        if "away_team" in game:
            teams.add(game["away_team"])
    return list(teams)


def _normalize_team_names(teams: list[str]) -> list[str]:
    """Convert team names/aliases to standard NBA abbreviations.

    Handles:
    - Full names: "Boston Celtics" -> "BOS"
    - Abbreviations: "BOS" -> "BOS"
    - Common aliases: "celtics" -> "BOS"
    """
    from nba_api.stats.static import teams as nba_teams

    # Build lookup maps
    abbr_map = {}
    for team in nba_teams.get_teams():
        abbr = team["abbreviation"]
        abbr_map[abbr.lower()] = abbr
        abbr_map[team["full_name"].lower()] = abbr
        abbr_map[team["nickname"].lower()] = abbr
        abbr_map[team["city"].lower()] = abbr

    # Add common aliases not in official data
    ALIASES = {
        "sixers": "PHI",
        "blazers": "POR",
        "cavs": "CLE",
        "mavs": "DAL",
        "wolves": "MIN",
        "clips": "LAC",
    }
    abbr_map.update({k.lower(): v for k, v in ALIASES.items()})

    result = []
    for team in teams:
        team_lower = team.lower().strip()
        if team_lower in abbr_map:
            result.append(abbr_map[team_lower])
        else:
            # Try partial match for full names
            for key, abbr in abbr_map.items():
                if team_lower in key or key in team_lower:
                    result.append(abbr)
                    break

    return list(set(result))  # Deduplicate


def stats_agent_impl(state: dict) -> dict:
    """Stats Agent implementation for LangGraph node.

    Wraps async collect_stats in sync execution for graph compatibility.

    Args:
        state: Current workflow state dict

    Returns:
        Dict with partial state update containing:
        - team_stats: Dict of team stats
        - player_stats: Empty dict (Phase 3 is team-focused)
        - injuries: List of injury reports
        - errors: List of error/warning messages
    """
    teams = state.get("teams", [])
    odds_data = state.get("odds_data", [])

    # Run async function in sync context
    # Handle nested event loop (same pattern as Lines Agent)
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is not None:
        # Already in async context - create new loop in thread
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, collect_stats(teams, odds_data))
            result = future.result()
    else:
        result = asyncio.run(collect_stats(teams, odds_data))

    return {
        "team_stats": result["team_stats"],
        "player_stats": result["player_stats"],
        "injuries": result["injuries"],
        "errors": result["errors"],
    }
