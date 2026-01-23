"""Tests for NBAStatsClient with mocked nba_api responses."""

import asyncio
from datetime import datetime
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from nba_betting_agent.agents.stats_agent.cache import StatsCache
from nba_betting_agent.agents.stats_agent.nba_client import (
    NBAStatsClient,
    get_current_season,
    get_team_id,
)


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


class TestGetCurrentSeason:
    def test_returns_season_format(self):
        """Test that season is in correct format."""
        season = get_current_season()
        assert "-" in season
        parts = season.split("-")
        assert len(parts) == 2
        assert len(parts[0]) == 4  # Full year
        assert len(parts[1]) == 2  # Short year


class TestGetTeamId:
    def test_valid_abbreviation(self):
        """Test retrieving team ID for valid abbreviation."""
        team_id = get_team_id("BOS")
        assert team_id == "1610612738"

    def test_lowercase_abbreviation(self):
        """Test case-insensitive abbreviation lookup."""
        team_id = get_team_id("bos")
        assert team_id == "1610612738"

    def test_invalid_abbreviation(self):
        """Test that invalid abbreviation returns None."""
        team_id = get_team_id("XXX")
        assert team_id is None


class TestNBAStatsClient:
    @pytest.mark.asyncio
    async def test_get_team_stats_success(self, mock_cache, sample_game_log_df):
        """Test successful stats fetch."""
        client = NBAStatsClient(cache=mock_cache)

        with patch.object(client, "_fetch_team_game_log", return_value=sample_game_log_df):
            stats, errors = await client.get_team_stats("BOS")

        assert stats is not None
        assert stats.abbreviation == "BOS"
        assert stats.record.wins == 7
        assert stats.record.losses == 3
        assert stats.stats.pts > 0
        assert len(errors) == 0

    @pytest.mark.asyncio
    async def test_get_team_stats_calculates_averages(self, mock_cache, sample_game_log_df):
        """Test that stats are correctly averaged."""
        client = NBAStatsClient(cache=mock_cache)

        with patch.object(client, "_fetch_team_game_log", return_value=sample_game_log_df):
            stats, _ = await client.get_team_stats("BOS")

        # Average of sample data
        expected_pts = sum([115, 120, 105, 118, 122, 108, 125, 119, 112, 117]) / 10
        assert abs(stats.stats.pts - expected_pts) < 0.1

    @pytest.mark.asyncio
    async def test_get_team_stats_home_away_splits(self, mock_cache, sample_game_log_df):
        """Test home/away splits are calculated."""
        client = NBAStatsClient(cache=mock_cache)

        with patch.object(client, "_fetch_team_game_log", return_value=sample_game_log_df):
            stats, _ = await client.get_team_stats("BOS")

        # 5 home games (vs.), 5 away games (@)
        assert stats.home_away.home.wins + stats.home_away.home.losses == 5
        assert stats.home_away.away.wins + stats.home_away.away.losses == 5

    @pytest.mark.asyncio
    async def test_get_team_stats_last_10(self, mock_cache, sample_game_log_df):
        """Test last 10 games stats."""
        client = NBAStatsClient(cache=mock_cache)

        with patch.object(client, "_fetch_team_game_log", return_value=sample_game_log_df):
            stats, _ = await client.get_team_stats("BOS")

        assert stats.last_10 is not None
        assert stats.last_10.record == "7-3"

    @pytest.mark.asyncio
    async def test_get_team_stats_caches_result(self, mock_cache, sample_game_log_df):
        """Test that successful fetch caches the result."""
        client = NBAStatsClient(cache=mock_cache)

        with patch.object(client, "_fetch_team_game_log", return_value=sample_game_log_df):
            await client.get_team_stats("BOS")

        # Check cache was populated
        cached = await mock_cache.get("team_stats:BOS", "team_stats")
        assert cached is not None
        assert cached.data["abbreviation"] == "BOS"

    @pytest.mark.asyncio
    async def test_get_team_stats_falls_back_to_cache(self, mock_cache, sample_game_log_df):
        """Test cache fallback on API failure."""
        client = NBAStatsClient(cache=mock_cache)

        # First call succeeds and caches
        with patch.object(client, "_fetch_team_game_log", return_value=sample_game_log_df):
            await client.get_team_stats("BOS")

        # Second call fails, should use cache
        with patch.object(client, "_fetch_team_game_log", side_effect=Exception("API down")):
            stats, errors = await client.get_team_stats("BOS")

        assert stats is not None
        assert stats.abbreviation == "BOS"
        assert any("API error" in e for e in errors)

    @pytest.mark.asyncio
    async def test_get_team_stats_unknown_team(self, mock_cache):
        """Test error for unknown team abbreviation."""
        client = NBAStatsClient(cache=mock_cache)
        stats, errors = await client.get_team_stats("XXX")

        assert stats is None
        assert any("Unknown team" in e for e in errors)

    @pytest.mark.asyncio
    async def test_get_team_stats_no_cache_fallback(self, mock_cache):
        """Test that error returned when API fails and no cache exists."""
        client = NBAStatsClient(cache=mock_cache)

        with patch.object(client, "_fetch_team_game_log", side_effect=Exception("API down")):
            stats, errors = await client.get_team_stats("BOS")

        assert stats is None
        assert any("API error" in e for e in errors)
        assert any("No cached data" in e for e in errors)

    @pytest.mark.asyncio
    async def test_get_advanced_metrics_success(self, mock_cache, sample_metrics_df):
        """Test successful advanced metrics fetch."""
        client = NBAStatsClient(cache=mock_cache)

        with patch.object(client, "_fetch_all_team_metrics", return_value=sample_metrics_df):
            metrics, errors = await client.get_advanced_metrics("BOS")

        assert metrics is not None
        assert metrics.off_rtg == 118.5
        assert metrics.def_rtg == 108.3
        assert metrics.net_rtg == 10.2
        assert len(errors) == 0

    @pytest.mark.asyncio
    async def test_get_advanced_metrics_caches_result(self, mock_cache, sample_metrics_df):
        """Test that advanced metrics are cached."""
        client = NBAStatsClient(cache=mock_cache)

        with patch.object(client, "_fetch_all_team_metrics", return_value=sample_metrics_df):
            await client.get_advanced_metrics("BOS")

        cached = await mock_cache.get("team_advanced:BOS", "team_advanced")
        assert cached is not None

    @pytest.mark.asyncio
    async def test_get_advanced_metrics_cache_fallback(self, mock_cache, sample_metrics_df):
        """Test cache fallback for advanced metrics."""
        client = NBAStatsClient(cache=mock_cache)

        # First call succeeds and caches
        with patch.object(client, "_fetch_all_team_metrics", return_value=sample_metrics_df):
            await client.get_advanced_metrics("BOS")

        # Second call fails, should use cache
        with patch.object(client, "_fetch_all_team_metrics", side_effect=Exception("API down")):
            metrics, errors = await client.get_advanced_metrics("BOS")

        assert metrics is not None
        assert metrics.off_rtg == 118.5
        assert any("API error" in e for e in errors)

    @pytest.mark.asyncio
    async def test_get_advanced_metrics_team_not_found(self, mock_cache, sample_metrics_df):
        """Test error when team not in metrics DataFrame."""
        client = NBAStatsClient(cache=mock_cache)

        # Return DF without LAC
        with patch.object(client, "_fetch_all_team_metrics", return_value=sample_metrics_df):
            metrics, errors = await client.get_advanced_metrics("LAC")

        assert metrics is None
        assert any("No advanced metrics found" in e for e in errors)

    @pytest.mark.asyncio
    async def test_get_advanced_metrics_unknown_team(self, mock_cache):
        """Test error for unknown team abbreviation."""
        client = NBAStatsClient(cache=mock_cache)
        metrics, errors = await client.get_advanced_metrics("XXX")

        assert metrics is None
        assert any("Unknown team" in e for e in errors)
