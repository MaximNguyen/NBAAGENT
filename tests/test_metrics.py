"""Tests for production metrics dataclasses.

Tests CacheMetrics and SportsbookMetrics from the monitoring module.
"""

import pytest
from datetime import datetime

from nba_betting_agent.monitoring.metrics import CacheMetrics, SportsbookMetrics


class TestCacheMetrics:
    """Tests for CacheMetrics dataclass."""

    def test_cache_metrics_hit_rate(self):
        """Hit rate includes both fresh and stale hits."""
        metrics = CacheMetrics(hits=80, misses=15, stale_hits=5)
        assert metrics.hit_rate == 85.0  # (80+5)/100 * 100
        assert metrics.fresh_hit_rate == 80.0

    def test_cache_metrics_empty(self):
        """Empty metrics return 0.0 for rates."""
        metrics = CacheMetrics()
        assert metrics.hits == 0
        assert metrics.misses == 0
        assert metrics.stale_hits == 0
        assert metrics.hit_rate == 0.0
        assert metrics.fresh_hit_rate == 0.0

    def test_cache_metrics_to_dict(self):
        """to_dict includes all fields and computed properties."""
        metrics = CacheMetrics(hits=10, misses=5, stale_hits=2)
        d = metrics.to_dict()

        assert d["hits"] == 10
        assert d["misses"] == 5
        assert d["stale_hits"] == 2
        assert "hit_rate" in d
        assert "fresh_hit_rate" in d
        # Verify computed rates
        assert d["hit_rate"] == pytest.approx(70.6, rel=0.1)  # (10+2)/17*100 = 70.6
        assert d["fresh_hit_rate"] == pytest.approx(58.8, rel=0.1)  # 10/17*100 = 58.8

    def test_cache_metrics_all_misses(self):
        """All misses results in 0% hit rate."""
        metrics = CacheMetrics(hits=0, misses=100, stale_hits=0)
        assert metrics.hit_rate == 0.0
        assert metrics.fresh_hit_rate == 0.0

    def test_cache_metrics_all_stale_hits(self):
        """All stale hits gives 100% hit rate but 0% fresh hit rate."""
        metrics = CacheMetrics(hits=0, misses=0, stale_hits=50)
        assert metrics.hit_rate == 100.0
        assert metrics.fresh_hit_rate == 0.0

    def test_cache_metrics_all_fresh_hits(self):
        """All fresh hits gives 100% for both rates."""
        metrics = CacheMetrics(hits=100, misses=0, stale_hits=0)
        assert metrics.hit_rate == 100.0
        assert metrics.fresh_hit_rate == 100.0


class TestSportsbookMetrics:
    """Tests for SportsbookMetrics dataclass."""

    def test_sportsbook_metrics_creation(self):
        """Create SportsbookMetrics with all fields."""
        now = datetime.now()
        sm = SportsbookMetrics(
            name="draftkings",
            games_with_odds=8,
            markets_available=["h2h", "spreads", "totals"],
            last_seen=now,
            availability_pct=80.0,
        )

        assert sm.name == "draftkings"
        assert sm.games_with_odds == 8
        assert sm.markets_available == ["h2h", "spreads", "totals"]
        assert sm.last_seen == now
        assert sm.availability_pct == 80.0

    def test_sportsbook_metrics_defaults(self):
        """Default values work correctly."""
        sm = SportsbookMetrics(name="fanduel")

        assert sm.name == "fanduel"
        assert sm.games_with_odds == 0
        assert sm.markets_available == []
        assert sm.last_seen is None
        assert sm.availability_pct == 0.0

    def test_sportsbook_metrics_markets_list(self):
        """Markets available is a mutable list."""
        sm = SportsbookMetrics(name="betmgm", markets_available=["h2h"])
        sm.markets_available.append("spreads")

        assert "spreads" in sm.markets_available

    def test_sportsbook_metrics_100_percent_availability(self):
        """100% availability when book has odds for all games."""
        sm = SportsbookMetrics(
            name="bovada",
            games_with_odds=10,
            availability_pct=100.0,
        )

        assert sm.availability_pct == 100.0


class TestCacheMetricsIntegration:
    """Integration tests for cache metrics with StatsCache."""

    def test_stats_cache_has_metrics(self):
        """StatsCache initializes with CacheMetrics."""
        from nba_betting_agent.agents.stats_agent.cache import StatsCache

        cache = StatsCache(cache_dir=".cache/test_metrics")
        try:
            assert hasattr(cache, "metrics")
            assert isinstance(cache.metrics, CacheMetrics)
            assert cache.metrics.hits == 0
            assert cache.metrics.misses == 0
        finally:
            cache.clear()

    def test_stats_cache_get_metrics(self):
        """get_metrics() returns dict with all fields."""
        from nba_betting_agent.agents.stats_agent.cache import StatsCache

        cache = StatsCache(cache_dir=".cache/test_metrics")
        try:
            metrics = cache.get_metrics()
            assert isinstance(metrics, dict)
            assert "hits" in metrics
            assert "misses" in metrics
            assert "stale_hits" in metrics
            assert "hit_rate" in metrics
            assert "fresh_hit_rate" in metrics
        finally:
            cache.clear()

    def test_stats_cache_reset_metrics(self):
        """reset_metrics() clears counters."""
        from nba_betting_agent.agents.stats_agent.cache import StatsCache

        cache = StatsCache(cache_dir=".cache/test_metrics")
        try:
            # Add some data and access it
            cache._set_sync("test_key", {"data": 1}, "team_stats")
            cache.get_sync("test_key", "team_stats")  # hit
            cache.get_sync("nonexistent", "team_stats")  # miss

            assert cache.metrics.hits >= 1
            assert cache.metrics.misses >= 1

            # Reset and verify
            cache.reset_metrics()
            assert cache.metrics.hits == 0
            assert cache.metrics.misses == 0
            assert cache.metrics.stale_hits == 0
        finally:
            cache.clear()

    def test_stats_cache_tracks_hits(self):
        """Cache hit increments hits counter."""
        from nba_betting_agent.agents.stats_agent.cache import StatsCache

        cache = StatsCache(cache_dir=".cache/test_metrics")
        try:
            cache.reset_metrics()  # Start fresh
            cache._set_sync("hit_test", {"data": 1}, "team_stats")

            initial_hits = cache.metrics.hits
            cache.get_sync("hit_test", "team_stats")

            assert cache.metrics.hits == initial_hits + 1
        finally:
            cache.clear()

    def test_stats_cache_tracks_misses(self):
        """Cache miss increments misses counter."""
        from nba_betting_agent.agents.stats_agent.cache import StatsCache

        cache = StatsCache(cache_dir=".cache/test_metrics")
        try:
            cache.reset_metrics()  # Start fresh

            initial_misses = cache.metrics.misses
            cache.get_sync("nonexistent_key", "team_stats")

            assert cache.metrics.misses == initial_misses + 1
        finally:
            cache.clear()
