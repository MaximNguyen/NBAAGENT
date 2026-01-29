"""Tests for ML data loading and schema validation.

Tests:
- HistoricalGame schema creation and derived field calculation
- HistoricalOdds schema creation for different market types
- TrainingDataset creation from lists
- load_historical_games with mocked NBA API
- load_historical_odds with mocked HTTP responses
"""

from datetime import date, datetime
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from nba_betting_agent.ml.data.schema import (
    HistoricalGame,
    HistoricalOdds,
    TrainingDataset,
)
from nba_betting_agent.ml.data.historical import (
    load_historical_games,
    load_historical_odds,
    _fetch_odds_for_date,
)


# =============================================================================
# Schema Tests
# =============================================================================


class TestHistoricalGame:
    """Tests for HistoricalGame dataclass."""

    def test_create_home_win(self):
        """Test creation with home team winning."""
        game = HistoricalGame(
            game_id="0022300001",
            game_date=datetime(2024, 1, 15, 19, 30),
            season="2023-24",
            home_team="BOS",
            away_team="LAL",
            home_score=110,
            away_score=95,
        )

        assert game.home_win is True
        assert game.spread == 15.0  # home_score - away_score
        assert game.total == 205.0  # home_score + away_score

    def test_create_away_win(self):
        """Test creation with away team winning."""
        game = HistoricalGame(
            game_id="0022300002",
            game_date=datetime(2024, 1, 16, 20, 0),
            season="2023-24",
            home_team="MIA",
            away_team="NYK",
            home_score=98,
            away_score=105,
        )

        assert game.home_win is False
        assert game.spread == -7.0  # Negative = home loss margin
        assert game.total == 203.0

    def test_create_tie_game(self):
        """Test creation with tied score (home_win should be False)."""
        game = HistoricalGame(
            game_id="0022300003",
            game_date=datetime(2024, 1, 17),
            season="2023-24",
            home_team="PHX",
            away_team="DEN",
            home_score=100,
            away_score=100,
        )

        assert game.home_win is False  # Ties go to away (>not >=)
        assert game.spread == 0.0
        assert game.total == 200.0

    def test_immutability(self):
        """Test that frozen dataclass prevents modification."""
        game = HistoricalGame(
            game_id="0022300004",
            game_date=datetime(2024, 1, 18),
            season="2023-24",
            home_team="GSW",
            away_team="LAC",
            home_score=115,
            away_score=108,
        )

        with pytest.raises(AttributeError):
            game.home_score = 120


class TestHistoricalOdds:
    """Tests for HistoricalOdds dataclass."""

    def test_create_h2h_odds(self):
        """Test creation of moneyline odds."""
        odds = HistoricalOdds(
            game_id="0022300001",
            game_date=datetime(2024, 1, 15, 19, 30),
            bookmaker="draftkings",
            market="h2h",
            outcome="Boston Celtics",
            price=1.65,
            point=None,
            timestamp=datetime(2024, 1, 15, 12, 0),
        )

        assert odds.market == "h2h"
        assert odds.point is None
        assert odds.price == 1.65

    def test_create_spread_odds(self):
        """Test creation of spread odds with point value."""
        odds = HistoricalOdds(
            game_id="0022300001",
            game_date=datetime(2024, 1, 15, 19, 30),
            bookmaker="fanduel",
            market="spreads",
            outcome="Boston Celtics",
            price=1.91,
            point=-5.5,
            timestamp=datetime(2024, 1, 15, 12, 0),
        )

        assert odds.market == "spreads"
        assert odds.point == -5.5
        assert odds.price == 1.91

    def test_create_totals_odds(self):
        """Test creation of totals (over/under) odds."""
        odds = HistoricalOdds(
            game_id="0022300001",
            game_date=datetime(2024, 1, 15, 19, 30),
            bookmaker="betmgm",
            market="totals",
            outcome="Over",
            price=1.87,
            point=215.5,
            timestamp=datetime(2024, 1, 15, 12, 0),
        )

        assert odds.market == "totals"
        assert odds.outcome == "Over"
        assert odds.point == 215.5

    def test_immutability(self):
        """Test that frozen dataclass prevents modification."""
        odds = HistoricalOdds(
            game_id="0022300001",
            game_date=datetime(2024, 1, 15),
            bookmaker="draftkings",
            market="h2h",
            outcome="Boston Celtics",
            price=1.65,
            point=None,
            timestamp=datetime(2024, 1, 15),
        )

        with pytest.raises(AttributeError):
            odds.price = 1.75


class TestTrainingDataset:
    """Tests for TrainingDataset dataclass."""

    def test_from_lists(self):
        """Test creation from mutable lists."""
        games = [
            HistoricalGame(
                game_id="0022300001",
                game_date=datetime(2024, 1, 15),
                season="2023-24",
                home_team="BOS",
                away_team="LAL",
                home_score=110,
                away_score=95,
            )
        ]

        odds = [
            HistoricalOdds(
                game_id="0022300001",
                game_date=datetime(2024, 1, 15),
                bookmaker="draftkings",
                market="h2h",
                outcome="Boston Celtics",
                price=1.65,
                point=None,
                timestamp=datetime(2024, 1, 15),
            )
        ]

        dataset = TrainingDataset.from_lists(
            games=games,
            odds=odds,
            season_range=("2023-24", "2023-24"),
        )

        assert len(dataset.games) == 1
        assert len(dataset.odds) == 1
        assert dataset.season_range == ("2023-24", "2023-24")

        # Verify tuples (immutable)
        assert isinstance(dataset.games, tuple)
        assert isinstance(dataset.odds, tuple)

    def test_immutability(self):
        """Test that frozen dataclass prevents modification."""
        dataset = TrainingDataset(
            games=tuple(),
            odds=tuple(),
            season_range=("2023-24", "2023-24"),
        )

        with pytest.raises(AttributeError):
            dataset.season_range = ("2022-23", "2023-24")


# =============================================================================
# Historical Games Loader Tests
# =============================================================================


class TestLoadHistoricalGames:
    """Tests for load_historical_games function."""

    @pytest.fixture
    def mock_game_data(self):
        """Sample NBA API response data."""
        import pandas as pd

        # Two rows for one game (home and away team perspectives)
        return pd.DataFrame([
            {
                "GAME_ID": "0022300001",
                "GAME_DATE": "2024-01-15",
                "TEAM_ID": 1610612738,
                "TEAM_ABBREVIATION": "BOS",
                "TEAM_NAME": "Boston Celtics",
                "MATCHUP": "BOS vs. LAL",
                "WL": "W",
                "PTS": 110,
            },
            {
                "GAME_ID": "0022300001",
                "GAME_DATE": "2024-01-15",
                "TEAM_ID": 1610612747,
                "TEAM_ABBREVIATION": "LAL",
                "TEAM_NAME": "Los Angeles Lakers",
                "MATCHUP": "LAL @ BOS",
                "WL": "L",
                "PTS": 95,
            },
        ])

    @patch("nba_betting_agent.ml.data.historical._get_cache")
    @patch("nba_betting_agent.ml.data.historical.leaguegamefinder.LeagueGameFinder")
    @patch("nba_betting_agent.ml.data.historical.time.sleep")
    def test_load_games_from_api(self, mock_sleep, mock_finder_class, mock_cache, mock_game_data):
        """Test loading games from NBA API."""
        # Setup cache miss
        mock_cache_instance = MagicMock()
        mock_cache_instance.get.return_value = None
        mock_cache.return_value = mock_cache_instance

        # Setup API response
        mock_finder = MagicMock()
        mock_finder.get_data_frames.return_value = [mock_game_data]
        mock_finder_class.return_value = mock_finder

        # Load games
        games = load_historical_games(["2023-24"])

        # Verify API was called
        mock_finder_class.assert_called_once()
        mock_sleep.assert_called_once_with(0.6)  # Rate limit

        # Verify results
        assert len(games) == 1
        game = games[0]
        assert game.game_id == "0022300001"
        assert game.home_team == "BOS"
        assert game.away_team == "LAL"
        assert game.home_score == 110
        assert game.away_score == 95
        assert game.home_win is True

        # Verify cache was set
        mock_cache_instance.set.assert_called_once()

    @patch("nba_betting_agent.ml.data.historical._get_cache")
    def test_load_games_from_cache(self, mock_cache):
        """Test loading games from cache."""
        # Create cached game
        cached_game = HistoricalGame(
            game_id="0022300001",
            game_date=datetime(2024, 1, 15),
            season="2023-24",
            home_team="BOS",
            away_team="LAL",
            home_score=110,
            away_score=95,
        )

        # Setup cache hit
        mock_cache_instance = MagicMock()
        mock_cache_instance.get.return_value = [cached_game]
        mock_cache.return_value = mock_cache_instance

        # Load games
        games = load_historical_games(["2023-24"])

        # Verify cache was checked
        mock_cache_instance.get.assert_called_once_with("nba_games:2023-24")

        # Verify results
        assert len(games) == 1
        assert games[0].game_id == "0022300001"

    @patch("nba_betting_agent.ml.data.historical._get_cache")
    @patch("nba_betting_agent.ml.data.historical.leaguegamefinder.LeagueGameFinder")
    @patch("nba_betting_agent.ml.data.historical.time.sleep")
    def test_load_games_multiple_seasons(self, mock_sleep, mock_finder_class, mock_cache, mock_game_data):
        """Test loading games from multiple seasons."""
        # Setup cache miss for both seasons
        mock_cache_instance = MagicMock()
        mock_cache_instance.get.return_value = None
        mock_cache.return_value = mock_cache_instance

        # Setup API response
        mock_finder = MagicMock()
        mock_finder.get_data_frames.return_value = [mock_game_data]
        mock_finder_class.return_value = mock_finder

        # Load multiple seasons
        games = load_historical_games(["2022-23", "2023-24"])

        # Verify API was called twice
        assert mock_finder_class.call_count == 2
        assert mock_sleep.call_count == 2

        # Verify results (each season returns same mock data)
        assert len(games) == 2


# =============================================================================
# Historical Odds Loader Tests
# =============================================================================


class TestLoadHistoricalOdds:
    """Tests for load_historical_odds function."""

    @pytest.fixture
    def mock_odds_response(self):
        """Sample Odds API response data."""
        return {
            "timestamp": "2024-01-15T12:00:00Z",
            "data": [
                {
                    "id": "abc123",
                    "sport_key": "basketball_nba",
                    "commence_time": "2024-01-15T19:30:00Z",
                    "home_team": "Boston Celtics",
                    "away_team": "Los Angeles Lakers",
                    "bookmakers": [
                        {
                            "key": "draftkings",
                            "title": "DraftKings",
                            "markets": [
                                {
                                    "key": "h2h",
                                    "outcomes": [
                                        {"name": "Boston Celtics", "price": 1.65},
                                        {"name": "Los Angeles Lakers", "price": 2.30},
                                    ],
                                },
                                {
                                    "key": "spreads",
                                    "outcomes": [
                                        {"name": "Boston Celtics", "price": 1.91, "point": -5.5},
                                        {"name": "Los Angeles Lakers", "price": 1.91, "point": 5.5},
                                    ],
                                },
                            ],
                        }
                    ],
                }
            ],
        }

    @patch("nba_betting_agent.ml.data.historical._get_cache")
    def test_load_odds_no_api_key(self, mock_cache):
        """Test graceful handling when API key is missing."""
        # Clear environment
        with patch.dict("os.environ", {}, clear=True):
            odds = load_historical_odds(
                start_date=date(2024, 1, 15),
                end_date=date(2024, 1, 15),
                api_key=None,
            )

        assert odds == []

    @patch("nba_betting_agent.ml.data.historical._get_cache")
    @patch("nba_betting_agent.ml.data.historical._fetch_odds_for_date")
    def test_load_odds_from_api(self, mock_fetch, mock_cache):
        """Test loading odds from API."""
        # Setup cache miss
        mock_cache_instance = MagicMock()
        mock_cache_instance.get.return_value = None
        mock_cache.return_value = mock_cache_instance

        # Setup API response
        mock_odds = [
            HistoricalOdds(
                game_id="abc123",
                game_date=datetime(2024, 1, 15, 19, 30),
                bookmaker="draftkings",
                market="h2h",
                outcome="Boston Celtics",
                price=1.65,
                point=None,
                timestamp=datetime(2024, 1, 15, 12, 0),
            )
        ]
        mock_fetch.return_value = mock_odds

        odds = load_historical_odds(
            start_date=date(2024, 1, 15),
            end_date=date(2024, 1, 15),
            api_key="test-key",
        )

        assert len(odds) == 1
        assert odds[0].bookmaker == "draftkings"

        # Verify cache was set
        mock_cache_instance.set.assert_called_once()

    @patch("nba_betting_agent.ml.data.historical._get_cache")
    def test_load_odds_from_cache(self, mock_cache):
        """Test loading odds from cache."""
        # Create cached odds
        cached_odds = [
            HistoricalOdds(
                game_id="abc123",
                game_date=datetime(2024, 1, 15, 19, 30),
                bookmaker="draftkings",
                market="h2h",
                outcome="Boston Celtics",
                price=1.65,
                point=None,
                timestamp=datetime(2024, 1, 15, 12, 0),
            )
        ]

        # Setup cache hit
        mock_cache_instance = MagicMock()
        mock_cache_instance.get.return_value = cached_odds
        mock_cache.return_value = mock_cache_instance

        odds = load_historical_odds(
            start_date=date(2024, 1, 15),
            end_date=date(2024, 1, 15),
            api_key="test-key",
        )

        assert len(odds) == 1
        assert odds[0].bookmaker == "draftkings"

    @patch("nba_betting_agent.ml.data.historical._get_cache")
    @patch("nba_betting_agent.ml.data.historical._fetch_odds_for_date")
    def test_load_odds_date_range(self, mock_fetch, mock_cache):
        """Test loading odds across multiple dates."""
        # Setup cache miss
        mock_cache_instance = MagicMock()
        mock_cache_instance.get.return_value = None
        mock_cache.return_value = mock_cache_instance

        # Setup API responses
        mock_fetch.return_value = []

        odds = load_historical_odds(
            start_date=date(2024, 1, 15),
            end_date=date(2024, 1, 17),  # 3 days
            api_key="test-key",
        )

        # Verify fetch was called for each day
        assert mock_fetch.call_count == 3


class TestFetchOddsForDate:
    """Tests for _fetch_odds_for_date helper."""

    @patch("nba_betting_agent.ml.data.historical.httpx.Client")
    def test_parse_odds_response(self, mock_client_class):
        """Test parsing of Odds API response."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "timestamp": "2024-01-15T12:00:00Z",
            "data": [
                {
                    "id": "abc123",
                    "commence_time": "2024-01-15T19:30:00Z",
                    "bookmakers": [
                        {
                            "key": "draftkings",
                            "markets": [
                                {
                                    "key": "h2h",
                                    "outcomes": [
                                        {"name": "Boston Celtics", "price": 1.65},
                                    ],
                                },
                            ],
                        }
                    ],
                }
            ],
        }

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_class.return_value = mock_client

        odds = _fetch_odds_for_date(date(2024, 1, 15), "test-key")

        assert len(odds) == 1
        assert odds[0].game_id == "abc123"
        assert odds[0].bookmaker == "draftkings"
        assert odds[0].market == "h2h"
        assert odds[0].outcome == "Boston Celtics"
        assert odds[0].price == 1.65
