"""User CRUD operations."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nba_betting_agent.api.auth import get_password_hash
from nba_betting_agent.db.models import UserModel


async def get_by_email(session: AsyncSession, email: str) -> UserModel | None:
    result = await session.execute(select(UserModel).where(UserModel.email == email))
    return result.scalar_one_or_none()


async def get_by_google_id(session: AsyncSession, google_id: str) -> UserModel | None:
    result = await session.execute(select(UserModel).where(UserModel.google_id == google_id))
    return result.scalar_one_or_none()


async def create_user_email(
    session: AsyncSession, email: str, password: str, display_name: str | None = None
) -> UserModel:
    now = datetime.now(timezone.utc)
    user = UserModel(
        id=uuid.uuid4().hex,
        email=email.lower().strip(),
        password_hash=get_password_hash(password),
        email_verified=False,
        display_name=display_name or email.split("@")[0],
        created_at=now,
        updated_at=now,
    )
    session.add(user)
    await session.flush()
    return user


async def create_or_get_google_user(
    session: AsyncSession, google_id: str, email: str, display_name: str | None = None
) -> UserModel:
    # Check by google_id first
    user = await get_by_google_id(session, google_id)
    if user:
        return user

    # Check if email exists (link Google to existing account)
    user = await get_by_email(session, email.lower().strip())
    if user:
        user.google_id = google_id
        user.email_verified = True
        if display_name and not user.display_name:
            user.display_name = display_name
        user.updated_at = datetime.now(timezone.utc)
        await session.flush()
        return user

    # Create new user
    now = datetime.now(timezone.utc)
    user = UserModel(
        id=uuid.uuid4().hex,
        email=email.lower().strip(),
        google_id=google_id,
        email_verified=True,
        display_name=display_name or email.split("@")[0],
        created_at=now,
        updated_at=now,
    )
    session.add(user)
    await session.flush()
    return user


async def verify_user_email(session: AsyncSession, user_id: str) -> bool:
    result = await session.execute(select(UserModel).where(UserModel.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        return False
    user.email_verified = True
    user.updated_at = datetime.now(timezone.utc)
    await session.flush()
    return True
