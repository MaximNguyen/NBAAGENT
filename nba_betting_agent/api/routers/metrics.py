"""System metrics endpoints - sportsbook coverage and cache performance."""

from fastapi import APIRouter

from nba_betting_agent.api.schemas import CacheMetricsResponse, SportsbookMetricsResponse
from nba_betting_agent.api.state import analysis_store

router = APIRouter(tags=["metrics"])


@router.get("/metrics/sportsbooks", response_model=list[SportsbookMetricsResponse])
async def get_sportsbook_metrics():
    """Get sportsbook coverage metrics from the latest analysis run."""
    latest = analysis_store.get_latest()
    if not latest or not latest.result:
        return []

    odds_data = latest.result.get("odds_data", [])

    # Aggregate sportsbook metrics from odds data
    book_stats: dict[str, dict] = {}
    total_games = len(odds_data)

    for game in odds_data:
        for bookmaker in game.get("bookmakers", []):
            key = bookmaker.get("key", bookmaker.get("title", "unknown"))
            if key not in book_stats:
                book_stats[key] = {
                    "name": key,
                    "games_with_odds": 0,
                    "markets": set(),
                    "last_seen": bookmaker.get("last_update"),
                }
            book_stats[key]["games_with_odds"] += 1
            for market in bookmaker.get("markets", []):
                book_stats[key]["markets"].add(market.get("key", "h2h"))

    results = []
    for key, stats in book_stats.items():
        availability = (stats["games_with_odds"] / total_games * 100) if total_games > 0 else 0
        results.append(
            SportsbookMetricsResponse(
                name=stats["name"],
                games_with_odds=stats["games_with_odds"],
                markets_available=sorted(stats["markets"]),
                last_seen=stats.get("last_seen"),
                availability_pct=round(availability, 1),
            )
        )

    return sorted(results, key=lambda x: x.availability_pct, reverse=True)


@router.get("/metrics/cache", response_model=CacheMetricsResponse)
async def get_cache_metrics():
    """Get cache performance metrics.

    Returns current cache hit/miss statistics.
    """
    # Try to get actual cache metrics from the odds repository
    try:
        from nba_betting_agent.db.repositories.odds import OddsRepository

        repo = OddsRepository()
        if hasattr(repo, "_disk_cache") and repo._disk_cache is not None:
            cache = repo._disk_cache
            stats = cache.stats(enable=True)
            hits = stats[0] if len(stats) > 0 else 0
            misses = stats[1] if len(stats) > 1 else 0
            repo.close_cache()
            return CacheMetricsResponse(
                hits=hits,
                misses=misses,
                stale_hits=0,
                hit_rate=round(hits / (hits + misses) * 100, 1) if (hits + misses) > 0 else 0,
                fresh_hit_rate=round(hits / (hits + misses) * 100, 1) if (hits + misses) > 0 else 0,
            )
    except Exception:
        pass

    # Fallback - no cache data available
    return CacheMetricsResponse(
        hits=0,
        misses=0,
        stale_hits=0,
        hit_rate=0,
        fresh_hit_rate=0,
    )
