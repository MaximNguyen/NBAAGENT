"""Stats Agent - Gathers NBA statistics and injury data with caching.

This module provides:
- StatsCache class with async support and stale-while-revalidate patterns
- Pydantic models for team stats and injury reports
- NBA data fetching with retry and circuit breaker patterns

Main entry points:
- stats_agent_impl: Sync wrapper for LangGraph node execution
- collect_stats: Async function for direct use
"""

from nba_betting_agent.agents.stats_agent.agent import (
    stats_agent_impl,
    collect_stats,
)
from nba_betting_agent.agents.stats_agent.cache import CacheEntry, StatsCache
from nba_betting_agent.agents.stats_agent.models import (
    HomeAwayRecord,
    HomeAwayStats,
    InjuryReport,
    Last10Stats,
    TeamAdvancedMetrics,
    TeamBasicStats,
    TeamRecord,
    TeamStats,
    TeamStatsCollection,
)

__all__ = [
    # Agent entry points
    "stats_agent_impl",
    "collect_stats",
    # Cache
    "StatsCache",
    "CacheEntry",
    # Models
    "TeamRecord",
    "TeamBasicStats",
    "TeamAdvancedMetrics",
    "HomeAwayRecord",
    "HomeAwayStats",
    "Last10Stats",
    "TeamStats",
    "InjuryReport",
    "TeamStatsCollection",
]
