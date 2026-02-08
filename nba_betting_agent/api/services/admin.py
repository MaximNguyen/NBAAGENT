"""Admin service: user management, system stats, and audit log operations."""

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from nba_betting_agent.db.models import AuditLogModel, UserModel


async def list_users(
    session: AsyncSession, skip: int = 0, limit: int = 50
) -> list[UserModel]:
    result = await session.execute(
        select(UserModel).order_by(UserModel.created_at.desc()).offset(skip).limit(limit)
    )
    return list(result.scalars().all())


async def count_users(session: AsyncSession) -> int:
    result = await session.execute(select(func.count(UserModel.id)))
    return result.scalar_one()


async def get_user_by_id(session: AsyncSession, user_id: str) -> UserModel | None:
    result = await session.execute(select(UserModel).where(UserModel.id == user_id))
    return result.scalar_one_or_none()


async def update_user_role(
    session: AsyncSession, user_id: str, new_role: str
) -> UserModel | None:
    result = await session.execute(select(UserModel).where(UserModel.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        return None
    user.role = new_role
    user.updated_at = datetime.now(timezone.utc)
    await session.flush()
    return user


async def delete_user(session: AsyncSession, user_id: str) -> bool:
    result = await session.execute(select(UserModel).where(UserModel.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        return False
    await session.delete(user)
    await session.flush()
    return True


async def get_system_stats(session: AsyncSession) -> dict:
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())

    total = await count_users(session)

    verified_result = await session.execute(
        select(func.count(UserModel.id)).where(UserModel.email_verified == True)  # noqa: E712
    )
    verified = verified_result.scalar_one()

    google_result = await session.execute(
        select(func.count(UserModel.id)).where(UserModel.google_id.is_not(None))
    )
    google_users = google_result.scalar_one()

    today_result = await session.execute(
        select(func.count(UserModel.id)).where(UserModel.created_at >= today_start)
    )
    signups_today = today_result.scalar_one()

    week_result = await session.execute(
        select(func.count(UserModel.id)).where(UserModel.created_at >= week_start)
    )
    signups_this_week = week_result.scalar_one()

    return {
        "total_users": total,
        "verified_users": verified,
        "google_users": google_users,
        "signups_today": signups_today,
        "signups_this_week": signups_this_week,
    }


async def create_audit_entry(
    session: AsyncSession,
    admin_id: str,
    action: str,
    target_id: str | None = None,
    details: dict | None = None,
) -> AuditLogModel:
    entry = AuditLogModel(
        timestamp=datetime.now(timezone.utc),
        admin_id=admin_id,
        action=action,
        target_id=target_id,
        details=json.dumps(details) if details else None,
    )
    session.add(entry)
    await session.flush()
    return entry


async def list_audit_log(
    session: AsyncSession, skip: int = 0, limit: int = 50
) -> list[AuditLogModel]:
    result = await session.execute(
        select(AuditLogModel)
        .order_by(AuditLogModel.timestamp.desc())
        .offset(skip)
        .limit(limit)
    )
    return list(result.scalars().all())


async def count_audit_log(session: AsyncSession) -> int:
    result = await session.execute(select(func.count(AuditLogModel.id)))
    return result.scalar_one()
