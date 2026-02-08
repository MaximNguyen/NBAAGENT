"""Authentication for the dashboard API.

PyJWT-based authentication with bcrypt password hashing.
Supports access tokens (short-lived), refresh tokens (long-lived),
email verification tokens, and Google OAuth ID token verification.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Annotated
import time
import uuid

import httpx
import jwt
from jwt.exceptions import InvalidTokenError
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext

from nba_betting_agent.api.config import Settings, get_settings

logger = logging.getLogger(__name__)

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


def create_access_token(
    user_id: str,
    settings: Settings,
    email: str | None = None,
    display_name: str | None = None,
    role: str | None = None,
) -> str:
    """Create a short-lived access token for API authentication.

    Args:
        user_id: User ID (UUID) to encode as the subject
        settings: Application settings containing JWT secret and configuration
        email: Optional email to include as a claim
        display_name: Optional display name to include as a claim
        role: Optional user role to include as a claim

    Returns:
        Encoded JWT access token string
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.access_token_expire_minutes)

    payload: dict = {
        "sub": user_id,
        "exp": expire,
        "iat": now,
        "type": "access",
        "jti": uuid.uuid4().hex,
    }
    if email:
        payload["email"] = email
    if display_name:
        payload["display_name"] = display_name
    if role:
        payload["role"] = role

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def create_refresh_token(user_id: str, settings: Settings) -> str:
    """Create a long-lived refresh token for obtaining new access tokens.

    Args:
        user_id: User ID (UUID) to encode as the subject
        settings: Application settings containing JWT secret and configuration

    Returns:
        Encoded JWT refresh token string
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=settings.refresh_token_expire_days)

    payload = {
        "sub": user_id,
        "exp": expire,
        "iat": now,
        "type": "refresh",
        "jti": uuid.uuid4().hex,
    }

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def create_email_verification_token(user_id: str, settings: Settings) -> str:
    """Create a token for email verification.

    Args:
        user_id: User ID to encode in the token
        settings: Application settings

    Returns:
        Encoded JWT token string
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(hours=settings.email_verification_token_expire_hours)

    payload = {
        "sub": user_id,
        "exp": expire,
        "iat": now,
        "type": "email_verification",
    }

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def verify_email_token(token: str, settings: Settings) -> str | None:
    """Verify an email verification token and return the user_id.

    Returns None if token is invalid or expired.
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )

        user_id: str | None = payload.get("sub")
        token_type: str | None = payload.get("type")

        if user_id is None or token_type != "email_verification":
            return None

        return user_id
    except InvalidTokenError:
        return None


async def verify_google_id_token(id_token: str, settings: Settings) -> dict | None:
    """Verify a Google ID token using Google's tokeninfo endpoint.

    Returns dict with {sub, email, name, email_verified} or None on failure.
    """
    if not settings.google_client_id:
        logger.error("GOOGLE_CLIENT_ID not configured")
        return None

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://oauth2.googleapis.com/tokeninfo",
                params={"id_token": id_token},
                timeout=10.0,
            )

            if resp.status_code != 200:
                logger.warning("Google token verification failed: %d", resp.status_code)
                return None

            data = resp.json()

            # Verify audience matches our client ID
            if data.get("aud") != settings.google_client_id:
                logger.warning("Google token aud mismatch")
                return None

            return {
                "sub": data["sub"],
                "email": data["email"],
                "name": data.get("name", ""),
                "email_verified": data.get("email_verified", "false") == "true",
            }
    except httpx.HTTPError as e:
        logger.error("Google token verification error: %s", e)
        return None


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

    Returns:
        User ID (sub claim) from token

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

        user_id: str | None = payload.get("sub")
        token_type: str | None = payload.get("type")
        jti = payload.get("jti")

        if user_id is None or token_type != "access":
            raise credentials_exception

        if jti and is_token_revoked(jti):
            raise credentials_exception

        return user_id

    except InvalidTokenError:
        raise credentials_exception


async def get_current_admin_user(
    user_id: Annotated[str, Depends(get_current_user)],
) -> str:
    """FastAPI dependency: Verify the current user has admin role.

    Queries the database for the user's role. Returns 403 if not admin.

    Returns:
        User ID if user is admin

    Raises:
        HTTPException: 403 if user is not admin, 401 if user not found
    """
    from sqlalchemy import select

    from nba_betting_agent.db.models import UserModel
    from nba_betting_agent.db.session import AsyncSessionFactory

    async with AsyncSessionFactory() as session:
        result = await session.execute(
            select(UserModel).where(UserModel.id == user_id)
        )
        user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    return user_id


def verify_ws_token(token: str) -> str | None:
    """Verify a token from WebSocket query parameter.

    Returns user_id or None on any error.
    """
    try:
        settings = get_settings()

        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm]
        )

        user_id: str | None = payload.get("sub")
        token_type: str | None = payload.get("type")
        jti = payload.get("jti")

        if user_id is None or token_type != "access":
            return None

        if jti and is_token_revoked(jti):
            return None

        return user_id

    except Exception:
        return None
