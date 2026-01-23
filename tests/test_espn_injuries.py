"""Tests for ESPNInjuriesClient with mocked HTTP responses."""

import pytest
import httpx
from datetime import datetime
from unittest.mock import AsyncMock, patch, MagicMock

from nba_betting_agent.agents.stats_agent.espn_injuries import ESPNInjuriesClient
from nba_betting_agent.agents.stats_agent.cache import StatsCache


@pytest.fixture
def mock_cache(tmp_path):
    """Create a cache in temp directory."""
    return StatsCache(cache_dir=str(tmp_path / "cache"))


@pytest.fixture
def sample_espn_response():
    """Sample ESPN injury API response."""
    return {
        "team": {
            "id": "2",
            "abbreviation": "BOS",
            "displayName": "Boston Celtics",
        },
        "injuries": [
            {
                "athlete": {
                    "id": "1234",
                    "displayName": "Jaylen Brown",
                    "position": {"abbreviation": "SG"},
                },
                "status": "Day-To-Day",
                "type": {"name": "Ankle"},
                "details": {"detail": "Questionable for tonight's game"},
            },
            {
                "athlete": {
                    "id": "5678",
                    "displayName": "Robert Williams III",
                    "position": {"abbreviation": "C"},
                },
                "status": "Out",
                "type": {"name": "Knee"},
                "details": {"detail": "Out indefinitely"},
            },
        ],
    }


@pytest.fixture
def empty_espn_response():
    """ESPN response with no injuries."""
    return {
        "team": {
            "id": "2",
            "abbreviation": "BOS",
        },
        "injuries": [],
    }


class TestESPNInjuriesClient:
    @pytest.mark.asyncio
    async def test_get_team_injuries_success(self, mock_cache, sample_espn_response):
        """Test successful injury fetch."""
        client = ESPNInjuriesClient(cache=mock_cache)

        with patch.object(
            client, "_fetch_injuries", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = sample_espn_response

            injuries, errors = await client.get_team_injuries("BOS")

        assert len(injuries) == 2
        assert injuries[0].player == "Jaylen Brown"
        assert injuries[0].status == "Day-To-Day"
        assert injuries[0].injury == "Ankle"
        assert injuries[1].player == "Robert Williams III"
        assert injuries[1].status == "Out"
        assert len(errors) == 0

    @pytest.mark.asyncio
    async def test_get_team_injuries_parses_position(
        self, mock_cache, sample_espn_response
    ):
        """Test position is parsed from response."""
        client = ESPNInjuriesClient(cache=mock_cache)

        with patch.object(
            client, "_fetch_injuries", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = sample_espn_response

            injuries, _ = await client.get_team_injuries("BOS")

        assert injuries[0].position == "SG"
        assert injuries[1].position == "C"

    @pytest.mark.asyncio
    async def test_get_team_injuries_empty_list(self, mock_cache, empty_espn_response):
        """Test handling of team with no injuries."""
        client = ESPNInjuriesClient(cache=mock_cache)

        with patch.object(
            client, "_fetch_injuries", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = empty_espn_response

            injuries, errors = await client.get_team_injuries("BOS")

        assert len(injuries) == 0
        assert len(errors) == 0  # No error - team is just healthy

    @pytest.mark.asyncio
    async def test_get_team_injuries_caches_result(
        self, mock_cache, sample_espn_response
    ):
        """Test that successful fetch caches the result."""
        client = ESPNInjuriesClient(cache=mock_cache)

        with patch.object(
            client, "_fetch_injuries", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = sample_espn_response

            await client.get_team_injuries("BOS")

        # Check cache was populated
        cached = await mock_cache.get("injuries:BOS", "injuries")
        assert cached is not None
        assert len(cached.data["injuries"]) == 2

    @pytest.mark.asyncio
    async def test_get_team_injuries_falls_back_to_cache(
        self, mock_cache, sample_espn_response
    ):
        """Test cache fallback on API failure."""
        client = ESPNInjuriesClient(cache=mock_cache)

        # First call succeeds and caches
        with patch.object(
            client, "_fetch_injuries", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = sample_espn_response
            await client.get_team_injuries("BOS")

        # Second call fails, should use cache
        with patch.object(
            client, "_fetch_injuries", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.side_effect = httpx.RequestError("Network error")

            injuries, errors = await client.get_team_injuries("BOS")

        assert len(injuries) == 2
        assert any("network error" in e for e in errors)

    @pytest.mark.asyncio
    async def test_get_team_injuries_404_error(self, mock_cache):
        """Test handling of 404 (team not found)."""
        client = ESPNInjuriesClient(cache=mock_cache)

        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch.object(
            client, "_fetch_injuries", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.side_effect = httpx.HTTPStatusError(
                "Not Found", request=MagicMock(), response=mock_response
            )

            injuries, errors = await client.get_team_injuries("XXX")

        assert len(injuries) == 0
        assert any("not found" in e for e in errors)

    @pytest.mark.asyncio
    async def test_get_team_injuries_no_cache_available(self, mock_cache):
        """Test when API fails and no cache exists."""
        client = ESPNInjuriesClient(cache=mock_cache)

        with patch.object(
            client, "_fetch_injuries", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.side_effect = httpx.RequestError("Network error")

            injuries, errors = await client.get_team_injuries("BOS")

        assert len(injuries) == 0
        assert any("No injury data" in e for e in errors)

    @pytest.mark.asyncio
    async def test_get_team_injuries_handles_malformed_data(self, mock_cache):
        """Test handling of malformed injury entry."""
        client = ESPNInjuriesClient(cache=mock_cache)

        malformed_response = {
            "team": {},
            "injuries": [
                # Valid entry
                {
                    "athlete": {"displayName": "Good Player"},
                    "status": "Out",
                    "type": {"name": "Knee"},
                },
                # Malformed - missing required fields
                {"random": "data"},
                # Another valid entry
                {
                    "athlete": {"displayName": "Another Player"},
                    "status": "Questionable",
                },
            ],
        }

        with patch.object(
            client, "_fetch_injuries", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = malformed_response

            injuries, errors = await client.get_team_injuries("BOS")

        # Should parse valid entries, skip malformed ones
        assert len(injuries) >= 1

    @pytest.mark.asyncio
    async def test_get_injuries_for_teams(self, mock_cache, sample_espn_response):
        """Test fetching injuries for multiple teams."""
        client = ESPNInjuriesClient(cache=mock_cache)

        with patch.object(
            client, "_fetch_injuries", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = sample_espn_response

            injuries, errors = await client.get_injuries_for_teams(["BOS", "LAL"])

        # 2 injuries per team x 2 teams = 4
        assert len(injuries) == 4
        assert mock_fetch.call_count == 2

    @pytest.mark.asyncio
    async def test_team_abbreviation_normalized_uppercase(
        self, mock_cache, sample_espn_response
    ):
        """Test that team abbreviation is normalized to uppercase."""
        client = ESPNInjuriesClient(cache=mock_cache)

        with patch.object(
            client, "_fetch_injuries", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = sample_espn_response

            injuries, _ = await client.get_team_injuries("bos")  # lowercase

        # Team in injury report should be uppercase
        assert all(inj.team == "BOS" for inj in injuries)

    @pytest.mark.asyncio
    async def test_get_team_injuries_parses_details(
        self, mock_cache, sample_espn_response
    ):
        """Test that injury details are parsed correctly."""
        client = ESPNInjuriesClient(cache=mock_cache)

        with patch.object(
            client, "_fetch_injuries", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = sample_espn_response

            injuries, _ = await client.get_team_injuries("BOS")

        assert injuries[0].details == "Questionable for tonight's game"
        assert injuries[1].details == "Out indefinitely"

    @pytest.mark.asyncio
    async def test_get_team_injuries_with_stale_cache(
        self, mock_cache, sample_espn_response
    ):
        """Test that stale cache warning is included in errors."""
        client = ESPNInjuriesClient(cache=mock_cache)

        # First call succeeds and caches
        with patch.object(
            client, "_fetch_injuries", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = sample_espn_response
            await client.get_team_injuries("BOS")

        # Mock cache to return stale data
        with patch.object(mock_cache, "get", new_callable=AsyncMock) as mock_get:
            from nba_betting_agent.agents.stats_agent.cache import CacheEntry

            stale_entry = CacheEntry(
                data={"injuries": [inj.model_dump(mode="json") for inj in []]},
                fetched_at=datetime.now(),
                is_stale=True,
            )
            mock_get.return_value = stale_entry

            with patch.object(
                client, "_fetch_injuries", new_callable=AsyncMock
            ) as mock_fetch:
                mock_fetch.side_effect = httpx.RequestError("Network error")

                injuries, errors = await client.get_team_injuries("BOS")

        assert any("stale" in e.lower() for e in errors)

    @pytest.mark.asyncio
    async def test_get_team_injuries_handles_http_500(self, mock_cache):
        """Test handling of HTTP 500 server error."""
        client = ESPNInjuriesClient(cache=mock_cache)

        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch.object(
            client, "_fetch_injuries", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.side_effect = httpx.HTTPStatusError(
                "Server Error", request=MagicMock(), response=mock_response
            )

            injuries, errors = await client.get_team_injuries("BOS")

        assert len(injuries) == 0
        assert any("HTTP 500" in e for e in errors)
