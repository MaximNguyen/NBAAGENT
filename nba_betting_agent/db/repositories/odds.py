"""Repository for odds data with hybrid two-tier caching.

Implements a caching strategy that balances API credit conservation with
historical data availability:

- L1 (diskcache): TTL-based cache for fresh API responses
- L2 (database): Permanent storage for backtesting and historical analysis

Cache can be disabled via ODDS_CACHE_ENABLED=false environment variable.
"""

from datetime import date, datetime
from typing import cast

from diskcache import FanoutCache
from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from nba_betting_agent.db.cache_toggle import get_cache_config
from nba_betting_agent.db.models import (
    HistoricalOddsModel,
    model_to_odds_dataclass,
    odds_dataclass_to_model,
)
from nba_betting_agent.ml.data.schema import HistoricalOdds
from nba_betting_agent.monitoring import get_logger


class OddsRepository:
    """Hybrid caching repository for odds data.

    Two-tier caching strategy:
    - L1 (diskcache): TTL-based cache for API response freshness
    - L2 (database): Permanent storage for historical analysis

    Cache can be toggled via ODDS_CACHE_ENABLED environment variable.

    Examples:
        >>> from nba_betting_agent.db.session import get_session
        >>> async with get_session() as session:
        ...     repo = OddsRepository(session)
        ...
        ...     # Check L1/L2 cache first
        ...     odds = await repo.get_odds_for_game("0022300001")
        ...     if not odds:
        ...         # Fetch from API and save
        ...         odds = fetch_from_api()
        ...         await repo.save_odds(odds)
        ...
        ...     # Historical range query (L2 only)
        ...     historical = await repo.get_odds_for_date_range(
        ...         start=date(2024, 1, 1),
        ...         end=date(2024, 1, 31),
        ...     )
    """

    def __init__(self, session: AsyncSession | None = None):
        """Initialize repository with optional database session.

        Args:
            session: AsyncSession for database operations. If None, database
                operations will be skipped (cache-only mode).
        """
        self.session = session
        self._db_available = session is not None
        self.logger = get_logger()

        # Initialize cache based on config
        config = get_cache_config()
        self._cache_enabled = config["enabled"]
        self._cache_ttl = config["ttl"]

        if self._cache_enabled:
            self._disk_cache: FanoutCache | None = FanoutCache(
                directory=config["cache_dir"],
                shards=8,
                timeout=0.01,
            )
            self.logger.info("odds_cache_initialized", ttl=self._cache_ttl, cache_dir=config["cache_dir"])
        else:
            self._disk_cache = None
            self.logger.info("odds_cache_disabled")

    async def get_odds_for_game(
        self, game_id: str, force_refresh: bool = False
    ) -> list[HistoricalOdds]:
        """Get odds for a game, checking L1 cache, then L2 database.

        Args:
            game_id: NBA game identifier
            force_refresh: Skip cache and force database lookup

        Returns:
            List of HistoricalOdds for the game. Empty if not found in cache/db.
            Caller should fetch from API if empty.

        Examples:
            >>> odds = await repo.get_odds_for_game("0022300001")
            >>> if not odds:
            ...     # Cache miss - fetch from API
            ...     odds = await fetch_from_odds_api(game_id)
            ...     await repo.save_odds(odds)
        """
        cache_key = f"odds:{game_id}"

        # L1: Check diskcache if enabled and not forcing refresh
        if self._cache_enabled and self._disk_cache and not force_refresh:
            cached = self._disk_cache.get(cache_key)
            if cached is not None:
                self.logger.debug("cache_hit", source="disk", game_id=game_id)
                # Cached data is list of dicts, convert to HistoricalOdds
                return [
                    HistoricalOdds(
                        game_id=item["game_id"],
                        game_date=item["game_date"],
                        bookmaker=item["bookmaker"],
                        market=item["market"],
                        outcome=item["outcome"],
                        price=item["price"],
                        point=item["point"],
                        timestamp=item["timestamp"],
                    )
                    for item in cached
                ]

        # L2: Check database if available
        if self._db_available and self.session:
            stmt = select(HistoricalOddsModel).where(
                HistoricalOddsModel.game_id == game_id
            )
            result = await self.session.execute(stmt)
            models = result.scalars().all()

            if models:
                odds = [model_to_odds_dataclass(model) for model in models]
                self.logger.debug("cache_hit", source="database", game_id=game_id, count=len(odds))

                # Warm L1 cache for future lookups
                if self._cache_enabled and self._disk_cache:
                    odds_dicts = [
                        {
                            "game_id": o.game_id,
                            "game_date": o.game_date,
                            "bookmaker": o.bookmaker,
                            "market": o.market,
                            "outcome": o.outcome,
                            "price": o.price,
                            "point": o.point,
                            "timestamp": o.timestamp,
                        }
                        for o in odds
                    ]
                    self._disk_cache.set(cache_key, odds_dicts, expire=self._cache_ttl)

                return odds

        # L3: Not found in cache or database
        self.logger.debug("cache_miss", game_id=game_id, checked="disk_and_database")
        return []

    async def save_odds(self, odds: list[HistoricalOdds]) -> int:
        """Save odds to database and warm L1 cache.

        Uses upsert (INSERT ... ON CONFLICT) to handle duplicate records.
        Also warms L1 cache for each unique game_id if cache enabled.

        Args:
            odds: List of HistoricalOdds to save

        Returns:
            Number of records saved to database (0 if db not available)

        Examples:
            >>> odds = await fetch_from_odds_api("0022300001")
            >>> count = await repo.save_odds(odds)
            >>> print(f"Saved {count} odds records")
        """
        if not self._db_available or not self.session:
            self.logger.warning("save_odds_skipped", reason="database_not_available")
            return 0

        if not odds:
            return 0

        # Convert to dicts for bulk insert
        odds_dicts = [
            {
                "game_id": o.game_id,
                "game_date": o.game_date,
                "bookmaker": o.bookmaker,
                "market": o.market,
                "outcome": o.outcome,
                "price": o.price,
                "point": o.point,
                "timestamp": o.timestamp,
            }
            for o in odds
        ]

        # Use dialect-specific upsert
        # SQLite: INSERT OR REPLACE
        # PostgreSQL: INSERT ... ON CONFLICT DO UPDATE
        try:
            # Detect dialect from session bind
            dialect_name = self.session.bind.dialect.name if self.session.bind else "sqlite"

            if dialect_name == "postgresql":
                stmt = pg_insert(HistoricalOddsModel).values(odds_dicts)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["game_id", "bookmaker", "market", "outcome", "timestamp"],
                    set_={
                        "price": stmt.excluded.price,
                        "point": stmt.excluded.point,
                        "game_date": stmt.excluded.game_date,
                    },
                )
            else:  # sqlite
                stmt = sqlite_insert(HistoricalOddsModel).values(odds_dicts)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["id"],
                    set_={
                        "price": stmt.excluded.price,
                        "point": stmt.excluded.point,
                    },
                )

            await self.session.execute(stmt)
            await self.session.commit()

            self.logger.info("odds_saved", count=len(odds))

        except Exception as e:
            self.logger.error("odds_save_failed", error=str(e))
            await self.session.rollback()
            return 0

        # Warm L1 cache for each unique game_id
        if self._cache_enabled and self._disk_cache:
            # Group by game_id
            by_game: dict[str, list[dict]] = {}
            for odds_dict in odds_dicts:
                game_id = odds_dict["game_id"]
                if game_id not in by_game:
                    by_game[game_id] = []
                by_game[game_id].append(odds_dict)

            # Set cache for each game
            for game_id, game_odds in by_game.items():
                cache_key = f"odds:{game_id}"
                self._disk_cache.set(cache_key, game_odds, expire=self._cache_ttl)

            self.logger.debug("cache_warmed", games=len(by_game))

        return len(odds)

    async def get_odds_for_date_range(
        self, start: date, end: date
    ) -> list[HistoricalOdds]:
        """Get odds for all games within date range from database.

        This is a historical query operation, so it bypasses L1 cache
        and queries L2 database directly.

        Args:
            start: Start date (inclusive)
            end: End date (inclusive)

        Returns:
            List of HistoricalOdds ordered by game_date, timestamp

        Examples:
            >>> from datetime import date
            >>> odds = await repo.get_odds_for_date_range(
            ...     start=date(2024, 1, 1),
            ...     end=date(2024, 1, 31),
            ... )
            >>> print(f"Found {len(odds)} odds records in January 2024")
        """
        if not self._db_available or not self.session:
            self.logger.warning("get_odds_for_date_range_skipped", reason="database_not_available")
            return []

        # Convert dates to datetime for comparison
        start_dt = datetime.combine(start, datetime.min.time())
        end_dt = datetime.combine(end, datetime.max.time())

        stmt = (
            select(HistoricalOddsModel)
            .where(HistoricalOddsModel.game_date >= start_dt)
            .where(HistoricalOddsModel.game_date <= end_dt)
            .order_by(HistoricalOddsModel.game_date, HistoricalOddsModel.timestamp)
        )

        result = await self.session.execute(stmt)
        models = result.scalars().all()

        odds = [model_to_odds_dataclass(model) for model in models]

        self.logger.info(
            "odds_range_query",
            start=start.isoformat(),
            end=end.isoformat(),
            count=len(odds),
        )

        return odds

    def invalidate_cache(self, game_id: str) -> None:
        """Invalidate L1 cache for a specific game.

        Use this when odds have been updated and cache should be refreshed.

        Args:
            game_id: NBA game identifier to invalidate

        Examples:
            >>> repo.invalidate_cache("0022300001")
            >>> # Next get_odds_for_game will skip L1 and check L2/API
        """
        if self._cache_enabled and self._disk_cache:
            cache_key = f"odds:{game_id}"
            self._disk_cache.delete(cache_key)
            self.logger.debug("cache_invalidated", game_id=game_id)

    @property
    def cache_enabled(self) -> bool:
        """Check if L1 disk cache is enabled.

        Returns:
            True if cache is enabled, False otherwise
        """
        return self._cache_enabled

    def close_cache(self) -> None:
        """Close disk cache to release file handles.

        Important for Windows where open file handles prevent directory cleanup.
        Call this in test teardown or when done with repository.
        """
        if self._disk_cache is not None:
            self._disk_cache.close()
            self._disk_cache = None
