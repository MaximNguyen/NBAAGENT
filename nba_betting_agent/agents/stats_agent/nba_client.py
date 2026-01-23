"""NBA API client with retry logic, circuit breaker, and cache integration.

Fetches team statistics from nba_api with resilience patterns matching Lines Agent.
Handles rate limiting, timeouts, and API failures gracefully by falling back to cached data.
"""

import asyncio
from datetime import datetime

import pandas as pd
from circuitbreaker import circuit
from nba_api.stats.endpoints import teamestimatedmetrics, teamgamelog
from nba_api.stats.static import teams as nba_teams
from tenacity import retry, stop_after_attempt, wait_exponential

from nba_betting_agent.agents.stats_agent.cache import StatsCache
from nba_betting_agent.agents.stats_agent.models import (
    HomeAwayRecord,
    HomeAwayStats,
    Last10Stats,
    TeamAdvancedMetrics,
    TeamBasicStats,
    TeamRecord,
    TeamStats,
)


def get_current_season() -> str:
    """Return current NBA season in '2025-26' format.

    NBA season starts in October, so:
    - Oct-Dec: Current year is start of season
    - Jan-Sep: Previous year is start of season

    Returns:
        Season string like "2025-26"
    """
    now = datetime.now()
    # NBA season starts in October
    if now.month >= 10:
        return f"{now.year}-{str(now.year + 1)[-2:]}"
    return f"{now.year - 1}-{str(now.year)[-2:]}"


def get_team_id(team_abbr: str) -> str | None:
    """Get NBA team ID from abbreviation.

    Args:
        team_abbr: Team abbreviation (e.g., "BOS", "LAL")

    Returns:
        Team ID as string or None if not found
    """
    team = nba_teams.find_team_by_abbreviation(team_abbr.upper())
    return str(team["id"]) if team else None


# Build reverse mapping for name lookups
TEAM_ABBR_BY_ID = {str(t["id"]): t["abbreviation"] for t in nba_teams.get_teams()}


class NBAStatsClient:
    """Client for fetching NBA stats with caching and resilience.

    Uses circuit breaker pattern (3 failures, 300s recovery) and retry logic
    (3 attempts, exponential backoff) to handle API failures gracefully.
    Falls back to cached data when API is unavailable.

    Example:
        client = NBAStatsClient()
        stats, errors = await client.get_team_stats("BOS")
        if stats:
            print(f"{stats.name}: {stats.record.wins}-{stats.record.losses}")
        if stats and stats.is_stale:
            print("Warning: Using stale cache data")
    """

    def __init__(self, cache: StatsCache | None = None):
        """Initialize NBA stats client.

        Args:
            cache: StatsCache instance (creates default if None)
        """
        self._cache = cache or StatsCache()
        self._season = get_current_season()

    @circuit(failure_threshold=3, recovery_timeout=300)
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=30))
    def _fetch_team_game_log(self, team_id: str) -> pd.DataFrame:
        """Fetch team game log with retry and circuit breaker.

        Args:
            team_id: NBA team ID (10-digit format)

        Returns:
            DataFrame with team game log data

        Raises:
            Various exceptions from nba_api on failure
        """
        endpoint = teamgamelog.TeamGameLog(
            team_id=team_id,
            season=self._season,
            season_type_all_star="Regular Season"
        )
        return endpoint.get_data_frames()[0]

    @circuit(failure_threshold=3, recovery_timeout=300)
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=30))
    def _fetch_all_team_metrics(self) -> pd.DataFrame:
        """Fetch estimated metrics for all teams.

        Returns:
            DataFrame with advanced metrics for all teams

        Raises:
            Various exceptions from nba_api on failure
        """
        endpoint = teamestimatedmetrics.TeamEstimatedMetrics(
            league_id="00",
            season=self._season,
            season_type="Regular Season"
        )
        return endpoint.get_data_frames()[0]

    async def get_team_stats(self, team_abbr: str) -> tuple[TeamStats | None, list[str]]:
        """Get stats for a single team with cache fallback.

        Tries to fetch live data from nba_api, falls back to cache on failure.
        Returns stale cache data with warning if live fetch fails.

        Args:
            team_abbr: Team abbreviation (e.g., "BOS", "LAL")

        Returns:
            Tuple of (TeamStats or None, list of error/warning messages)
        """
        errors = []
        cache_key = f"team_stats:{team_abbr.upper()}"

        team_id = get_team_id(team_abbr)
        if not team_id:
            errors.append(f"Unknown team abbreviation: {team_abbr}")
            return None, errors

        # Try live fetch
        try:
            df = await asyncio.get_running_loop().run_in_executor(
                None, self._fetch_team_game_log, team_id
            )
            stats = self._parse_game_log(df, team_abbr, team_id)

            # Cache the result
            await self._cache.set(cache_key, stats.model_dump(mode="json"), "team_stats")
            return stats, errors

        except Exception as e:
            errors.append(f"NBA API error for {team_abbr}: {type(e).__name__}: {e}")

        # Fall back to cache
        cached = await self._cache.get(cache_key, "team_stats")
        if cached:
            if cached.is_stale:
                errors.append(f"Using stale cache for {team_abbr} (fetched {cached.fetched_at})")
            stats = TeamStats.model_validate(cached.data)
            stats.is_stale = cached.is_stale
            return stats, errors

        errors.append(f"No cached data available for {team_abbr}")
        return None, errors

    def _parse_game_log(self, df: pd.DataFrame, abbr: str, team_id: str) -> TeamStats:
        """Parse TeamGameLog DataFrame into TeamStats model.

        Args:
            df: DataFrame from TeamGameLog endpoint
            abbr: Team abbreviation
            team_id: Team ID

        Returns:
            TeamStats model with parsed data
        """
        # Get team name from static data
        team_info = nba_teams.find_team_by_abbreviation(abbr.upper())
        team_name = team_info["full_name"] if team_info else abbr

        # Calculate record from W/L column
        wins = (df["WL"] == "W").sum()
        losses = (df["WL"] == "L").sum()

        # Calculate averages
        stats = TeamBasicStats(
            pts=df["PTS"].mean(),
            reb=df["REB"].mean(),
            ast=df["AST"].mean(),
            stl=df["STL"].mean() if "STL" in df.columns else 0.0,
            blk=df["BLK"].mean() if "BLK" in df.columns else 0.0,
            tov=df["TOV"].mean() if "TOV" in df.columns else 0.0,
            fg_pct=df["FG_PCT"].mean(),
            fg3_pct=df["FG3_PCT"].mean(),
            ft_pct=df["FT_PCT"].mean(),
        )

        # Home/away splits from MATCHUP column (contains "vs." for home, "@" for away)
        home_games = df[df["MATCHUP"].str.contains("vs.", na=False)]
        away_games = df[df["MATCHUP"].str.contains("@", na=False)]

        home_away = HomeAwayStats(
            home=HomeAwayRecord(
                wins=(home_games["WL"] == "W").sum(),
                losses=(home_games["WL"] == "L").sum(),
                pts=home_games["PTS"].mean() if len(home_games) > 0 else 0.0,
            ),
            away=HomeAwayRecord(
                wins=(away_games["WL"] == "W").sum(),
                losses=(away_games["WL"] == "L").sum(),
                pts=away_games["PTS"].mean() if len(away_games) > 0 else 0.0,
            ),
        )

        # Last 10 games
        last_10 = df.head(10)
        last_10_wins = (last_10["WL"] == "W").sum()
        last_10_losses = (last_10["WL"] == "L").sum()

        return TeamStats(
            team_id=team_id,
            name=team_name,
            abbreviation=abbr.upper(),
            record=TeamRecord(wins=wins, losses=losses),
            stats=stats,
            home_away=home_away,
            last_10=Last10Stats(
                record=f"{last_10_wins}-{last_10_losses}",
                pts=last_10["PTS"].mean(),
            ),
            fetched_at=datetime.now(),
        )

    async def get_advanced_metrics(self, team_abbr: str) -> tuple[TeamAdvancedMetrics | None, list[str]]:
        """Get advanced metrics for a team with cache fallback.

        Args:
            team_abbr: Team abbreviation (e.g., "BOS", "LAL")

        Returns:
            Tuple of (TeamAdvancedMetrics or None, list of error/warning messages)
        """
        errors = []
        cache_key = f"team_advanced:{team_abbr.upper()}"

        team_id = get_team_id(team_abbr)
        if not team_id:
            errors.append(f"Unknown team abbreviation: {team_abbr}")
            return None, errors

        try:
            df = await asyncio.get_running_loop().run_in_executor(
                None, self._fetch_all_team_metrics
            )
            # Filter to requested team
            team_row = df[df["TEAM_ID"] == int(team_id)]
            if team_row.empty:
                errors.append(f"No advanced metrics found for {team_abbr}")
                return None, errors

            row = team_row.iloc[0]
            metrics = TeamAdvancedMetrics(
                off_rtg=row["E_OFF_RATING"],
                def_rtg=row["E_DEF_RATING"],
                net_rtg=row["E_NET_RATING"],
                pace=row["E_PACE"],
                efg_pct=0.0,  # Not in this endpoint, will calculate from basic stats
            )

            # Cache
            await self._cache.set(cache_key, metrics.model_dump(mode="json"), "team_advanced")
            return metrics, errors

        except Exception as e:
            errors.append(f"NBA API error for {team_abbr} advanced: {type(e).__name__}: {e}")

        # Cache fallback
        cached = await self._cache.get(cache_key, "team_advanced")
        if cached:
            if cached.is_stale:
                errors.append(f"Using stale advanced metrics for {team_abbr}")
            return TeamAdvancedMetrics.model_validate(cached.data), errors

        return None, errors
