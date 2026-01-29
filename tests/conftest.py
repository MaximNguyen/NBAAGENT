"""Shared pytest fixtures for NBA betting agent tests."""

import pytest
from datetime import datetime, timedelta
from freezegun import freeze_time

from nba_betting_agent.agents.stats_agent.cache import StatsCache
from nba_betting_agent.monitoring import configure_logging


@pytest.fixture(autouse=True)
def setup_test_logging():
    """Configure structlog for test output."""
    configure_logging("development")


@pytest.fixture
def clean_cache(tmp_path):
    """Provide a fresh cache instance for testing.

    Uses tmp_path to ensure isolated cache directory per test.
    Automatically clears cache after test completes.
    """
    cache = StatsCache(cache_dir=str(tmp_path / "test_cache"))
    yield cache
    cache.clear()


@pytest.fixture
def historical_window():
    """30-day historical window for temporal validation.

    Returns dict with:
        start: First day of validation period
        end: Last day of validation period
        train_split: Last day of training data (day 21)
        test_start: First day of test data (day 22)

    The 70/30 split (21 train / 9 test days) provides enough data
    for both model training and validation while avoiding overfitting.
    """
    return {
        "start": datetime(2026, 1, 1, 0, 0, 0),
        "end": datetime(2026, 1, 30, 23, 59, 59),
        "train_split": datetime(2026, 1, 21, 23, 59, 59),
        "test_start": datetime(2026, 1, 22, 0, 0, 0),
    }


@pytest.fixture
def sample_odds_data():
    """Sample odds data for testing temporal validation.

    Provides realistic odds data structure matching The Odds API format.
    """
    return {
        "game_id": "test_game_001",
        "home_team": "Boston Celtics",
        "away_team": "Los Angeles Lakers",
        "commence_time": datetime(2026, 1, 15, 19, 30, 0),
        "bookmakers": [
            {
                "key": "draftkings",
                "markets": [
                    {
                        "key": "h2h",
                        "outcomes": [
                            {"name": "Boston Celtics", "price": 1.67},
                            {"name": "Los Angeles Lakers", "price": 2.25},
                        ]
                    }
                ]
            }
        ]
    }


@pytest.fixture
def temporal_split(historical_window):
    """Provide pre-computed train/test split dates.

    Train: Days 1-21 (21 days, ~70%)
    Test: Days 22-30 (9 days, ~30%)

    This split ensures no data leakage - all test dates are
    strictly after all training dates.
    """
    return {
        "train_dates": [
            historical_window["start"] + timedelta(days=i)
            for i in range(21)  # Days 1-21
        ],
        "test_dates": [
            historical_window["test_start"] + timedelta(days=i)
            for i in range(9)  # Days 22-30
        ],
    }
