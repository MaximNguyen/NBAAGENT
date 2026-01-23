"""Disk-based caching with TTL and stale-while-revalidate patterns.

Uses diskcache.FanoutCache for thread-safe disk caching with automatic TTL expiration.
Supports async operations via run_in_executor wrapper.
"""

import asyncio
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from diskcache import FanoutCache


@dataclass
class CacheEntry:
    """Represents cached data with metadata.

    Attributes:
        data: Cached dictionary data
        fetched_at: Timestamp when data was originally fetched
        is_stale: Whether data is past TTL but within stale_max window
    """

    data: dict
    fetched_at: datetime
    is_stale: bool = False


# TTL configuration for different data types
# Format: {data_type: {"ttl": seconds, "stale_max": seconds}}
TTL_CONFIG = {
    "team_stats": {"ttl": 86400, "stale_max": 172800},  # 24h / 48h
    "team_advanced": {"ttl": 86400, "stale_max": 172800},  # 24h / 48h
    "injuries": {"ttl": 3600, "stale_max": 14400},  # 1h / 4h
    "schedule": {"ttl": 21600, "stale_max": 43200},  # 6h / 12h
}


class StatsCache:
    """Thread-safe disk cache with TTL expiration and stale-while-revalidate support.

    Uses diskcache.FanoutCache (8 shards) for concurrent write performance.
    Provides async methods via run_in_executor for LangGraph integration.

    Cache directory structure:
        .cache/nba_stats/
            00.db  # Shard 0
            01.db  # Shard 1
            ...
            07.db  # Shard 7

    Example:
        cache = StatsCache()

        # Async usage
        entry = await cache.get("team_stats:BOS", "team_stats")
        if entry is None:
            data = await fetch_data()
            await cache.set("team_stats:BOS", data, "team_stats")
        elif entry.is_stale:
            print("Using stale cache, refresh in background")

        # Sync fallback
        entry = cache.get_sync("team_stats:BOS", "team_stats")
    """

    def __init__(self, cache_dir: str = ".cache/nba_stats"):
        """Initialize FanoutCache with 8 shards.

        Args:
            cache_dir: Directory for cache storage (default: .cache/nba_stats)
        """
        self._cache = FanoutCache(
            directory=cache_dir,
            shards=8,  # One per concurrent writer recommended
            timeout=0.01,  # 10ms timeout for lock acquisition
        )

    async def get(self, key: str, data_type: str) -> CacheEntry | None:
        """Async get with stale detection.

        Args:
            key: Cache key (e.g., "team_stats:BOS")
            data_type: Data type from TTL_CONFIG (e.g., "team_stats")

        Returns:
            CacheEntry with is_stale=True if past TTL but within stale_max,
            None if missing or too stale to use
        """
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, self._get_sync, key, data_type)
        return result

    async def set(self, key: str, data: dict, data_type: str) -> None:
        """Async set with TTL from config.

        Args:
            key: Cache key
            data: Dictionary to cache
            data_type: Data type from TTL_CONFIG for TTL lookup
        """
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._set_sync, key, data, data_type)

    def get_sync(self, key: str, data_type: str) -> CacheEntry | None:
        """Synchronous get (fallback for non-async contexts).

        Args:
            key: Cache key
            data_type: Data type from TTL_CONFIG

        Returns:
            CacheEntry or None
        """
        return self._get_sync(key, data_type)

    def _get_sync(self, key: str, data_type: str) -> CacheEntry | None:
        """Internal synchronous get implementation.

        Implements stale-while-revalidate pattern:
        - Fresh (age <= ttl): return with is_stale=False
        - Stale (ttl < age <= stale_max): return with is_stale=True
        - Too stale (age > stale_max): return None

        Args:
            key: Cache key
            data_type: Data type from TTL_CONFIG

        Returns:
            CacheEntry or None
        """
        config = TTL_CONFIG.get(data_type, {"ttl": 86400, "stale_max": 172800})
        cached = self._cache.get(key, expire_time=True, default=None)

        if cached is None:
            return None

        value, expire_time = cached

        # If no expiration set (shouldn't happen, but handle gracefully)
        if expire_time is None:
            return CacheEntry(data=value, fetched_at=datetime.now())

        # Calculate age and stale status
        ttl = config["ttl"]
        stale_max = config["stale_max"]
        age = time.time() - (expire_time - ttl)

        if age > stale_max:
            return None  # Too stale to use

        is_stale = age > ttl
        fetched_at = datetime.fromtimestamp(expire_time - ttl)
        return CacheEntry(data=value, fetched_at=fetched_at, is_stale=is_stale)

    def _set_sync(self, key: str, data: dict, data_type: str) -> None:
        """Internal synchronous set implementation.

        Args:
            key: Cache key
            data: Dictionary to cache
            data_type: Data type from TTL_CONFIG for TTL lookup
        """
        config = TTL_CONFIG.get(data_type, {"ttl": 86400, "stale_max": 172800})
        ttl = config["ttl"]
        self._cache.set(key, data, expire=ttl)

    def clear(self) -> None:
        """Clear entire cache (for testing).

        Warning: Removes all cached data across all shards.
        """
        self._cache.clear()
