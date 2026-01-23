"""Tests for The Odds API client.

Uses pytest-httpx to mock HTTP responses for testing retry logic,
response validation, and credit tracking.
"""

import logging
import os
import re
from unittest.mock import patch

import httpx
import pytest
from tenacity import RetryError

from nba_betting_agent.agents.lines_agent.api import OddsAPIClient
from nba_betting_agent.agents.lines_agent.models import GameOdds


# Sample response matching The Odds API format
MOCK_RESPONSE = [
    {
        "id": "abc123",
        "sport_key": "basketball_nba",
        "commence_time": "2026-01-24T00:00:00Z",
        "home_team": "Boston Celtics",
        "away_team": "Los Angeles Lakers",
        "bookmakers": [
            {
                "key": "draftkings",
                "title": "DraftKings",
                "last_update": "2026-01-23T20:00:00Z",
                "markets": [
                    {
                        "key": "h2h",
                        "outcomes": [
                            {"name": "Boston Celtics", "price": 1.65},
                            {"name": "Los Angeles Lakers", "price": 2.30},
                        ],
                    }
                ],
            }
        ],
    }
]

# Response with spread and totals markets
MOCK_RESPONSE_ALL_MARKETS = [
    {
        "id": "def456",
        "sport_key": "basketball_nba",
        "commence_time": "2026-01-25T02:30:00Z",
        "home_team": "Golden State Warriors",
        "away_team": "Phoenix Suns",
        "bookmakers": [
            {
                "key": "fanduel",
                "title": "FanDuel",
                "last_update": "2026-01-24T18:00:00Z",
                "markets": [
                    {
                        "key": "h2h",
                        "outcomes": [
                            {"name": "Golden State Warriors", "price": 1.80},
                            {"name": "Phoenix Suns", "price": 2.05},
                        ],
                    },
                    {
                        "key": "spreads",
                        "outcomes": [
                            {"name": "Golden State Warriors", "price": 1.91, "point": -2.5},
                            {"name": "Phoenix Suns", "price": 1.91, "point": 2.5},
                        ],
                    },
                    {
                        "key": "totals",
                        "outcomes": [
                            {"name": "Over", "price": 1.95, "point": 225.5},
                            {"name": "Under", "price": 1.87, "point": 225.5},
                        ],
                    },
                ],
            }
        ],
    }
]

# URL pattern for matching API requests with any query params
ODDS_API_URL_PATTERN = re.compile(
    r"https://api\.the-odds-api\.com/v4/sports/basketball_nba/odds.*"
)


class TestOddsAPIClientInit:
    """Tests for OddsAPIClient initialization."""

    def test_client_requires_api_key(self, monkeypatch):
        """Client raises ValueError when no API key is available."""
        # Clear all environment variables and prevent load_dotenv from loading
        monkeypatch.delenv("ODDS_API_KEY", raising=False)
        monkeypatch.setattr("nba_betting_agent.agents.lines_agent.api.odds_api.load_dotenv", lambda: None)
        with pytest.raises(ValueError, match="ODDS_API_KEY not found"):
            OddsAPIClient()

    def test_client_accepts_env_key(self, monkeypatch):
        """Client reads API key from ODDS_API_KEY environment variable."""
        monkeypatch.setenv("ODDS_API_KEY", "test_key_from_env")
        monkeypatch.setattr("nba_betting_agent.agents.lines_agent.api.odds_api.load_dotenv", lambda: None)
        client = OddsAPIClient()
        assert client.api_key == "test_key_from_env"

    def test_client_accepts_parameter_key(self, monkeypatch):
        """Client accepts API key as parameter, overriding env."""
        monkeypatch.setenv("ODDS_API_KEY", "env_key")
        monkeypatch.setattr("nba_betting_agent.agents.lines_agent.api.odds_api.load_dotenv", lambda: None)
        client = OddsAPIClient(api_key="param_key")
        assert client.api_key == "param_key"

    def test_client_initializes_credit_tracking(self, monkeypatch):
        """Client initializes credit tracking attributes as None."""
        monkeypatch.setenv("ODDS_API_KEY", "test_key")
        monkeypatch.setattr("nba_betting_agent.agents.lines_agent.api.odds_api.load_dotenv", lambda: None)
        client = OddsAPIClient()
        assert client.remaining_credits is None
        assert client.used_credits is None


class TestOddsAPIClientGetNBAOdds:
    """Tests for get_nba_odds method."""

    @pytest.fixture(autouse=True)
    def setup_env(self, monkeypatch):
        """Set up environment for all tests in this class."""
        monkeypatch.setenv("ODDS_API_KEY", "test_key")
        monkeypatch.setattr("nba_betting_agent.agents.lines_agent.api.odds_api.load_dotenv", lambda: None)

    @pytest.mark.asyncio
    async def test_get_nba_odds_success(self, httpx_mock):
        """Returns list of GameOdds from successful API response."""
        httpx_mock.add_response(
            url=ODDS_API_URL_PATTERN,
            json=MOCK_RESPONSE,
            headers={"x-requests-remaining": "450", "x-requests-used": "50"},
        )

        client = OddsAPIClient()
        games = await client.get_nba_odds()

        assert len(games) == 1
        assert isinstance(games[0], GameOdds)
        assert games[0].id == "abc123"
        assert games[0].home_team == "Boston Celtics"
        assert games[0].away_team == "Los Angeles Lakers"
        assert len(games[0].bookmakers) == 1
        assert games[0].bookmakers[0].key == "draftkings"

    @pytest.mark.asyncio
    async def test_get_nba_odds_validates_response(self, httpx_mock):
        """Pydantic validates response data structure."""
        httpx_mock.add_response(
            url=ODDS_API_URL_PATTERN,
            json=MOCK_RESPONSE_ALL_MARKETS,
            headers={"x-requests-remaining": "400", "x-requests-used": "100"},
        )

        client = OddsAPIClient()
        games = await client.get_nba_odds()

        # Verify all market types are parsed
        game = games[0]
        assert game.bookmakers[0].key == "fanduel"
        markets = {m.key for m in game.bookmakers[0].markets}
        assert markets == {"h2h", "spreads", "totals"}

        # Verify spread points are parsed
        spread_market = next(m for m in game.bookmakers[0].markets if m.key == "spreads")
        assert spread_market.outcomes[0].point == -2.5

    @pytest.mark.asyncio
    async def test_get_nba_odds_retries_on_timeout(self, httpx_mock):
        """Retries request with exponential backoff on timeout."""
        # First two requests timeout, third succeeds
        httpx_mock.add_exception(
            httpx.TimeoutException("Connection timed out"),
            url=ODDS_API_URL_PATTERN,
        )
        httpx_mock.add_exception(
            httpx.TimeoutException("Connection timed out"),
            url=ODDS_API_URL_PATTERN,
        )
        httpx_mock.add_response(
            url=ODDS_API_URL_PATTERN,
            json=MOCK_RESPONSE,
            headers={"x-requests-remaining": "400", "x-requests-used": "100"},
        )

        client = OddsAPIClient()
        games = await client.get_nba_odds()

        # Should succeed after retries
        assert len(games) == 1
        assert games[0].id == "abc123"

    @pytest.mark.asyncio
    async def test_get_nba_odds_raises_after_max_retries(self, httpx_mock):
        """Raises exception after exhausting retry attempts."""
        # All three attempts fail
        httpx_mock.add_exception(
            httpx.TimeoutException("timeout"),
            url=ODDS_API_URL_PATTERN,
        )
        httpx_mock.add_exception(
            httpx.TimeoutException("timeout"),
            url=ODDS_API_URL_PATTERN,
        )
        httpx_mock.add_exception(
            httpx.TimeoutException("timeout"),
            url=ODDS_API_URL_PATTERN,
        )

        client = OddsAPIClient()
        with pytest.raises(RetryError):
            await client.get_nba_odds()

    @pytest.mark.asyncio
    async def test_get_nba_odds_tracks_credits(self, httpx_mock):
        """Updates remaining_credits and used_credits from response headers."""
        httpx_mock.add_response(
            url=ODDS_API_URL_PATTERN,
            json=MOCK_RESPONSE,
            headers={"x-requests-remaining": "423", "x-requests-used": "77"},
        )

        client = OddsAPIClient()
        await client.get_nba_odds()

        assert client.remaining_credits == 423
        assert client.used_credits == 77

    @pytest.mark.asyncio
    async def test_get_nba_odds_warns_low_credits(self, httpx_mock, caplog):
        """Logs warning when remaining credits < 50."""
        httpx_mock.add_response(
            url=ODDS_API_URL_PATTERN,
            json=MOCK_RESPONSE,
            headers={"x-requests-remaining": "25", "x-requests-used": "475"},
        )

        client = OddsAPIClient()
        with caplog.at_level(logging.WARNING):
            await client.get_nba_odds()

        assert client.remaining_credits == 25
        assert "Low API credits remaining: 25" in caplog.text

    @pytest.mark.asyncio
    async def test_get_nba_odds_no_warning_normal_credits(self, httpx_mock, caplog):
        """No warning when remaining credits >= 50."""
        httpx_mock.add_response(
            url=ODDS_API_URL_PATTERN,
            json=MOCK_RESPONSE,
            headers={"x-requests-remaining": "200", "x-requests-used": "300"},
        )

        client = OddsAPIClient()
        with caplog.at_level(logging.WARNING):
            await client.get_nba_odds()

        assert "Low API credits" not in caplog.text

    @pytest.mark.asyncio
    async def test_get_nba_odds_handles_empty_response(self, httpx_mock):
        """Handles empty response (no games scheduled)."""
        httpx_mock.add_response(
            url=ODDS_API_URL_PATTERN,
            json=[],
            headers={"x-requests-remaining": "499", "x-requests-used": "1"},
        )

        client = OddsAPIClient()
        games = await client.get_nba_odds()

        assert games == []

    @pytest.mark.asyncio
    async def test_get_nba_odds_custom_markets(self, httpx_mock):
        """Passes custom markets parameter to API."""
        httpx_mock.add_response(
            url=ODDS_API_URL_PATTERN,
            json=MOCK_RESPONSE,
            headers={"x-requests-remaining": "400", "x-requests-used": "100"},
        )

        client = OddsAPIClient()
        await client.get_nba_odds(markets="h2h")

        # Verify the request was made with correct params
        request = httpx_mock.get_request()
        assert "markets=h2h" in str(request.url)
