"""Production metrics dataclasses for observability.

Provides dataclasses for tracking:
- Sportsbook availability metrics (per-book coverage)
- Cache performance metrics (hit/miss/stale rates)

Usage:
    from nba_betting_agent.monitoring.metrics import SportsbookMetrics, CacheMetrics

    # Track sportsbook coverage
    sm = SportsbookMetrics(name="draftkings", games_with_odds=10, availability_pct=100.0)

    # Track cache performance
    cm = CacheMetrics(hits=80, misses=15, stale_hits=5)
    print(f"Hit rate: {cm.hit_rate}%")  # 85.0%
"""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class SportsbookMetrics:
    """Metrics for a single sportsbook.

    Tracks availability and market coverage for monitoring
    which sportsbooks are providing data.

    Attributes:
        name: Sportsbook identifier (e.g., "draftkings", "fanduel")
        games_with_odds: Number of games with odds from this book
        markets_available: List of market types provided (e.g., ["h2h", "spreads"])
        last_seen: Timestamp of last odds update from this book
        availability_pct: Percentage of total games with odds from this book
    """

    name: str
    games_with_odds: int = 0
    markets_available: list[str] = field(default_factory=list)
    last_seen: datetime | None = None
    availability_pct: float = 0.0


@dataclass
class CacheMetrics:
    """Track cache performance for monitoring.

    Provides hit/miss/stale tracking with computed hit rates.
    Use for monitoring cache effectiveness and detecting degradation.

    Attributes:
        hits: Number of fresh cache hits
        misses: Number of cache misses
        stale_hits: Number of stale cache hits (data used but needs refresh)
    """

    hits: int = 0
    misses: int = 0
    stale_hits: int = 0

    @property
    def hit_rate(self) -> float:
        """Calculate overall cache hit rate as percentage.

        Includes both fresh and stale hits as cache "hits".
        Returns 0.0 if no cache operations have occurred.
        """
        total = self.hits + self.misses + self.stale_hits
        return round((self.hits + self.stale_hits) / total * 100, 1) if total > 0 else 0.0

    @property
    def fresh_hit_rate(self) -> float:
        """Calculate fresh (non-stale) hit rate as percentage.

        Only counts fresh hits, not stale ones.
        Returns 0.0 if no cache operations have occurred.
        """
        total = self.hits + self.misses + self.stale_hits
        return round(self.hits / total * 100, 1) if total > 0 else 0.0

    def to_dict(self) -> dict:
        """Export metrics as dictionary for API responses.

        Returns:
            Dictionary with all metrics including computed rates.
        """
        return {
            "hits": self.hits,
            "misses": self.misses,
            "stale_hits": self.stale_hits,
            "hit_rate": self.hit_rate,
            "fresh_hit_rate": self.fresh_hit_rate,
        }
