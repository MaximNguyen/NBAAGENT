"""Cache configuration toggle from environment variables.

Provides runtime control over odds caching behavior via environment variables.
Cache can be disabled to troubleshoot issues or force fresh API calls.
"""

import os
from functools import lru_cache


@lru_cache(maxsize=1)
def get_cache_config() -> dict:
    """Load cache configuration from environment.

    Environment variables:
        ODDS_CACHE_ENABLED: "true"/"1"/"yes"/"on" = enabled (default: true)
        ODDS_CACHE_TTL: seconds (default: 3600 = 1 hour)
        ODDS_CACHE_DIR: cache directory (default: .cache/odds_api)

    Returns:
        Dictionary with enabled, ttl, and cache_dir keys.

    Examples:
        >>> config = get_cache_config()
        >>> config["enabled"]  # True by default
        True
        >>> config["ttl"]  # 3600 seconds default
        3600

        # Disable cache
        >>> os.environ["ODDS_CACHE_ENABLED"] = "false"
        >>> get_cache_config.cache_clear()
        >>> is_cache_enabled()
        False
    """
    # Parse ODDS_CACHE_ENABLED (default: enabled)
    enabled_str = os.getenv("ODDS_CACHE_ENABLED", "true").lower()
    # Empty string counts as default (enabled)
    if enabled_str == "":
        enabled_str = "true"
    enabled = enabled_str in ("true", "1", "yes", "on")

    # Parse ODDS_CACHE_TTL (default: 3600 seconds = 1 hour)
    ttl_str = os.getenv("ODDS_CACHE_TTL", "3600")
    try:
        ttl = int(ttl_str)
    except ValueError:
        ttl = 3600  # Fallback to default on invalid value

    # Parse ODDS_CACHE_DIR (default: .cache/odds_api)
    cache_dir = os.getenv("ODDS_CACHE_DIR", ".cache/odds_api")

    return {
        "enabled": enabled,
        "ttl": ttl,
        "cache_dir": cache_dir,
    }


def is_cache_enabled() -> bool:
    """Check if odds cache is enabled.

    Convenience function that reads from get_cache_config().

    Returns:
        True if cache is enabled, False otherwise.

    Examples:
        >>> is_cache_enabled()
        True

        # Disable via environment
        >>> os.environ["ODDS_CACHE_ENABLED"] = "false"
        >>> get_cache_config.cache_clear()
        >>> is_cache_enabled()
        False
    """
    return get_cache_config()["enabled"]
