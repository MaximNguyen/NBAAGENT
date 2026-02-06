"""Authentication for the dashboard API.

Simple JWT-based auth with a single hardcoded user.
"""

import hashlib
import hmac
import json
import os
import time
from base64 import urlsafe_b64decode, urlsafe_b64encode
from typing import Optional

from fastapi import Depends, HTTPException, WebSocket, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

# --- Credentials ---
_USERNAME = "admin"
_PASSWORD_HASH = hashlib.sha256(b"Maxim03").hexdigest()

# --- JWT-like token (HMAC-SHA256, no external dep) ---
_SECRET = os.getenv("DASHBOARD_SECRET", "nba-ev-dashboard-secret-k3y-2026")
_TOKEN_EXPIRY = 60 * 60 * 24 * 7  # 7 days

_bearer_scheme = HTTPBearer()


def _b64e(data: bytes) -> str:
    return urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64d(s: str) -> bytes:
    padding = 4 - len(s) % 4
    return urlsafe_b64decode(s + "=" * padding)


def _sign(payload: str) -> str:
    return hmac.new(_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()


def verify_credentials(username: str, password: str) -> bool:
    """Check username/password against stored credentials."""
    if username != _USERNAME:
        return False
    return hmac.compare_digest(
        hashlib.sha256(password.encode()).hexdigest(),
        _PASSWORD_HASH,
    )


def create_token(username: str) -> str:
    """Create a signed JWT-like token."""
    payload = json.dumps({
        "sub": username,
        "exp": int(time.time()) + _TOKEN_EXPIRY,
    })
    encoded = _b64e(payload.encode())
    signature = _sign(encoded)
    return f"{encoded}.{signature}"


def decode_token(token: str) -> Optional[str]:
    """Decode and verify a token. Returns username or None."""
    try:
        parts = token.split(".")
        if len(parts) != 2:
            return None

        encoded, signature = parts

        # Verify signature
        if not hmac.compare_digest(_sign(encoded), signature):
            return None

        # Decode payload
        payload = json.loads(_b64d(encoded))

        # Check expiry
        if payload.get("exp", 0) < time.time():
            return None

        return payload.get("sub")
    except Exception:
        return None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> str:
    """FastAPI dependency: extract and validate the Bearer token."""
    username = decode_token(credentials.credentials)
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return username


def verify_ws_token(token: str) -> Optional[str]:
    """Verify a token from WebSocket query param. Returns username or None."""
    return decode_token(token)
