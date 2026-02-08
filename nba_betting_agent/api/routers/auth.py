"""Authentication endpoints for login and token refresh."""

from typing import Annotated

import jwt
from jwt.exceptions import InvalidTokenError
from fastapi import APIRouter, Depends, HTTPException, Request, status

from nba_betting_agent.api.auth import (
    create_access_token,
    create_refresh_token,
    verify_password,
)
from nba_betting_agent.api.config import Settings, get_settings
from nba_betting_agent.api.middleware.rate_limit import limiter
from nba_betting_agent.api.schemas import LoginRequest, RefreshRequest, TokenResponse

router = APIRouter(tags=["auth"])


@router.post("/auth/login", response_model=TokenResponse)
@limiter.limit("5/15minutes")
async def login(
    request: Request,
    credentials: LoginRequest,
    settings: Annotated[Settings, Depends(get_settings)]
):
    """Authenticate with username and password, receive access and refresh tokens.

    Args:
        request: FastAPI request object (required for rate limiting)
        credentials: Login credentials (username and password)
        settings: Application settings with password hash

    Returns:
        TokenResponse with access_token, refresh_token, and token_type

    Raises:
        HTTPException: 401 if credentials are invalid
    """
    # Verify password against stored bcrypt hash
    if not verify_password(credentials.password, settings.dashboard_password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Single-user system: username is always "dashboard"
    username = "dashboard"

    # Create both access and refresh tokens
    access_token = create_access_token(username, settings)
    refresh_token = create_refresh_token(username, settings)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer"
    )


@router.post("/auth/refresh", response_model=TokenResponse)
async def refresh(
    request: RefreshRequest,
    settings: Annotated[Settings, Depends(get_settings)]
):
    """Exchange a valid refresh token for a new access token.

    Args:
        request: Refresh token request
        settings: Application settings for JWT verification

    Returns:
        TokenResponse with new access_token and same refresh_token

    Raises:
        HTTPException: 401 if refresh token is invalid or expired
    """
    try:
        # Decode and verify refresh token
        payload = jwt.decode(
            request.refresh_token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm]
        )

        username: str | None = payload.get("sub")
        token_type: str | None = payload.get("type")

        # Validate token type and username
        if username is None or token_type != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Create new access token
        access_token = create_access_token(username, settings)

        # Return new access token with same refresh token
        return TokenResponse(
            access_token=access_token,
            refresh_token=request.refresh_token,
            token_type="bearer"
        )

    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )
