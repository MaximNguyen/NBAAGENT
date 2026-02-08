"""Authentication for the dashboard API.

PyJWT-based authentication with bcrypt password hashing.
Supports access tokens (short-lived) and refresh tokens (long-lived).
"""

from datetime import datetime, timedelta, timezone
from typing import Annotated
import time
import uuid

import jwt
from jwt.exceptions import InvalidTokenError
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext

from nba_betting_agent.api.config import Settings, get_settings

# OAuth2 scheme for Bearer token extraction
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# Password hashing context with bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)

# Token blacklist for logout support (RATE-05)
# Format: {jti: expiry_timestamp} — cleaned up on each revoke call
_revoked_tokens: dict[str, float] = {}


def _cleanup_expired_tokens():
    """Remove expired tokens from blacklist to prevent unbounded growth."""
    global _revoked_tokens
    current_time = time.time()
    _revoked_tokens = {jti: exp for jti, exp in _revoked_tokens.items() if exp > current_time}


def revoke_token(jti: str, exp: int):
    """Add a token to the blacklist.

    Args:
        jti: Token identifier (jti claim)
        exp: Token expiry timestamp (exp claim)
    """
    _cleanup_expired_tokens()
    _revoked_tokens[jti] = float(exp)


def is_token_revoked(jti: str) -> bool:
    """Check if a token has been revoked.

    Args:
        jti: Token identifier (jti claim)

    Returns:
        True if token is revoked and not yet expired, False otherwise
    """
    if jti not in _revoked_tokens:
        return False

    # Check if token expired naturally
    if _revoked_tokens[jti] < time.time():
        del _revoked_tokens[jti]
        return False

    return True


def create_access_token(username: str, settings: Settings) -> str:
    """Create a short-lived access token for API authentication.

    Args:
        username: The username to encode in the token
        settings: Application settings containing JWT secret and configuration

    Returns:
        Encoded JWT access token string
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.access_token_expire_minutes)

    payload = {
        "sub": username,
        "exp": expire,
        "iat": now,
        "type": "access",
        "jti": uuid.uuid4().hex
    }

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm
    )


def create_refresh_token(username: str, settings: Settings) -> str:
    """Create a long-lived refresh token for obtaining new access tokens.

    Args:
        username: The username to encode in the token
        settings: Application settings containing JWT secret and configuration

    Returns:
        Encoded JWT refresh token string
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=settings.refresh_token_expire_days)

    payload = {
        "sub": username,
        "exp": expire,
        "iat": now,
        "type": "refresh",
        "jti": uuid.uuid4().hex
    }

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm
    )


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a bcrypt hash.

    Args:
        plain_password: The plain text password to verify
        hashed_password: The bcrypt hash to compare against

    Returns:
        True if password matches, False otherwise
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Generate a bcrypt hash for a password.

    Utility function for generating password hashes.

    Args:
        password: The plain text password to hash

    Returns:
        Bcrypt hash string
    """
    return pwd_context.hash(password)


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    settings: Annotated[Settings, Depends(get_settings)]
) -> str:
    """FastAPI dependency: Extract and validate access token from Authorization header.

    Args:
        token: Bearer token extracted from Authorization header
        settings: Application settings for JWT verification

    Returns:
        Username from token

    Raises:
        HTTPException: 401 if token is invalid, expired, or not an access token
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm]
        )

        username: str | None = payload.get("sub")
        token_type: str | None = payload.get("type")
        jti = payload.get("jti")

        if username is None or token_type != "access":
            raise credentials_exception

        if jti and is_token_revoked(jti):
            raise credentials_exception

        return username

    except InvalidTokenError:
        raise credentials_exception


def verify_ws_token(token: str) -> str | None:
    """Verify a token from WebSocket query parameter.

    Used for WebSocket authentication where standard dependency injection
    is not available. Returns username or None on any error.

    Args:
        token: JWT token string

    Returns:
        Username if token is valid and is an access token, None otherwise
    """
    try:
        settings = get_settings()

        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm]
        )

        username: str | None = payload.get("sub")
        token_type: str | None = payload.get("type")
        jti = payload.get("jti")

        if username is None or token_type != "access":
            return None

        if jti and is_token_revoked(jti):
            return None

        return username

    except Exception:
        return None
