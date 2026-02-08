"""Authentication endpoints for multi-user login, registration, and token management."""

from typing import Annotated

import jwt
from jwt.exceptions import InvalidTokenError
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from nba_betting_agent.api.auth import (
    create_access_token,
    create_email_verification_token,
    create_refresh_token,
    oauth2_scheme,
    revoke_token,
    verify_email_token,
    verify_google_id_token,
    verify_password,
)
from nba_betting_agent.api.config import Settings, get_settings
from nba_betting_agent.api.deps import get_db_session
from nba_betting_agent.api.middleware.rate_limit import limiter
from nba_betting_agent.api.schemas import (
    GoogleAuthRequest,
    LoginRequest,
    MessageResponse,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    VerifyEmailRequest,
)
from nba_betting_agent.api.services import email as email_service
from nba_betting_agent.api.services import user as user_service

router = APIRouter(tags=["auth"])


@router.post("/auth/register", response_model=MessageResponse)
@limiter.limit("3/hour")
async def register(
    request: Request,
    body: RegisterRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    """Register a new user with email and password."""
    existing = await user_service.get_by_email(db, body.email)
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    user = await user_service.create_user_email(db, body.email, body.password, body.display_name)
    await db.commit()

    # Send verification email
    token = create_email_verification_token(user.id, settings)
    await email_service.send_verification_email(user.email, token, settings)

    return MessageResponse(message="Registration successful. Check your email to verify your account.")


@router.post("/auth/verify-email", response_model=MessageResponse)
@limiter.limit("10/hour")
async def verify_email(
    request: Request,
    body: VerifyEmailRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    """Verify email address using token from verification email."""
    user_id = verify_email_token(body.token, settings)
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid or expired verification token")

    success = await user_service.verify_user_email(db, user_id)
    if not success:
        raise HTTPException(status_code=404, detail="User not found")

    await db.commit()
    return MessageResponse(message="Email verified successfully. You can now log in.")


@router.post("/auth/google", response_model=TokenResponse)
@limiter.limit("10/15minutes")
async def google_auth(
    request: Request,
    body: GoogleAuthRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    """Authenticate with Google ID token."""
    google_info = await verify_google_id_token(body.id_token, settings)
    if not google_info:
        raise HTTPException(status_code=401, detail="Invalid Google token")

    user = await user_service.create_or_get_google_user(
        db, google_info["sub"], google_info["email"], google_info.get("name")
    )
    await db.commit()

    role = getattr(user, "role", "user")
    access_token = create_access_token(user.id, settings, email=user.email, display_name=user.display_name, role=role)
    refresh_token = create_refresh_token(user.id, settings)

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/auth/login", response_model=TokenResponse)
@limiter.limit("5/15minutes")
async def login(
    request: Request,
    credentials: LoginRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    """Authenticate with email and password."""
    user = await user_service.get_by_email(db, credentials.email)

    if not user or not user.password_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified. Check your inbox or request a new verification email.",
        )

    role = getattr(user, "role", "user")
    access_token = create_access_token(user.id, settings, email=user.email, display_name=user.display_name, role=role)
    refresh_token = create_refresh_token(user.id, settings)

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/auth/resend-verification", response_model=MessageResponse)
@limiter.limit("2/hour")
async def resend_verification(
    request: Request,
    credentials: LoginRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    """Resend email verification link. Requires email+password to prevent abuse."""
    user = await user_service.get_by_email(db, credentials.email)

    if not user or not user.password_hash:
        # Don't reveal whether email exists
        return MessageResponse(message="If the account exists, a verification email has been sent.")

    if not verify_password(credentials.password, user.password_hash):
        return MessageResponse(message="If the account exists, a verification email has been sent.")

    if user.email_verified:
        return MessageResponse(message="Email is already verified. You can log in.")

    token = create_email_verification_token(user.id, settings)
    await email_service.send_verification_email(user.email, token, settings)

    return MessageResponse(message="If the account exists, a verification email has been sent.")


@router.post("/auth/refresh", response_model=TokenResponse)
@limiter.limit("30/minute")
async def refresh(
    request: Request,
    refresh_request: RefreshRequest,
    settings: Annotated[Settings, Depends(get_settings)],
):
    """Exchange a valid refresh token for a new access token."""
    try:
        payload = jwt.decode(
            refresh_request.refresh_token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )

        user_id: str | None = payload.get("sub")
        token_type: str | None = payload.get("type")

        if user_id is None or token_type != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        access_token = create_access_token(user_id, settings)

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_request.refresh_token,
        )

    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.post("/auth/logout")
@limiter.limit("30/minute")
async def logout(
    request: Request,
    token: Annotated[str, Depends(oauth2_scheme)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    """Logout by revoking the current access token."""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )

        jti = payload.get("jti")
        exp = payload.get("exp")

        if not jti or not exp:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing jti or exp claim",
                headers={"WWW-Authenticate": "Bearer"},
            )

        revoke_token(jti, exp)

        return {"message": "Successfully logged out"}

    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
