"""Admin endpoints — user management, system stats, audit log, analysis trigger."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from nba_betting_agent.api.auth import get_current_admin_user
from nba_betting_agent.api.deps import get_db_session
from nba_betting_agent.api.middleware.rate_limit import limiter
from nba_betting_agent.api.schemas import (
    AuditLogEntry,
    AuditLogResponse,
    AnalysisRunResponse,
    MessageResponse,
    SystemStatsResponse,
    UpdateUserRoleRequest,
    UserAdminResponse,
    UserListResponse,
)
from nba_betting_agent.api.services import admin as admin_service

router = APIRouter(prefix="/admin", tags=["admin"])

_executor = ThreadPoolExecutor(max_workers=1)


def _user_to_response(user) -> UserAdminResponse:
    return UserAdminResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        email_verified=user.email_verified,
        has_google=user.google_id is not None,
        created_at=user.created_at.isoformat() if user.created_at else "",
    )


@router.get("/users", response_model=UserListResponse)
@limiter.limit("30/minute")
async def list_users(
    request: Request,
    admin_id: Annotated[str, Depends(get_current_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
):
    """List all users (paginated)."""
    users = await admin_service.list_users(db, skip=skip, limit=limit)
    total = await admin_service.count_users(db)
    return UserListResponse(
        users=[_user_to_response(u) for u in users],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.patch("/users/{user_id}/role", response_model=UserAdminResponse)
@limiter.limit("30/minute")
async def update_user_role(
    request: Request,
    admin_id: Annotated[str, Depends(get_current_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    body: UpdateUserRoleRequest,
    user_id: str = Path(..., max_length=36),
):
    """Change a user's role."""
    target = await admin_service.get_user_by_id(db, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    old_role = target.role
    updated = await admin_service.update_user_role(db, user_id, body.role)

    await admin_service.create_audit_entry(
        db,
        admin_id=admin_id,
        action="user.role_changed",
        target_id=user_id,
        details={"old_role": old_role, "new_role": body.role},
    )
    await db.commit()

    return _user_to_response(updated)


@router.delete("/users/{user_id}", response_model=MessageResponse)
@limiter.limit("30/minute")
async def delete_user(
    request: Request,
    admin_id: Annotated[str, Depends(get_current_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    user_id: str = Path(..., max_length=36),
):
    """Delete a user. Admin cannot delete themselves."""
    if user_id == admin_id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")

    target = await admin_service.get_user_by_id(db, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    target_email = target.email
    deleted = await admin_service.delete_user(db, user_id)

    await admin_service.create_audit_entry(
        db,
        admin_id=admin_id,
        action="user.deleted",
        target_id=user_id,
        details={"email": target_email},
    )
    await db.commit()

    return MessageResponse(message=f"User {target_email} deleted")


@router.get("/stats", response_model=SystemStatsResponse)
@limiter.limit("30/minute")
async def get_stats(
    request: Request,
    admin_id: Annotated[str, Depends(get_current_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    """Get system statistics."""
    stats = await admin_service.get_system_stats(db)
    return SystemStatsResponse(**stats)


@router.get("/audit-log", response_model=AuditLogResponse)
@limiter.limit("30/minute")
async def get_audit_log(
    request: Request,
    admin_id: Annotated[str, Depends(get_current_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
):
    """Get admin audit log (paginated)."""
    entries = await admin_service.list_audit_log(db, skip=skip, limit=limit)
    total = await admin_service.count_audit_log(db)
    return AuditLogResponse(
        entries=[
            AuditLogEntry(
                id=e.id,
                timestamp=e.timestamp.isoformat() if e.timestamp else "",
                admin_id=e.admin_id,
                action=e.action,
                target_id=e.target_id,
                details=e.details,
            )
            for e in entries
        ],
        total=total,
    )


@router.post("/analysis/run", response_model=AnalysisRunResponse)
@limiter.limit("30/minute")
async def trigger_analysis(
    request: Request,
    admin_id: Annotated[str, Depends(get_current_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    """Trigger an analysis run from the admin panel."""
    from nba_betting_agent.api.routers.analysis import _run_analysis_sync
    from nba_betting_agent.api.state import analysis_store

    run = analysis_store.create_run("admin triggered analysis")

    loop = asyncio.get_event_loop()
    loop.run_in_executor(
        _executor,
        _run_analysis_sync,
        run.run_id,
        "find best bets tonight",
        0.02,
        None,
        10,
    )

    await admin_service.create_audit_entry(
        db,
        admin_id=admin_id,
        action="analysis.triggered",
        details={"run_id": run.run_id},
    )
    await db.commit()

    return AnalysisRunResponse(
        run_id=run.run_id,
        status="pending",
        message="Analysis triggered by admin.",
    )
