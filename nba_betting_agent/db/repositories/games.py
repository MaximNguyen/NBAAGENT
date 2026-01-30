"""Games repository with graceful degradation to API fallback.

Provides database access for historical games with automatic fallback
to NBA API when database is unavailable.
"""

from typing import Any

from sqlalchemy import func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from nba_betting_agent.db.models import (
    HistoricalGameModel,
    game_dataclass_to_model,
    model_to_game_dataclass,
)
from nba_betting_agent.ml.data.historical import load_historical_games
from nba_betting_agent.ml.data.schema import HistoricalGame
from nba_betting_agent.monitoring import get_logger


class GamesRepository:
    """Repository for historical games with graceful degradation.

    Provides data access layer for historical NBA games. When database is
    unavailable, automatically falls back to NBA API data loader.

    This pattern enables:
    - Clean separation between data access and business logic
    - Graceful degradation when database is down
    - Easy testing with mock sessions

    Attributes:
        session: AsyncSession for database operations (None if unavailable)
        _db_available: Track database availability state
        logger: Structured logger instance
    """

    def __init__(self, session: AsyncSession | None = None):
        """Initialize repository with optional database session.

        Args:
            session: AsyncSession for database ops. If None, falls back to API.
        """
        self.session = session
        self._db_available = session is not None
        self.logger = get_logger()

    async def get_by_season(
        self, season: str, fallback_to_api: bool = True
    ) -> list[HistoricalGame]:
        """Get games for a season from database or API fallback.

        Query priority:
        1. Database (if available and has data)
        2. API fallback (if enabled and DB empty/unavailable)
        3. Empty list (if fallback disabled)

        Args:
            season: NBA season string (e.g., "2023-24")
            fallback_to_api: Whether to use API when DB unavailable/empty

        Returns:
            List of HistoricalGame objects, sorted by date ascending

        Example:
            repo = GamesRepository(session)
            games = await repo.get_by_season("2023-24")
            print(f"Found {len(games)} games")
        """
        # Fast path: database unavailable, use API immediately
        if not self._db_available:
            if fallback_to_api:
                self.logger.warning(
                    "games_repo_db_unavailable",
                    season=season,
                    fallback="api",
                    message="Database unavailable, using API fallback",
                )
                return load_historical_games([season])
            else:
                self.logger.warning(
                    "games_repo_db_unavailable",
                    season=season,
                    fallback="none",
                    message="Database unavailable and fallback disabled",
                )
                return []

        # Try database query
        try:
            stmt = (
                select(HistoricalGameModel)
                .where(HistoricalGameModel.season == season)
                .order_by(HistoricalGameModel.game_date)
            )

            result = await self.session.execute(stmt)
            models = result.scalars().all()

            if models:
                # Convert models to dataclasses
                games = [model_to_game_dataclass(model) for model in models]
                self.logger.info(
                    "games_repo_db_hit",
                    season=season,
                    count=len(games),
                )
                return games

            # Database is up but has no data for this season
            if fallback_to_api:
                self.logger.info(
                    "games_repo_db_empty",
                    season=season,
                    message="No games in database, fetching from API",
                )
                # Fetch from API and save to database
                api_games = load_historical_games([season])
                if api_games:
                    # Store in database for future queries
                    await self.bulk_save(api_games)
                    self.logger.info(
                        "games_repo_backfill_completed",
                        season=season,
                        count=len(api_games),
                    )
                return api_games
            else:
                return []

        except Exception as e:
            # Database error - mark as unavailable and fall back
            self.logger.error(
                "games_repo_db_error",
                season=season,
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True,
            )
            self._db_available = False

            if fallback_to_api:
                self.logger.info(
                    "games_repo_api_fallback",
                    season=season,
                    message="Database error, falling back to API",
                )
                return load_historical_games([season])
            else:
                return []

    async def bulk_save(self, games: list[HistoricalGame]) -> int:
        """Bulk insert games into database with conflict handling.

        Uses database-specific conflict resolution:
        - SQLite: OR IGNORE for duplicate game_ids
        - PostgreSQL: ON CONFLICT DO NOTHING

        This enables idempotent saves - calling multiple times with same
        games won't cause errors or duplicates.

        Args:
            games: List of HistoricalGame dataclasses to save

        Returns:
            Number of games inserted (may be less than input if duplicates)

        Example:
            games = load_historical_games(["2023-24"])
            count = await repo.bulk_save(games)
            print(f"Saved {count} games")
        """
        if not self._db_available:
            self.logger.warning(
                "games_repo_bulk_save_skipped",
                count=len(games),
                reason="database_unavailable",
            )
            return 0

        if not games:
            return 0

        try:
            # Convert dataclasses to dicts for bulk insert
            game_dicts: list[dict[str, Any]] = []
            for game in games:
                model = game_dataclass_to_model(game)
                game_dict = {
                    "game_id": model.game_id,
                    "game_date": model.game_date,
                    "season": model.season,
                    "home_team": model.home_team,
                    "away_team": model.away_team,
                    "home_score": model.home_score,
                    "away_score": model.away_score,
                    "home_win": model.home_win,
                    "spread": model.spread,
                    "total": model.total,
                }
                game_dicts.append(game_dict)

            # Build insert statement with conflict handling
            stmt = insert(HistoricalGameModel).values(game_dicts)

            # Detect database dialect for conflict handling
            dialect_name = self.session.bind.dialect.name

            if dialect_name == "sqlite":
                # SQLite uses OR IGNORE
                stmt = stmt.prefix_with("OR IGNORE")
            elif dialect_name == "postgresql":
                # PostgreSQL uses ON CONFLICT DO NOTHING
                from sqlalchemy.dialects.postgresql import insert as pg_insert

                stmt = pg_insert(HistoricalGameModel).values(game_dicts)
                stmt = stmt.on_conflict_do_nothing(index_elements=["game_id"])

            # Execute insert
            await self.session.execute(stmt)
            await self.session.commit()

            self.logger.info(
                "games_repo_bulk_save_completed",
                count=len(games),
            )

            return len(games)

        except Exception as e:
            self.logger.error(
                "games_repo_bulk_save_failed",
                count=len(games),
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True,
            )
            await self.session.rollback()
            return 0

    async def get_count_by_season(self, season: str) -> int:
        """Get count of games in database for a season.

        Useful for checking if data exists before querying.

        Args:
            season: NBA season string (e.g., "2023-24")

        Returns:
            Number of games for this season in database (0 if unavailable)

        Example:
            count = await repo.get_count_by_season("2023-24")
            if count > 0:
                games = await repo.get_by_season("2023-24", fallback_to_api=False)
        """
        if not self._db_available:
            return 0

        try:
            stmt = select(func.count()).select_from(HistoricalGameModel).where(
                HistoricalGameModel.season == season
            )

            result = await self.session.execute(stmt)
            count = result.scalar() or 0
            return count

        except Exception as e:
            self.logger.error(
                "games_repo_count_failed",
                season=season,
                error=str(e),
                error_type=type(e).__name__,
            )
            return 0

    async def check_health(self) -> bool:
        """Check if database connection is healthy.

        Executes a simple query to verify connectivity. Updates internal
        _db_available flag based on result.

        Returns:
            True if database is healthy, False otherwise

        Example:
            if await repo.check_health():
                games = await repo.get_by_season("2023-24", fallback_to_api=False)
            else:
                print("Database unavailable")
        """
        if not self._db_available:
            return False

        try:
            # Simple health check query
            await self.session.execute(select(1))
            self._db_available = True
            return True

        except Exception as e:
            self.logger.warning(
                "games_repo_health_check_failed",
                error=str(e),
                error_type=type(e).__name__,
            )
            self._db_available = False
            return False
