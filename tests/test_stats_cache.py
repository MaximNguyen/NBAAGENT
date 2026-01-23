"""Tests for StatsCache with TTL and stale-while-revalidate behavior."""

import asyncio
import time
from datetime import datetime
from unittest.mock import patch

import pytest

from nba_betting_agent.agents.stats_agent.cache import CacheEntry, StatsCache


@pytest.fixture
def cache():
    """Create test cache and clean up after."""
    test_cache = StatsCache(cache_dir=".cache/test_nba_stats")
    yield test_cache
    test_cache.clear()


def test_cache_set_and_get(cache):
    """Test basic set/get roundtrip."""
    data = {"team": "BOS", "pts": 118.5}
    cache._set_sync("test_key", data, "team_stats")

    entry = cache.get_sync("test_key", "team_stats")
    assert entry is not None
    assert entry.data == data
    assert entry.is_stale is False
    assert isinstance(entry.fetched_at, datetime)


def test_cache_returns_none_for_missing_key(cache):
    """Test that missing keys return None."""
    entry = cache.get_sync("nonexistent_key", "team_stats")
    assert entry is None


def test_cache_detects_stale_data(cache):
    """Test stale detection by mocking time.

    Cache entry should be marked stale when age > ttl but < stale_max.
    """
    data = {"team": "LAL", "pts": 115.2}

    # Mock current time as 0
    with patch("time.time", return_value=0):
        cache._set_sync("stale_test", data, "team_stats")

    # Fast forward 25 hours (past 24h ttl, within 48h stale_max)
    with patch("time.time", return_value=25 * 3600):
        entry = cache.get_sync("stale_test", "team_stats")

        assert entry is not None, "Should return stale data within stale_max window"
        assert entry.is_stale is True, "Should be marked as stale"
        assert entry.data == data

    # Fast forward 50 hours (past 48h stale_max)
    with patch("time.time", return_value=50 * 3600):
        entry = cache.get_sync("stale_test", "team_stats")
        assert entry is None, "Should return None when too stale"


@pytest.mark.asyncio
async def test_async_get_set(cache):
    """Test async versions of get/set."""
    data = {"team": "GSW", "pts": 120.8}

    await cache.set("async_test", data, "team_stats")
    entry = await cache.get("async_test", "team_stats")

    assert entry is not None
    assert entry.data == data
    assert entry.is_stale is False


def test_cache_respects_data_type_ttl(cache):
    """Test that different data types have different TTLs.

    injuries has 1h TTL, team_stats has 24h TTL.
    """
    team_data = {"team": "BOS", "pts": 118.5}
    injury_data = {"player": "Jaylen Brown", "status": "Out"}

    # Set both at time 0
    with patch("time.time", return_value=0):
        cache._set_sync("team_key", team_data, "team_stats")
        cache._set_sync("injury_key", injury_data, "injuries")

    # Check at 2 hours - injuries should be stale, team_stats should be fresh
    with patch("time.time", return_value=2 * 3600):
        team_entry = cache.get_sync("team_key", "team_stats")
        injury_entry = cache.get_sync("injury_key", "injuries")

        assert team_entry is not None
        assert team_entry.is_stale is False, "team_stats should still be fresh (24h TTL)"

        assert injury_entry is not None
        assert (
            injury_entry.is_stale is True
        ), "injuries should be stale (1h TTL, 2h elapsed)"


def test_clear_removes_all_data(cache):
    """Test that clear() removes all cached data."""
    data1 = {"key": "value1"}
    data2 = {"key": "value2"}

    cache._set_sync("key1", data1, "team_stats")
    cache._set_sync("key2", data2, "injuries")

    # Verify data exists
    assert cache.get_sync("key1", "team_stats") is not None
    assert cache.get_sync("key2", "injuries") is not None

    # Clear and verify empty
    cache.clear()
    assert cache.get_sync("key1", "team_stats") is None
    assert cache.get_sync("key2", "injuries") is None


def test_cache_entry_dataclass():
    """Test CacheEntry dataclass structure."""
    now = datetime.now()
    entry = CacheEntry(data={"test": "data"}, fetched_at=now, is_stale=True)

    assert entry.data == {"test": "data"}
    assert entry.fetched_at == now
    assert entry.is_stale is True

    # Test default is_stale=False
    entry2 = CacheEntry(data={}, fetched_at=now)
    assert entry2.is_stale is False


@pytest.mark.asyncio
async def test_concurrent_async_operations(cache):
    """Test that async operations can run concurrently."""
    data_sets = [
        {"key": f"team_{i}", "data": {"team": f"TEAM{i}", "pts": 100.0 + i}}
        for i in range(10)
    ]

    # Write concurrently
    write_tasks = [
        cache.set(item["key"], item["data"], "team_stats") for item in data_sets
    ]
    await asyncio.gather(*write_tasks)

    # Read concurrently
    read_tasks = [cache.get(item["key"], "team_stats") for item in data_sets]
    entries = await asyncio.gather(*read_tasks)

    # Verify all entries
    assert len(entries) == 10
    for i, entry in enumerate(entries):
        assert entry is not None
        assert entry.data["team"] == f"TEAM{i}"
        assert entry.data["pts"] == 100.0 + i
