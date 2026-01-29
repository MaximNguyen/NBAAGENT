"""Monitoring module for structured logging and observability.

This module provides production-grade logging capabilities using structlog:
- Structured JSON logging for production
- Human-readable console output for development
- Correlation IDs for request tracing
- Agent timing metrics
"""

from nba_betting_agent.monitoring.logging import (
    configure_logging,
    get_logger,
    bind_correlation_id,
)

__all__ = [
    "configure_logging",
    "get_logger",
    "bind_correlation_id",
]
