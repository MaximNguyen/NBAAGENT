"""Rate limiting middleware using SlowAPI."""

from fastapi import Request
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

__all__ = ["limiter", "get_rate_limit_key", "RateLimitExceeded", "_rate_limit_exceeded_handler"]


def get_rate_limit_key(request: Request) -> str:
    """Extract rate limit key from request (IP-based limiting).

    Args:
        request: FastAPI request object

    Returns:
        Client IP address as rate limit key
    """
    return get_remote_address(request)


# Create module-level limiter instance
limiter = Limiter(key_func=get_rate_limit_key)
