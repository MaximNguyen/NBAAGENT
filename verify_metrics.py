#!/usr/bin/env python3
"""Verification script for 06-03 metrics implementation.

Run this script to verify:
1. CacheMetrics and SportsbookMetrics dataclasses work
2. StatsCache metrics tracking works
3. OddsAPIClient sportsbook metrics tracking works (import only - no API call)

Usage:
    python verify_metrics.py
"""

import sys


def verify_imports():
    """Verify all new imports work."""
    print("Testing imports...")

    try:
        from nba_betting_agent.monitoring import SportsbookMetrics, CacheMetrics

        print("  [OK] SportsbookMetrics imported from monitoring")
        print("  [OK] CacheMetrics imported from monitoring")
    except ImportError as e:
        print(f"  [FAIL] Import error: {e}")
        return False

    try:
        from nba_betting_agent.monitoring.metrics import SportsbookMetrics, CacheMetrics

        print("  [OK] Direct import from metrics module")
    except ImportError as e:
        print(f"  [FAIL] Import error: {e}")
        return False

    return True


def verify_cache_metrics():
    """Verify CacheMetrics dataclass works."""
    print("\nTesting CacheMetrics...")

    from nba_betting_agent.monitoring.metrics import CacheMetrics

    # Empty metrics
    cm = CacheMetrics()
    assert cm.hits == 0
    assert cm.misses == 0
    assert cm.stale_hits == 0
    assert cm.hit_rate == 0.0
    assert cm.fresh_hit_rate == 0.0
    print("  [OK] Empty CacheMetrics defaults to zeros")

    # Metrics with values
    cm = CacheMetrics(hits=80, misses=15, stale_hits=5)
    assert cm.hit_rate == 85.0, f"Expected 85.0, got {cm.hit_rate}"
    assert cm.fresh_hit_rate == 80.0, f"Expected 80.0, got {cm.fresh_hit_rate}"
    print(f"  [OK] Hit rate: {cm.hit_rate}% (expected 85.0%)")
    print(f"  [OK] Fresh hit rate: {cm.fresh_hit_rate}% (expected 80.0%)")

    # to_dict method
    d = cm.to_dict()
    assert "hits" in d
    assert "misses" in d
    assert "stale_hits" in d
    assert "hit_rate" in d
    assert "fresh_hit_rate" in d
    print(f"  [OK] to_dict() returns: {d}")

    return True


def verify_sportsbook_metrics():
    """Verify SportsbookMetrics dataclass works."""
    print("\nTesting SportsbookMetrics...")

    from datetime import datetime

    from nba_betting_agent.monitoring.metrics import SportsbookMetrics

    # Default values
    sm = SportsbookMetrics(name="draftkings")
    assert sm.name == "draftkings"
    assert sm.games_with_odds == 0
    assert sm.markets_available == []
    assert sm.last_seen is None
    assert sm.availability_pct == 0.0
    print("  [OK] SportsbookMetrics defaults work")

    # Full values
    now = datetime.now()
    sm = SportsbookMetrics(
        name="fanduel",
        games_with_odds=10,
        markets_available=["h2h", "spreads", "totals"],
        last_seen=now,
        availability_pct=100.0,
    )
    assert sm.name == "fanduel"
    assert sm.games_with_odds == 10
    assert len(sm.markets_available) == 3
    assert sm.last_seen == now
    assert sm.availability_pct == 100.0
    print(f"  [OK] Full SportsbookMetrics: {sm.name}, {sm.games_with_odds} games, {sm.availability_pct}%")

    return True


def verify_stats_cache_metrics():
    """Verify StatsCache has metrics tracking."""
    print("\nTesting StatsCache metrics...")

    from nba_betting_agent.agents.stats_agent.cache import StatsCache
    from nba_betting_agent.monitoring.metrics import CacheMetrics

    cache = StatsCache(cache_dir=".cache/verify_metrics")
    try:
        # Has metrics attribute
        assert hasattr(cache, "metrics")
        assert isinstance(cache.metrics, CacheMetrics)
        print("  [OK] StatsCache has metrics attribute of type CacheMetrics")

        # Has get_metrics method
        assert hasattr(cache, "get_metrics")
        metrics = cache.get_metrics()
        assert isinstance(metrics, dict)
        print(f"  [OK] get_metrics() returns dict: {metrics}")

        # Has reset_metrics method
        assert hasattr(cache, "reset_metrics")
        cache.reset_metrics()
        assert cache.metrics.hits == 0
        print("  [OK] reset_metrics() works")

        # Tracks misses
        cache.reset_metrics()
        cache.get_sync("nonexistent", "team_stats")
        assert cache.metrics.misses == 1
        print("  [OK] Cache miss increments misses counter")

        # Tracks hits
        cache._set_sync("test_key", {"data": 1}, "team_stats")
        cache.get_sync("test_key", "team_stats")
        assert cache.metrics.hits == 1
        print("  [OK] Cache hit increments hits counter")

        return True
    finally:
        cache.clear()


def verify_odds_api_metrics():
    """Verify OddsAPIClient has sportsbook metrics (import only, no API call)."""
    print("\nTesting OddsAPIClient metrics (import/structure only)...")

    import os

    # Set a dummy key to avoid ValueError
    os.environ["ODDS_API_KEY"] = "test_key_for_verification"

    from nba_betting_agent.agents.lines_agent.api.odds_api import (
        REQUIRED_SPORTSBOOKS,
        OddsAPIClient,
    )

    # Verify REQUIRED_SPORTSBOOKS constant
    assert REQUIRED_SPORTSBOOKS == {"draftkings", "fanduel", "betmgm", "bovada"}
    print(f"  [OK] REQUIRED_SPORTSBOOKS: {REQUIRED_SPORTSBOOKS}")

    # Verify client has sportsbook_metrics attribute
    client = OddsAPIClient(api_key="test_key")
    assert hasattr(client, "sportsbook_metrics")
    assert isinstance(client.sportsbook_metrics, dict)
    print("  [OK] OddsAPIClient has sportsbook_metrics dict")

    # Verify get_sportsbook_metrics method
    assert hasattr(client, "get_sportsbook_metrics")
    metrics = client.get_sportsbook_metrics()
    assert isinstance(metrics, dict)
    print("  [OK] get_sportsbook_metrics() returns dict")

    # Verify _update_sportsbook_metrics method exists
    assert hasattr(client, "_update_sportsbook_metrics")
    print("  [OK] _update_sportsbook_metrics() method exists")

    return True


def main():
    """Run all verifications."""
    print("=" * 60)
    print("Metrics Implementation Verification (06-03)")
    print("=" * 60)

    results = []

    results.append(("Imports", verify_imports()))
    results.append(("CacheMetrics", verify_cache_metrics()))
    results.append(("SportsbookMetrics", verify_sportsbook_metrics()))
    results.append(("StatsCache metrics", verify_stats_cache_metrics()))
    results.append(("OddsAPIClient metrics", verify_odds_api_metrics()))

    print("\n" + "=" * 60)
    print("VERIFICATION RESULTS")
    print("=" * 60)

    all_passed = True
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  {name}: {status}")
        if not passed:
            all_passed = False

    if all_passed:
        print("\nAll verifications passed!")
        print("\nTo run full test suite:")
        print("  pytest tests/test_metrics.py tests/test_stats_cache.py tests/test_odds_api.py -v")
        return 0
    else:
        print("\nSome verifications failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
