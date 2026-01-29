"""Structured logging configuration using structlog.

This module configures structlog for production-grade observability:
- JSON output in production mode (filterable, parseable)
- Colored console output in development mode (human-readable)
- Correlation IDs for tracing related operations
- Agent timing metrics (duration_ms field)

Usage:
    from nba_betting_agent.monitoring import configure_logging, get_logger

    # Configure once at app startup
    configure_logging("production")  # or "development"

    # Get logger for module
    log = get_logger()

    # Log structured events
    log.info("odds_fetched", game_count=5, source="odds_api")
    log.warning("low_api_credits", remaining=25)
    log.error("api_request_failed", error=str(e), retry_count=3)
"""

import logging
import sys
from typing import Any

import structlog


def configure_logging(mode: str = "development") -> None:
    """Configure structlog for the application.

    Args:
        mode: Either "production" (JSON output) or "development" (colored console)

    Sets up structlog with appropriate processors and renderers based on mode.
    In production: JSON output for machine parsing
    In development: Colored console output for human readability
    """
    # Determine processors based on mode
    if mode == "production":
        # Production: JSON output for log aggregation/filtering
        processors = [
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Development: Colored console output
        processors = [
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.dev.ConsoleRenderer(colors=True),
        ]

    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure stdlib logging to work with structlog
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.INFO,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance.

    Args:
        name: Logger name (defaults to caller's module name)

    Returns:
        Configured structlog logger

    Usage:
        log = get_logger()
        log.info("event_name", key1="value1", key2=123)
    """
    return structlog.get_logger(name)


def bind_correlation_id(correlation_id: str) -> None:
    """Bind a correlation ID to the current context.

    All subsequent log events in this context will include the correlation_id field.
    Useful for tracing related operations across multiple agents/functions.

    Args:
        correlation_id: Unique identifier for this operation (e.g., request ID)

    Usage:
        bind_correlation_id("req_abc123")
        log.info("processing_started")  # Will include correlation_id="req_abc123"
    """
    structlog.contextvars.bind_contextvars(correlation_id=correlation_id)


def unbind_correlation_id() -> None:
    """Remove correlation ID from context.

    Useful when processing completes to avoid leaking IDs to subsequent operations.
    """
    structlog.contextvars.unbind_contextvars("correlation_id")
