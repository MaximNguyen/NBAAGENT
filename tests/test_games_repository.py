"""Tests for GamesRepository with database and API fallback behavior.

Tests verify:
- Database queries return stored games
- API fallback when database is empty
- API fallback when database is unavailable
- Bulk save with idempotent conflict handling
- Health checks for database connectivity
"""

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from nba_betting_agent.db.models import Base, HistoricalGameModel
from nba_betting_agent.db.repositories.games import GamesRepository
from nba_betting_agent.ml.data.schema import HistoricalGame


@pytest_asyncio.fixture
async def test_engine():
    """Create in-memory SQLite engine for testing."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture
async def test_session(test_engine):
    """Create async session for testing."""
    async_session = sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session() as session:
        yield session


@pytest.fixture
def sample_games():
    """Create sample historical games for testing."""
    return [
        HistoricalGame(
            game_id="0022300001",
            game_date=datetime(2024, 1, 15, 19, 0),
            season="2023-24",
            home_team="BOS",
            away_team="LAL",
            home_score=115,
            away_score=110,
        ),
        HistoricalGame(
            game_id="0022300002",
            game_date=datetime(2024, 1, 16, 20, 0),
            season="2023-24",
            home_team="GSW",
            away_team="MIL",
            home_score=120,
            away_score=118,
        ),
        HistoricalGame(
            game_id="0022300003",
            game_date=datetime(2024, 1, 17, 19, 30),
            season="2023-24",
            home_team="PHX",
            away_team="DEN",
            home_score=105,
            away_score=112,
        ),
    ]


@pytest.mark.asyncio
async def test_get_games_by_season_empty_db(test_session, sample_games):
    """Test get_by_season falls back to API when database is empty."""
    repo = GamesRepository(session=test_session)

    # Mock the API loader to return sample games
    with patch("nba_betting_agent.db.repositories.games.load_historical_games") as mock_load:
        mock_load.return_value = sample_games

        # Call get_by_season - should trigger API fallback
        games = await repo.get_by_season("2023-24")

        # Verify API was called
        mock_load.assert_called_once_with(["2023-24"])

        # Verify games returned
        assert len(games) == 3
        assert games[0].game_id == "0022300001"
        assert games[1].home_team == "GSW"
        assert games[2].away_team == "DEN"

    # Verify games were saved to database (backfill)
    stmt = select(HistoricalGameModel).where(HistoricalGameModel.season == "2023-24")
    result = await test_session.execute(stmt)
    db_games = result.scalars().all()
    assert len(db_games) == 3


@pytest.mark.asyncio
async def test_get_games_by_season_from_db(test_session, sample_games):
    """Test get_by_season returns games from database when available."""
    repo = GamesRepository(session=test_session)

    # Pre-populate database with games
    saved_count = await repo.bulk_save(sample_games)
    assert saved_count == 3

    # Mock API to verify it's NOT called
    with patch("nba_betting_agent.db.repositories.games.load_historical_games") as mock_load:
        games = await repo.get_by_season("2023-24")

        # Verify API was NOT called (database hit)
        mock_load.assert_not_called()

        # Verify games returned from database
        assert len(games) == 3
        assert games[0].game_id == "0022300001"
        assert games[1].home_team == "GSW"
        assert games[2].away_score == 112


@pytest.mark.asyncio
async def test_get_games_by_season_sorted_by_date(test_session, sample_games):
    """Test games are returned sorted by date ascending."""
    repo = GamesRepository(session=test_session)

    # Save games out of order
    await repo.bulk_save([sample_games[2], sample_games[0], sample_games[1]])

    games = await repo.get_by_season("2023-24", fallback_to_api=False)

    # Verify sorted by date
    assert len(games) == 3
    assert games[0].game_date == datetime(2024, 1, 15, 19, 0)
    assert games[1].game_date == datetime(2024, 1, 16, 20, 0)
    assert games[2].game_date == datetime(2024, 1, 17, 19, 30)


@pytest.mark.asyncio
async def test_bulk_save_idempotent(test_session, sample_games):
    """Test bulk_save can be called multiple times without errors."""
    repo = GamesRepository(session=test_session)

    # Save games first time
    count1 = await repo.bulk_save(sample_games)
    assert count1 == 3

    # Save same games again (should not error or duplicate)
    count2 = await repo.bulk_save(sample_games)
    assert count2 == 3  # SQLite OR IGNORE doesn't return affected rows

    # Verify no duplicates in database
    stmt = select(HistoricalGameModel).where(HistoricalGameModel.season == "2023-24")
    result = await test_session.execute(stmt)
    db_games = result.scalars().all()
    assert len(db_games) == 3  # Still only 3, no duplicates


@pytest.mark.asyncio
async def test_graceful_degradation_no_session(sample_games):
    """Test repository falls back to API when no session provided."""
    repo = GamesRepository(session=None)

    # Verify database marked as unavailable
    assert repo._db_available is False

    # Mock API
    with patch("nba_betting_agent.db.repositories.games.load_historical_games") as mock_load:
        mock_load.return_value = sample_games

        games = await repo.get_by_season("2023-24")

        # Verify API fallback was used
        mock_load.assert_called_once_with(["2023-24"])
        assert len(games) == 3


@pytest.mark.asyncio
async def test_graceful_degradation_no_fallback(test_session):
    """Test repository returns empty list when fallback disabled."""
    repo = GamesRepository(session=test_session)

    # Request games with fallback disabled - database empty
    games = await repo.get_by_season("2023-24", fallback_to_api=False)

    # Should return empty list, not call API
    assert games == []


@pytest.mark.asyncio
async def test_check_health_success(test_session):
    """Test health check passes with valid session."""
    repo = GamesRepository(session=test_session)

    health = await repo.check_health()

    assert health is True
    assert repo._db_available is True


@pytest.mark.asyncio
async def test_check_health_failure():
    """Test health check fails with broken session."""
    # Create a mock session that raises errors
    from unittest.mock import AsyncMock, MagicMock

    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.execute = AsyncMock(side_effect=RuntimeError("Connection failed"))

    repo = GamesRepository(session=mock_session)

    # Health check should fail
    health = await repo.check_health()

    assert health is False
    assert repo._db_available is False


@pytest.mark.asyncio
async def test_get_count_by_season(test_session, sample_games):
    """Test get_count_by_season returns correct count."""
    repo = GamesRepository(session=test_session)

    # Empty database
    count = await repo.get_count_by_season("2023-24")
    assert count == 0

    # Save games
    await repo.bulk_save(sample_games)

    # Count should match
    count = await repo.get_count_by_season("2023-24")
    assert count == 3

    # Different season should be 0
    count = await repo.get_count_by_season("2022-23")
    assert count == 0


@pytest.mark.asyncio
async def test_get_count_when_unavailable():
    """Test get_count returns 0 when database unavailable."""
    repo = GamesRepository(session=None)

    count = await repo.get_count_by_season("2023-24")

    assert count == 0


@pytest.mark.asyncio
async def test_bulk_save_when_unavailable(sample_games):
    """Test bulk_save returns 0 when database unavailable."""
    repo = GamesRepository(session=None)

    count = await repo.bulk_save(sample_games)

    assert count == 0


@pytest.mark.asyncio
async def test_bulk_save_empty_list(test_session):
    """Test bulk_save handles empty list gracefully."""
    repo = GamesRepository(session=test_session)

    count = await repo.bulk_save([])

    assert count == 0


@pytest.mark.asyncio
async def test_database_error_triggers_fallback(test_session, sample_games):
    """Test database errors mark repository as unavailable and trigger fallback."""
    repo = GamesRepository(session=test_session)

    # Mock session.execute to raise error
    original_execute = test_session.execute

    async def failing_execute(*args, **kwargs):
        raise RuntimeError("Database connection lost")

    test_session.execute = failing_execute

    # Mock API fallback
    with patch("nba_betting_agent.db.repositories.games.load_historical_games") as mock_load:
        mock_load.return_value = sample_games

        games = await repo.get_by_season("2023-24")

        # Should have fallen back to API
        mock_load.assert_called_once()
        assert len(games) == 3

        # Repository should be marked unavailable
        assert repo._db_available is False

    # Restore
    test_session.execute = original_execute


@pytest.mark.asyncio
async def test_multiple_seasons_distinct(test_session):
    """Test repository can handle games from multiple seasons."""
    repo = GamesRepository(session=test_session)

    # Create games for different seasons
    season1_games = [
        HistoricalGame(
            game_id="0022300001",
            game_date=datetime(2024, 1, 15),
            season="2023-24",
            home_team="BOS",
            away_team="LAL",
            home_score=110,
            away_score=105,
        ),
    ]

    season2_games = [
        HistoricalGame(
            game_id="0022200001",
            game_date=datetime(2023, 1, 15),
            season="2022-23",
            home_team="GSW",
            away_team="MIL",
            home_score=115,
            away_score=112,
        ),
    ]

    # Save both seasons
    await repo.bulk_save(season1_games)
    await repo.bulk_save(season2_games)

    # Query each season separately
    s1_games = await repo.get_by_season("2023-24", fallback_to_api=False)
    s2_games = await repo.get_by_season("2022-23", fallback_to_api=False)

    assert len(s1_games) == 1
    assert len(s2_games) == 1
    assert s1_games[0].season == "2023-24"
    assert s2_games[0].season == "2022-23"


@pytest.mark.asyncio
async def test_dataclass_model_conversion(test_session, sample_games):
    """Test conversion between frozen dataclasses and mutable models."""
    repo = GamesRepository(session=test_session)

    # Save dataclass
    await repo.bulk_save([sample_games[0]])

    # Retrieve and verify fields match
    games = await repo.get_by_season("2023-24", fallback_to_api=False)
    game = games[0]

    # Verify all fields converted correctly
    assert game.game_id == "0022300001"
    assert game.game_date == datetime(2024, 1, 15, 19, 0)
    assert game.season == "2023-24"
    assert game.home_team == "BOS"
    assert game.away_team == "LAL"
    assert game.home_score == 115
    assert game.away_score == 110
    assert game.home_win is True  # Computed field
    assert game.spread == 5.0  # Computed field
    assert game.total == 225.0  # Computed field
