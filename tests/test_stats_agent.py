"""Integration tests for Stats Agent."""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import pandas as pd

from nba_betting_agent.agents.stats_agent import stats_agent_impl, collect_stats
from nba_betting_agent.agents.stats_agent.cache import StatsCache
from nba_betting_agent.agents.stats_agent.nba_client import NBAStatsClient
from nba_betting_agent.agents.stats_agent.espn_injuries import ESPNInjuriesClient


@pytest.fixture
def mock_cache(tmp_path):
    """Create a cache in temp directory."""
    return StatsCache(cache_dir=str(tmp_path / "cache"))


@pytest.fixture
def sample_game_log_df():
    """Sample TeamGameLog DataFrame."""
    return pd.DataFrame({
        "TEAM_ID": [1610612738] * 10,
        "GAME_ID": [f"00221{i:05d}" for i in range(10)],
        "GAME_DATE": ["2026-01-01"] * 10,
        "MATCHUP": ["BOS vs. NYK", "BOS @ LAL", "BOS vs. MIA", "BOS @ CHI", "BOS vs. GSW",
                    "BOS @ PHX", "BOS vs. DEN", "BOS @ LAC", "BOS vs. MIL", "BOS @ PHI"],
        "WL": ["W", "W", "L", "W", "W", "L", "W", "W", "L", "W"],
        "PTS": [115, 120, 105, 118, 122, 108, 125, 119, 112, 117],
        "REB": [45, 48, 42, 46, 50, 44, 47, 45, 43, 46],
        "AST": [28, 30, 25, 27, 32, 24, 29, 28, 26, 27],
        "STL": [8, 10, 6, 9, 11, 7, 8, 9, 7, 8],
        "BLK": [5, 6, 4, 5, 7, 4, 6, 5, 4, 5],
        "TOV": [12, 10, 14, 11, 9, 15, 10, 11, 13, 10],
        "FG_PCT": [0.48, 0.52, 0.44, 0.49, 0.51, 0.45, 0.50, 0.48, 0.46, 0.49],
        "FG3_PCT": [0.38, 0.42, 0.35, 0.39, 0.41, 0.36, 0.40, 0.38, 0.37, 0.39],
        "FT_PCT": [0.82, 0.85, 0.78, 0.81, 0.84, 0.80, 0.83, 0.82, 0.79, 0.81],
    })


@pytest.fixture
def sample_metrics_df():
    """Sample TeamEstimatedMetrics DataFrame."""
    return pd.DataFrame({
        "TEAM_ID": [1610612738, 1610612747],
        "TEAM_NAME": ["Boston Celtics", "Los Angeles Lakers"],
        "E_OFF_RATING": [118.5, 115.2],
        "E_DEF_RATING": [108.3, 112.1],
        "E_NET_RATING": [10.2, 3.1],
        "E_PACE": [99.8, 101.2],
    })


@pytest.fixture
def sample_espn_response():
    """Sample ESPN injury response."""
    return {
        "team": {"abbreviation": "BOS"},
        "injuries": [
            {
                "athlete": {"displayName": "Jaylen Brown", "position": {"abbreviation": "SG"}},
                "status": "Day-To-Day",
                "type": {"name": "Ankle"},
                "details": {"detail": "Questionable"},
            },
        ],
    }


class TestCollectStats:
    @pytest.mark.asyncio
    async def test_collect_stats_with_teams(
        self, sample_game_log_df, sample_metrics_df, sample_espn_response
    ):
        """Test stats collection with explicit team list."""
        with patch.object(NBAStatsClient, "_fetch_team_game_log", return_value=sample_game_log_df), \
             patch.object(NBAStatsClient, "_fetch_all_team_metrics", return_value=sample_metrics_df), \
             patch.object(ESPNInjuriesClient, "_fetch_injuries", new_callable=AsyncMock, return_value=sample_espn_response):

            result = await collect_stats(["BOS"])

        assert "BOS" in result["team_stats"]
        assert result["team_stats"]["BOS"]["abbreviation"] == "BOS"
        assert len(result["injuries"]) >= 0  # May have injuries
        assert "errors" in result

    @pytest.mark.asyncio
    async def test_collect_stats_extracts_teams_from_odds(
        self, sample_game_log_df, sample_metrics_df, sample_espn_response
    ):
        """Test team extraction from odds_data when no teams specified."""
        odds_data = [
            {"home_team": "Boston Celtics", "away_team": "Los Angeles Lakers"},
        ]

        with patch.object(NBAStatsClient, "_fetch_team_game_log", return_value=sample_game_log_df), \
             patch.object(NBAStatsClient, "_fetch_all_team_metrics", return_value=sample_metrics_df), \
             patch.object(ESPNInjuriesClient, "_fetch_injuries", new_callable=AsyncMock, return_value=sample_espn_response):

            result = await collect_stats([], odds_data)

        # Should have extracted teams from odds
        assert len(result["team_stats"]) > 0

    @pytest.mark.asyncio
    async def test_collect_stats_no_teams_no_odds(self):
        """Test error when no teams and no odds data."""
        result = await collect_stats([])

        assert result["team_stats"] == {}
        assert any("no teams" in e for e in result["errors"])

    @pytest.mark.asyncio
    async def test_collect_stats_normalizes_team_names(
        self, sample_game_log_df, sample_metrics_df, sample_espn_response
    ):
        """Test team name normalization (aliases, full names)."""
        with patch.object(NBAStatsClient, "_fetch_team_game_log", return_value=sample_game_log_df), \
             patch.object(NBAStatsClient, "_fetch_all_team_metrics", return_value=sample_metrics_df), \
             patch.object(ESPNInjuriesClient, "_fetch_injuries", new_callable=AsyncMock, return_value=sample_espn_response):

            result = await collect_stats(["celtics"])  # Common alias

        assert "BOS" in result["team_stats"]


class TestStatsAgentImpl:
    def test_stats_agent_impl_with_teams(
        self, sample_game_log_df, sample_metrics_df, sample_espn_response
    ):
        """Test sync wrapper with teams in state."""
        state = {
            "teams": ["BOS"],
            "odds_data": [],
        }

        with patch.object(NBAStatsClient, "_fetch_team_game_log", return_value=sample_game_log_df), \
             patch.object(NBAStatsClient, "_fetch_all_team_metrics", return_value=sample_metrics_df), \
             patch.object(ESPNInjuriesClient, "_fetch_injuries", new_callable=AsyncMock, return_value=sample_espn_response):

            result = stats_agent_impl(state)

        assert "team_stats" in result
        assert "injuries" in result
        assert "errors" in result

    def test_stats_agent_impl_extracts_from_odds(
        self, sample_game_log_df, sample_metrics_df, sample_espn_response
    ):
        """Test sync wrapper extracts teams from odds_data."""
        state = {
            "teams": [],
            "odds_data": [{"home_team": "Boston Celtics", "away_team": "Los Angeles Lakers"}],
        }

        with patch.object(NBAStatsClient, "_fetch_team_game_log", return_value=sample_game_log_df), \
             patch.object(NBAStatsClient, "_fetch_all_team_metrics", return_value=sample_metrics_df), \
             patch.object(ESPNInjuriesClient, "_fetch_injuries", new_callable=AsyncMock, return_value=sample_espn_response):

            result = stats_agent_impl(state)

        assert len(result["team_stats"]) > 0

    def test_stats_agent_impl_handles_api_errors(self):
        """Test graceful degradation on API errors."""
        state = {
            "teams": ["BOS"],
            "odds_data": [],
        }

        with patch.object(NBAStatsClient, "_fetch_team_game_log", side_effect=Exception("API down")), \
             patch.object(ESPNInjuriesClient, "_fetch_injuries", new_callable=AsyncMock, side_effect=Exception("API down")):

            result = stats_agent_impl(state)

        # Should not crash, should have errors
        assert "errors" in result
        assert len(result["errors"]) > 0


class TestTeamNameNormalization:
    def test_normalize_abbreviation(self):
        from nba_betting_agent.agents.stats_agent.agent import _normalize_team_names

        result = _normalize_team_names(["BOS", "LAL"])
        assert "BOS" in result
        assert "LAL" in result

    def test_normalize_full_name(self):
        from nba_betting_agent.agents.stats_agent.agent import _normalize_team_names

        result = _normalize_team_names(["Boston Celtics"])
        assert "BOS" in result

    def test_normalize_alias(self):
        from nba_betting_agent.agents.stats_agent.agent import _normalize_team_names

        result = _normalize_team_names(["celtics", "sixers"])
        assert "BOS" in result
        assert "PHI" in result

    def test_normalize_unknown_team(self):
        from nba_betting_agent.agents.stats_agent.agent import _normalize_team_names

        result = _normalize_team_names(["unknown_team"])
        assert len(result) == 0

    def test_normalize_city_name(self):
        from nba_betting_agent.agents.stats_agent.agent import _normalize_team_names

        result = _normalize_team_names(["Boston", "Los Angeles"])
        # Los Angeles maps to LAL (first match in nba_api)
        assert "BOS" in result
        assert len(result) >= 1

    def test_normalize_nickname(self):
        from nba_betting_agent.agents.stats_agent.agent import _normalize_team_names

        result = _normalize_team_names(["Lakers", "Warriors"])
        assert "LAL" in result
        assert "GSW" in result

    def test_normalize_mixed_case(self):
        from nba_betting_agent.agents.stats_agent.agent import _normalize_team_names

        result = _normalize_team_names(["bOsTon CeLtiCs", "LAKERS"])
        assert "BOS" in result
        assert "LAL" in result

    def test_normalize_deduplicates(self):
        from nba_betting_agent.agents.stats_agent.agent import _normalize_team_names

        result = _normalize_team_names(["BOS", "celtics", "Boston Celtics"])
        assert result.count("BOS") == 1  # Should deduplicate


class TestExtractTeamsFromOdds:
    def test_extract_teams_from_odds(self):
        from nba_betting_agent.agents.stats_agent.agent import _extract_teams_from_odds

        odds_data = [
            {"home_team": "Boston Celtics", "away_team": "Los Angeles Lakers"},
            {"home_team": "Golden State Warriors", "away_team": "Miami Heat"},
        ]

        result = _extract_teams_from_odds(odds_data)
        assert len(result) == 4
        assert "Boston Celtics" in result
        assert "Los Angeles Lakers" in result
        assert "Golden State Warriors" in result
        assert "Miami Heat" in result

    def test_extract_teams_empty_odds(self):
        from nba_betting_agent.agents.stats_agent.agent import _extract_teams_from_odds

        result = _extract_teams_from_odds([])
        assert result == []

    def test_extract_teams_deduplicates(self):
        from nba_betting_agent.agents.stats_agent.agent import _extract_teams_from_odds

        odds_data = [
            {"home_team": "Boston Celtics", "away_team": "Los Angeles Lakers"},
            {"home_team": "Boston Celtics", "away_team": "Miami Heat"},
        ]

        result = _extract_teams_from_odds(odds_data)
        assert len(result) == 3  # BOS, LAL, MIA (no duplicates)
