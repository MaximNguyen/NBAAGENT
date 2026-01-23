"""Stats Agent - Gathers NBA statistics and injury data with caching.

This module provides:
- StatsCache class with async support and stale-while-revalidate patterns
- Pydantic models for team stats and injury reports
- NBA data fetching with retry and circuit breaker patterns
"""
