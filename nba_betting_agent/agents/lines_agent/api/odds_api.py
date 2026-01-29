"""The Odds API client for fetching NBA betting odds.

This module provides an async client for The Odds API (https://the-odds-api.com)
with retry logic for transient errors, credit tracking, and sportsbook metrics.
"""

import os
import time
from datetime import datetime

import httpx
from dotenv import load_dotenv
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from nba_betting_agent.agents.lines_agent.models import GameOdds
from nba_betting_agent.monitoring import get_logger, SportsbookMetrics

log = get_logger()

# Required sportsbooks for complete coverage analysis
REQUIRED_SPORTSBOOKS = {"draftkings", "fanduel", "betmgm", "bovada"}


class OddsAPIClient:
    """Async client for The Odds API.

    Fetches NBA odds with automatic retry on transient errors (timeouts, rate limits,
    server errors) and tracks remaining API credits from response headers.

    Also tracks per-sportsbook metrics for monitoring coverage and availability.

    Attributes:
        remaining_credits: Number of API credits remaining (from last response)
        used_credits: Number of API credits used this month (from last response)
        sportsbook_metrics: Dict of sportsbook name to SportsbookMetrics
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
        self.sportsbook_metrics: dict[str, SportsbookMetrics] = {}

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

        # Update sportsbook metrics
        self._update_sportsbook_metrics(games)

        duration_ms = int((time.perf_counter() - start_time) * 1000)
        log.info(
            "odds_api_request_completed",
            game_count=len(games),
            duration_ms=duration_ms,
            credits_remaining=self.remaining_credits,
            credits_used=self.used_credits,
        )

        return games

    def _update_sportsbook_metrics(self, games: list[GameOdds]) -> None:
        """Update sportsbook metrics from fetched games.

        Tracks per-sportsbook coverage including:
        - Number of games with odds from each book
        - Market types available from each book
        - Last seen timestamp
        - Availability percentage (games with book / total games)

        Also logs warning if required sportsbooks are missing.

        Args:
            games: List of GameOdds from API response
        """
        if not games:
            return

        total_games = len(games)
        book_game_counts: dict[str, int] = {}
        book_markets: dict[str, set[str]] = {}
        book_last_update: dict[str, datetime] = {}

        # Aggregate metrics across all games
        for game in games:
            for bookmaker in game.bookmakers:
                book_key = bookmaker.key
                book_game_counts[book_key] = book_game_counts.get(book_key, 0) + 1

                # Track available markets
                if book_key not in book_markets:
                    book_markets[book_key] = set()
                for market in bookmaker.markets:
                    book_markets[book_key].add(market.key)

                # Track last update time
                if bookmaker.last_update:
                    book_last_update[book_key] = bookmaker.last_update

        # Build metrics objects
        self.sportsbook_metrics = {}
        for book_key, game_count in book_game_counts.items():
            self.sportsbook_metrics[book_key] = SportsbookMetrics(
                name=book_key,
                games_with_odds=game_count,
                markets_available=sorted(book_markets.get(book_key, set())),
                last_seen=book_last_update.get(book_key),
                availability_pct=round((game_count / total_games) * 100, 1),
            )

        # Check for missing required sportsbooks
        available = set(self.sportsbook_metrics.keys())
        missing = REQUIRED_SPORTSBOOKS - available
        if missing:
            log.warning(
                "sportsbooks_unavailable",
                missing=sorted(missing),
                available=sorted(available),
            )

    def get_sportsbook_metrics(self) -> dict:
        """Get current sportsbook metrics as dictionary.

        Returns:
            Dict mapping sportsbook names to their metrics as dicts.
            Each metric dict contains: name, games_with_odds, markets_available,
            last_seen, availability_pct.
        """
        return {
            name: {
                "name": metrics.name,
                "games_with_odds": metrics.games_with_odds,
                "markets_available": metrics.markets_available,
                "last_seen": metrics.last_seen.isoformat() if metrics.last_seen else None,
                "availability_pct": metrics.availability_pct,
            }
            for name, metrics in self.sportsbook_metrics.items()
        }
