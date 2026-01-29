"""The Odds API client for fetching NBA betting odds.

This module provides an async client for The Odds API (https://the-odds-api.com)
with retry logic for transient errors and credit tracking.
"""

import os
import time

import httpx
from dotenv import load_dotenv
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from nba_betting_agent.agents.lines_agent.models import GameOdds
from nba_betting_agent.monitoring import get_logger

log = get_logger()


class OddsAPIClient:
    """Async client for The Odds API.

    Fetches NBA odds with automatic retry on transient errors (timeouts, rate limits,
    server errors) and tracks remaining API credits from response headers.

    Attributes:
        remaining_credits: Number of API credits remaining (from last response)
        used_credits: Number of API credits used this month (from last response)
    """

    BASE_URL = "https://api.the-odds-api.com/v4"

    def __init__(self, api_key: str | None = None) -> None:
        """Initialize the Odds API client.

        Args:
            api_key: API key for The Odds API. If not provided, reads from
                     ODDS_API_KEY environment variable.

        Raises:
            ValueError: If no API key is provided or found in environment.
        """
        load_dotenv()

        self.api_key = api_key or os.getenv("ODDS_API_KEY")
        if not self.api_key:
            raise ValueError(
                "ODDS_API_KEY not found in environment. "
                "Set it in .env or pass api_key parameter."
            )

        self.remaining_credits: int | None = None
        self.used_credits: int | None = None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    )
    async def get_nba_odds(
        self,
        markets: str = "h2h,spreads,totals",
        odds_format: str = "decimal",
    ) -> list[GameOdds]:
        """Fetch current NBA odds from The Odds API.

        Retrieves odds for all upcoming NBA games across configured markets
        and bookmakers.

        Args:
            markets: Comma-separated market types to fetch.
                     Options: h2h (moneyline), spreads, totals
            odds_format: Format for odds values. Use "decimal" for consistency.

        Returns:
            List of GameOdds objects, each containing odds from multiple
            bookmakers for a single game.

        Raises:
            httpx.HTTPError: If request fails after 3 retry attempts.
            httpx.TimeoutException: If request times out after 3 retry attempts.
            pydantic.ValidationError: If response data fails validation.
        """
        start_time = time.perf_counter()

        params = {
            "apiKey": self.api_key,
            "regions": "us",
            "markets": markets,
            "oddsFormat": odds_format,
        }

        log.info("odds_api_request_started", markets=markets)

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{self.BASE_URL}/sports/basketball_nba/odds",
                params=params,
            )
            response.raise_for_status()

        # Extract remaining credits from response headers
        remaining = response.headers.get("x-requests-remaining")
        used = response.headers.get("x-requests-used")
        if remaining:
            self.remaining_credits = int(remaining)
        if used:
            self.used_credits = int(used)

        # Log warning if credits are low
        if self.remaining_credits is not None and self.remaining_credits < 50:
            log.warning(
                "low_api_credits",
                remaining=self.remaining_credits,
                message="Consider reducing request frequency",
            )

        # Parse and validate response
        data = response.json()
        games: list[GameOdds] = []
        for game_data in data:
            game = GameOdds.model_validate(game_data)
            games.append(game)

        duration_ms = int((time.perf_counter() - start_time) * 1000)
        log.info(
            "odds_api_request_completed",
            game_count=len(games),
            duration_ms=duration_ms,
            credits_remaining=self.remaining_credits,
            credits_used=self.used_credits,
        )

        return games
