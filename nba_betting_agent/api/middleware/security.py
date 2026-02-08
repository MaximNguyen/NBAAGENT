"""Security headers middleware for API transport protection."""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all HTTP responses.

    Implements TRNS-01:
    - HSTS (Strict-Transport-Security)
    - X-Frame-Options: DENY
    - X-Content-Type-Options: nosniff
    - Content-Security-Policy with self and cdn.jsdelivr.net for Swagger UI
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        """Add security headers to response."""
        response = await call_next(request)

        # HSTS: Force HTTPS for 1 year, include subdomains
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )

        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"

        # Prevent MIME sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Content Security Policy
        # - default-src 'self': Only load resources from same origin
        # - script-src/style-src: Allow self + cdn.jsdelivr.net (Swagger) + accounts.google.com (OAuth)
        # - frame-src: Allow Google OAuth popup/redirect
        # - connect-src: Allow Google token verification
        # - frame-ancestors 'none': Prevent framing (redundant with X-Frame-Options)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' https://cdn.jsdelivr.net https://accounts.google.com; "
            "style-src 'self' https://cdn.jsdelivr.net https://accounts.google.com; "
            "frame-src https://accounts.google.com; "
            "connect-src 'self' https://accounts.google.com https://oauth2.googleapis.com; "
            "frame-ancestors 'none'"
        )

        return response
