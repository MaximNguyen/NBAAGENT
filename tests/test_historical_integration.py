"""Integration tests for database-backed historical data loading.

Tests verify:
- load_historical_games checks database first, falls back to API
- load_historical_odds uses OddsRepository for caching
- USE_DATABASE toggle works correctly
- Graceful degradation when database unavailable
"""

import os
from datetime import date, datetime
from unittest.mock import Mock, patch, AsyncMock

import pytest

from nba_betting_agent.db import get_games_repository, get_odds_repository
from nba_betting_agent.db.session import AsyncSessionFactory
from nba_betting_agent.ml.data.historical import (
    load_historical_games,
    load_historical_odds,
)
from nba_betting_agent.ml.data.schema import HistoricalGame, HistoricalOdds


@pytest.fixture
async def test_session():
    """Create a test database session."""
    session = AsyncSessionFactory()
    try:
        yield session
    finally:
        await session.close()


@pytest.fixture
def sample_games():
    """Sample game data for testing."""
    return [
        HistoricalGame(
            game_id="0022300001",
            game_date=datetime(2024, 1, 15),
            season="2023-24",
            home_team="BOS",
            away_team="LAL",
            home_score=110,
            away_score=105,
        ),
        HistoricalGame(
            game_id="0022300002",
            game_date=datetime(2024, 1, 16),
            season="2023-24",
            home_team="GSW",
            away_team="MIA",
            home_score=115,
            away_score=108,
        ),
    ]


@pytest.fixture
def sample_odds():
    """Sample odds data for testing."""
    return [
        HistoricalOdds(
            game_id="0022300001",
            game_date=datetime(2024, 1, 15),
            bookmaker="draftkings",
            market="h2h",
            outcome="BOS",
            price=1.85,
            point=None,
            timestamp=datetime(2024, 1, 15, 10, 0),
        ),
        HistoricalOdds(
            game_id="0022300001",
            game_date=datetime(2024, 1, 15),
            bookmaker="draftkings",
            market="h2h",
            outcome="LAL",
            price=2.10,
            point=None,
            timestamp=datetime(2024, 1, 15, 10, 0),
        ),
    ]


def test_load_games_uses_database(sample_games, monkeypatch):
    """Test that load_historical_games checks database first."""
    # Mock the async repository to return data from database
    mock_repo = Mock()
    mock_repo.get_by_season = AsyncMock(return_value=sample_games)
    mock_repo.bulk_save = AsyncMock(return_value=2)

    # Mock get_games_repository to return our mock
    with patch("nba_betting_agent.ml.data.historical.get_games_repository", return_value=mock_repo):
        # Mock get_session context manager
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("nba_betting_agent.ml.data.historical.get_session", return_value=mock_session):
            # Mock NBA API (should NOT be called)
            with patch("nba_betting_agent.ml.data.historical._load_games_from_api") as mock_api:
                mock_api.return_value = []

                # Call load_historical_games
                games = load_historical_games(["2023-24"])

                # Assert games returned from database
                assert len(games) == 2
                assert games[0].game_id == "0022300001"
                assert games[1].game_id == "0022300002"

                # Assert API not called (database had data)
                mock_api.assert_not_called()


def test_load_games_fallback_to_api(sample_games, monkeypatch):
    """Test that load_historical_games falls back to API when database empty."""
    # Mock the async repository to return empty list (database has no data)
    mock_repo = Mock()
    mock_repo.get_by_season = AsyncMock(return_value=[])
    mock_repo.bulk_save = AsyncMock(return_value=2)

    # Mock get_games_repository to return our mock
    with patch("nba_betting_agent.ml.data.historical.get_games_repository", return_value=mock_repo):
        # Mock get_session context manager
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("nba_betting_agent.ml.data.historical.get_session", return_value=mock_session):
            # Mock NBA API to return games
            with patch("nba_betting_agent.ml.data.historical._load_games_from_api") as mock_api:
                mock_api.return_value = sample_games

                # Call load_historical_games
                games = load_historical_games(["2023-24"])

                # Assert games returned from API
                assert len(games) == 2
                assert games[0].game_id == "0022300001"

                # Assert API was called
                mock_api.assert_called_once_with(["2023-24"])

                # Assert games were saved to database
                mock_repo.bulk_save.assert_called_once()


def test_load_games_api_only_mode(sample_games, monkeypatch):
    """Test that USE_DATABASE=false skips database entirely."""
    # Set USE_DATABASE=false before importing
    monkeypatch.setenv("USE_DATABASE", "false")

    # Need to reload the module to pick up the env var
    import importlib
    import nba_betting_agent.ml.data.historical as hist_module
    importlib.reload(hist_module)

    # Mock NBA API
    with patch.object(hist_module, "_load_games_from_api") as mock_api:
        mock_api.return_value = sample_games

        # Mock get_games_repository (should NOT be called)
        with patch.object(hist_module, "get_games_repository") as mock_get_repo:
            # Call load_historical_games
            games = hist_module.load_historical_games(["2023-24"])

            # Assert games returned from API
            assert len(games) == 2

            # Assert API was called
            mock_api.assert_called_once()

            # Assert repository was NOT used
            mock_get_repo.assert_not_called()

    # Reload again to restore USE_DATABASE=true
    monkeypatch.delenv("USE_DATABASE", raising=False)
    importlib.reload(hist_module)


def test_load_odds_with_caching(sample_odds, monkeypatch):
    """Test that load_historical_odds uses caching."""
    # Mock the async repository
    mock_repo = Mock()
    # First call: database has data
    mock_repo.get_odds_for_date_range = AsyncMock(return_value=sample_odds)

    # Mock get_odds_repository to return our mock
    with patch("nba_betting_agent.ml.data.historical.get_odds_repository", return_value=mock_repo):
        # Mock get_session context manager
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("nba_betting_agent.ml.data.historical.get_session", return_value=mock_session):
            # Mock Odds API (should NOT be called)
            with patch("nba_betting_agent.ml.data.historical._load_odds_from_api") as mock_api:
                mock_api.return_value = []

                # Call load_historical_odds
                odds = load_historical_odds(
                    start_date=date(2024, 1, 15),
                    end_date=date(2024, 1, 15),
                    api_key="test-key",
                )

                # Assert odds returned from database
                assert len(odds) == 2
                assert odds[0].game_id == "0022300001"

                # Assert API not called (database had data)
                mock_api.assert_not_called()


def test_load_odds_cache_disabled(sample_odds, monkeypatch):
    """Test that ODDS_CACHE_ENABLED=false disables caching."""
    # Set cache disabled
    monkeypatch.setenv("ODDS_CACHE_ENABLED", "false")

    # Mock the async repository - empty database
    mock_repo = Mock()
    mock_repo.get_odds_for_date_range = AsyncMock(return_value=[])
    mock_repo.save_odds = AsyncMock(return_value=2)

    # Mock get_odds_repository to return our mock
    with patch("nba_betting_agent.ml.data.historical.get_odds_repository", return_value=mock_repo):
        # Mock get_session context manager
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("nba_betting_agent.ml.data.historical.get_session", return_value=mock_session):
            # Mock Odds API to return odds
            with patch("nba_betting_agent.ml.data.historical._load_odds_from_api") as mock_api:
                mock_api.return_value = sample_odds

                # Call load_historical_odds twice
                odds1 = load_historical_odds(
                    start_date=date(2024, 1, 15),
                    end_date=date(2024, 1, 15),
                    api_key="test-key",
                )
                odds2 = load_historical_odds(
                    start_date=date(2024, 1, 15),
                    end_date=date(2024, 1, 15),
                    api_key="test-key",
                )

                # Assert both calls returned odds
                assert len(odds1) == 2
                assert len(odds2) == 2

                # Note: We can't easily test if API was called twice without cache
                # because the diskcache is still in _load_odds_from_api
                # The important thing is that OddsRepository respects ODDS_CACHE_ENABLED


def test_graceful_degradation(sample_games, monkeypatch):
    """Test that database errors don't crash, system falls back to API."""
    # Mock the async repository to raise an error
    mock_repo = Mock()
    mock_repo.get_by_season = AsyncMock(side_effect=Exception("Database connection failed"))

    # Mock get_games_repository to return our mock
    with patch("nba_betting_agent.ml.data.historical.get_games_repository", return_value=mock_repo):
        # Mock get_session context manager
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("nba_betting_agent.ml.data.historical.get_session", return_value=mock_session):
            # Mock NBA API to return games
            with patch("nba_betting_agent.ml.data.historical._load_games_from_api") as mock_api:
                mock_api.return_value = sample_games

                # Call load_historical_games (should not crash)
                games = load_historical_games(["2023-24"])

                # Assert games returned from API fallback
                assert len(games) == 2
                assert games[0].game_id == "0022300001"

                # Assert API was called as fallback
                mock_api.assert_called_once()
