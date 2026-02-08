"""Tests for admin endpoints — authorization, user management, audit log."""

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest
from fastapi.testclient import TestClient
from passlib.context import CryptContext


# --- Fixtures ---

@pytest.fixture
def test_settings(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-that-is-at-least-32-characters-long")
    monkeypatch.setenv("DASHBOARD_PASSWORD_HASH", "")
    monkeypatch.setenv("ENVIRONMENT", "test")

    from nba_betting_agent.api.config import get_settings
    get_settings.cache_clear()
    yield get_settings()
    get_settings.cache_clear()


@pytest.fixture
def admin_user():
    user = MagicMock()
    user.id = "admin-user-id-001"
    user.email = "admin@example.com"
    user.password_hash = CryptContext(schemes=["bcrypt"], bcrypt__rounds=4).hash("adminpass123")
    user.email_verified = True
    user.display_name = "Admin"
    user.role = "admin"
    user.google_id = None
    user.created_at = datetime.now(timezone.utc)
    user.updated_at = datetime.now(timezone.utc)
    return user


@pytest.fixture
def regular_user():
    user = MagicMock()
    user.id = "regular-user-id-002"
    user.email = "user@example.com"
    user.password_hash = CryptContext(schemes=["bcrypt"], bcrypt__rounds=4).hash("userpass123")
    user.email_verified = True
    user.display_name = "Regular"
    user.role = "user"
    user.google_id = None
    user.created_at = datetime.now(timezone.utc)
    user.updated_at = datetime.now(timezone.utc)
    return user


@pytest.fixture
def admin_token(test_settings, admin_user):
    from nba_betting_agent.api.auth import create_access_token
    return create_access_token(
        admin_user.id, test_settings,
        email=admin_user.email, display_name=admin_user.display_name, role="admin",
    )


@pytest.fixture
def user_token(test_settings, regular_user):
    from nba_betting_agent.api.auth import create_access_token
    return create_access_token(
        regular_user.id, test_settings,
        email=regular_user.email, display_name=regular_user.display_name, role="user",
    )


@pytest.fixture
def client(test_settings, admin_user, regular_user):
    from nba_betting_agent.api.app import create_app
    from nba_betting_agent.api.deps import get_db_session
    from nba_betting_agent.api.middleware.rate_limit import limiter

    limiter.reset()
    app = create_app()

    users_db = {
        admin_user.id: admin_user,
        regular_user.id: regular_user,
    }
    users_by_email = {
        admin_user.email: admin_user,
        regular_user.email: regular_user,
    }
    audit_entries = []

    mock_session = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.close = AsyncMock()

    async def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db_session] = override_get_db

    # Build a mock session factory for get_current_admin_user
    async def _admin_execute(stmt):
        result = MagicMock()
        try:
            clause = stmt.whereclause
            if hasattr(clause, 'right') and hasattr(clause.right, 'value'):
                uid = clause.right.value
                result.scalar_one_or_none = MagicMock(return_value=users_db.get(uid))
                return result
        except Exception:
            pass
        result.scalar_one_or_none = MagicMock(return_value=None)
        return result

    mock_admin_session = AsyncMock()
    mock_admin_session.execute = AsyncMock(side_effect=_admin_execute)

    class _MockSessionCM:
        async def __aenter__(self):
            return mock_admin_session
        async def __aexit__(self, *a):
            pass

    mock_session_factory = MagicMock(return_value=_MockSessionCM())

    with patch("nba_betting_agent.api.routers.auth.user_service") as mock_user_svc, \
         patch("nba_betting_agent.api.routers.auth.email_service") as mock_email_svc, \
         patch("nba_betting_agent.db.session.AsyncSessionFactory", mock_session_factory), \
         patch("nba_betting_agent.api.routers.admin.admin_service") as mock_admin_svc:

        mock_email_svc.send_verification_email = AsyncMock(return_value=True)

        async def _get_by_email(session, email):
            return users_by_email.get(email.lower().strip())
        mock_user_svc.get_by_email = AsyncMock(side_effect=_get_by_email)

        # Admin service mocks
        async def _list_users(session, skip=0, limit=50):
            return list(users_db.values())[skip:skip + limit]

        async def _count_users(session):
            return len(users_db)

        async def _get_user_by_id(session, user_id):
            return users_db.get(user_id)

        async def _update_user_role(session, user_id, new_role):
            user = users_db.get(user_id)
            if user:
                user.role = new_role
            return user

        async def _delete_user(session, user_id):
            if user_id in users_db:
                del users_db[user_id]
                return True
            return False

        async def _get_system_stats(session):
            return {
                "total_users": len(users_db),
                "verified_users": sum(1 for u in users_db.values() if u.email_verified),
                "google_users": sum(1 for u in users_db.values() if u.google_id is not None),
                "signups_today": 1,
                "signups_this_week": 2,
            }

        async def _create_audit_entry(session, admin_id, action, target_id=None, details=None):
            entry = MagicMock()
            entry.id = len(audit_entries) + 1
            entry.timestamp = datetime.now(timezone.utc)
            entry.admin_id = admin_id
            entry.action = action
            entry.target_id = target_id
            entry.details = json.dumps(details) if details else None
            audit_entries.append(entry)
            return entry

        async def _list_audit_log(session, skip=0, limit=50):
            return audit_entries[skip:skip + limit]

        async def _count_audit_log(session):
            return len(audit_entries)

        mock_admin_svc.list_users = AsyncMock(side_effect=_list_users)
        mock_admin_svc.count_users = AsyncMock(side_effect=_count_users)
        mock_admin_svc.get_user_by_id = AsyncMock(side_effect=_get_user_by_id)
        mock_admin_svc.update_user_role = AsyncMock(side_effect=_update_user_role)
        mock_admin_svc.delete_user = AsyncMock(side_effect=_delete_user)
        mock_admin_svc.get_system_stats = AsyncMock(side_effect=_get_system_stats)
        mock_admin_svc.create_audit_entry = AsyncMock(side_effect=_create_audit_entry)
        mock_admin_svc.list_audit_log = AsyncMock(side_effect=_list_audit_log)
        mock_admin_svc.count_audit_log = AsyncMock(side_effect=_count_audit_log)

        app._test_audit_entries = audit_entries

        yield TestClient(app)

    app.dependency_overrides.clear()


# --- Admin Authorization Tests ---

def test_admin_list_users_success(client, admin_token):
    response = client.get(
        "/api/admin/users",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "users" in data
    assert "total" in data
    assert data["total"] == 2


def test_admin_stats_success(client, admin_token):
    response = client.get(
        "/api/admin/stats",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_users"] == 2
    assert "verified_users" in data
    assert "signups_today" in data


def test_admin_audit_log_success(client, admin_token):
    response = client.get(
        "/api/admin/audit-log",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "entries" in data
    assert "total" in data


def test_admin_change_role(client, admin_token, regular_user):
    response = client.patch(
        f"/api/admin/users/{regular_user.id}/role",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"role": "admin"},
    )
    assert response.status_code == 200
    assert response.json()["role"] == "admin"


def test_admin_change_role_creates_audit_entry(client, admin_token, regular_user):
    client.patch(
        f"/api/admin/users/{regular_user.id}/role",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"role": "admin"},
    )
    entries = client.app._test_audit_entries
    assert len(entries) >= 1
    last = entries[-1]
    assert last.action == "user.role_changed"
    assert last.target_id == regular_user.id


def test_admin_delete_user(client, admin_token, regular_user):
    response = client.delete(
        f"/api/admin/users/{regular_user.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    assert "deleted" in response.json()["message"].lower()


def test_admin_cannot_self_delete(client, admin_token, admin_user):
    response = client.delete(
        f"/api/admin/users/{admin_user.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 400
    assert "yourself" in response.json()["detail"].lower()


def test_admin_invalid_role_value(client, admin_token, regular_user):
    response = client.patch(
        f"/api/admin/users/{regular_user.id}/role",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"role": "superuser"},
    )
    assert response.status_code == 422


# --- Regular User Gets 403 ---

def test_regular_user_403_list_users(client, user_token):
    response = client.get(
        "/api/admin/users",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 403


def test_regular_user_403_stats(client, user_token):
    response = client.get(
        "/api/admin/stats",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 403


def test_regular_user_403_audit_log(client, user_token):
    response = client.get(
        "/api/admin/audit-log",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 403


def test_regular_user_403_delete(client, user_token, admin_user):
    response = client.delete(
        f"/api/admin/users/{admin_user.id}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 403


def test_regular_user_403_change_role(client, user_token, admin_user):
    response = client.patch(
        f"/api/admin/users/{admin_user.id}/role",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"role": "admin"},
    )
    assert response.status_code == 403


# --- Unauthenticated Gets 401 ---

def test_unauthenticated_401_list_users(client):
    response = client.get("/api/admin/users")
    assert response.status_code == 401


def test_unauthenticated_401_stats(client):
    response = client.get("/api/admin/stats")
    assert response.status_code == 401


def test_unauthenticated_401_audit_log(client):
    response = client.get("/api/admin/audit-log")
    assert response.status_code == 401
