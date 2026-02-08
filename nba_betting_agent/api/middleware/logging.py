"""Request logging middleware with sensitive data redaction."""

import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from structlog.contextvars import bind_contextvars, clear_contextvars

log = structlog.get_logger()


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log all HTTP requests with structured metadata.

    Implements TRNS-04 and TRNS-05:
    - Logs method, path, status_code, duration_ms, client_ip, request_id
    - Skips health check endpoints to reduce noise
    - Never logs Authorization headers or API keys (not bound to contextvars)
    - Uses structlog contextvars for request-scoped context
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        """Log request completion with metadata."""
        # Clear any prior request context
        clear_contextvars()

        # Generate request ID for tracing
        request_id = str(uuid.uuid4())

        # Extract client IP from proxy headers or direct connection
        # Railway proxy uses X-Envoy-External-Address
        client_ip = request.headers.get("X-Envoy-External-Address")
        if not client_ip and request.client:
            client_ip = request.client.host

        # Bind request metadata to contextvars (available in all logs)
        bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            client_ip=client_ip,
        )

        # Skip logging for health check endpoints
        if request.url.path in ["/api/health", "/healthcheck"]:
            return await call_next(request)

        # Measure request duration
        start_time = time.time()
        response = await call_next(request)
        duration_ms = int((time.time() - start_time) * 1000)

        # Log request completion
        log.info(
            "request_completed",
            status_code=response.status_code,
            duration_ms=duration_ms,
        )

        return response
