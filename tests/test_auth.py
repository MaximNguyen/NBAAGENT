"""Integration tests for multi-user authentication system.

Tests PyJWT-based authentication, bcrypt password hashing, token refresh,
registration, email verification, and security requirements.
"""

import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest
from fastapi.testclient import TestClient
from passlib.context import CryptContext


# --- Fixtures ---

@pytest.fixture
def test_password():
    """Password for testing."""
    return "testpass123"


@pytest.fixture
def test_password_hash(test_password):
    """Bcrypt hash of test password (rounds=4 for speed)."""
    pwd_context = CryptContext(schemes=["bcrypt"], bcrypt__rounds=4)
    return pwd_context.hash(test_password)


@pytest.fixture
def test_user(test_password_hash):
    """Create a mock UserModel-like object."""
    user = MagicMock()
    user.id = "test-user-id-123"
    user.email = "test@example.com"
    user.password_hash = test_password_hash
    user.email_verified = True
    user.display_name = "Test User"
    user.role = "user"
    user.google_id = None
    user.created_at = datetime.now(timezone.utc)
    user.updated_at = datetime.now(timezone.utc)
    return user


@pytest.fixture
def test_settings(monkeypatch):
    """Set up test environment variables before importing app."""
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-that-is-at-least-32-characters-long")
    monkeypatch.setenv("DASHBOARD_PASSWORD_HASH", "")
    monkeypatch.setenv("ENVIRONMENT", "test")

    from nba_betting_agent.api.config import get_settings
    get_settings.cache_clear()

    yield get_settings()

    get_settings.cache_clear()


@pytest.fixture
def mock_db_session():
    """Create a mock async DB session."""
    session = AsyncMock()
    session.commit = AsyncMock()
    session.close = AsyncMock()
    session.flush = AsyncMock()
    return session


@pytest.fixture
def client(test_settings, test_user, mock_db_session):
    """Test client with mocked DB dependency."""
    from nba_betting_agent.api.app import create_app
    from nba_betting_agent.api.deps import get_db_session
    from nba_betting_agent.api.middleware.rate_limit import limiter

    # Reset rate limiter state between tests
    limiter.reset()

    app = create_app()

    # Track created users for register/login flow
    users_db = {"test@example.com": test_user}

    async def override_get_db():
        yield mock_db_session

    app.dependency_overrides[get_db_session] = override_get_db

    # Patch user service functions to use our in-memory store
    def _get_by_email(session, email):
        return users_db.get(email.lower().strip())

    async def _async_get_by_email(session, email):
        return _get_by_email(session, email)

    async def _async_create_user_email(session, email, password, display_name=None):
        pwd_context = CryptContext(schemes=["bcrypt"], bcrypt__rounds=4)
        new_user = MagicMock()
        new_user.id = uuid.uuid4().hex
        new_user.email = email.lower().strip()
        new_user.password_hash = pwd_context.hash(password)
        new_user.email_verified = False
        new_user.display_name = display_name or email.split("@")[0]
        new_user.google_id = None
        new_user.created_at = datetime.now(timezone.utc)
        new_user.updated_at = datetime.now(timezone.utc)
        users_db[new_user.email] = new_user
        return new_user

    async def _async_verify_user_email(session, user_id):
        for u in users_db.values():
            if u.id == user_id:
                u.email_verified = True
                return True
        return False

    with patch("nba_betting_agent.api.routers.auth.user_service") as mock_user_svc, \
         patch("nba_betting_agent.api.routers.auth.email_service") as mock_email_svc:
        mock_user_svc.get_by_email = AsyncMock(side_effect=_async_get_by_email)
        mock_user_svc.create_user_email = AsyncMock(side_effect=_async_create_user_email)
        mock_user_svc.verify_user_email = AsyncMock(side_effect=_async_verify_user_email)
        mock_user_svc.create_or_get_google_user = AsyncMock()
        mock_email_svc.send_verification_email = AsyncMock(return_value=True)

        yield TestClient(app)

    app.dependency_overrides.clear()


# --- Login Tests ---

def test_login_valid_credentials(client, test_password):
    """Valid credentials return 200 with access_token, refresh_token, and token_type."""
    response = client.post("/api/auth/login", json={
        "email": "test@example.com",
        "password": test_password
    })

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert len(data["access_token"]) > 0
    assert len(data["refresh_token"]) > 0


def test_login_invalid_password(client):
    """Invalid password returns 401."""
    response = client.post("/api/auth/login", json={
        "email": "test@example.com",
        "password": "wrongpassword"
    })

    assert response.status_code == 401
    assert "Invalid email or password" in response.json()["detail"]


def test_login_nonexistent_email(client):
    """Nonexistent email returns 401."""
    response = client.post("/api/auth/login", json={
        "email": "nobody@example.com",
        "password": "somepass123"
    })

    assert response.status_code == 401


def test_login_empty_password(client):
    """Empty password returns 422 (Pydantic validation)."""
    response = client.post("/api/auth/login", json={
        "email": "test@example.com",
        "password": ""
    })

    assert response.status_code == 422


def test_login_password_too_long(client):
    """Password longer than 72 chars returns 422."""
    response = client.post("/api/auth/login", json={
        "email": "test@example.com",
        "password": "a" * 73
    })

    assert response.status_code == 422


# --- Token Claims Tests ---

def test_access_token_has_correct_claims(client, test_password, test_settings):
    """Access token contains correct claims: sub=user_id, type=access, exp ~1hr."""
    response = client.post("/api/auth/login", json={
        "email": "test@example.com",
        "password": test_password
    })

    access_token = response.json()["access_token"]

    payload = jwt.decode(
        access_token,
        test_settings.jwt_secret_key,
        algorithms=["HS256"]
    )

    assert payload["sub"] == "test-user-id-123"
    assert payload["type"] == "access"
    assert "exp" in payload
    assert "iat" in payload
    assert payload.get("email") == "test@example.com"

    exp_time = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    now = datetime.now(timezone.utc)
    time_diff = (exp_time - now).total_seconds()

    assert 3595 < time_diff < 3605


def test_refresh_token_has_correct_claims(client, test_password, test_settings):
    """Refresh token contains correct claims: sub, type=refresh, exp ~7 days."""
    response = client.post("/api/auth/login", json={
        "email": "test@example.com",
        "password": test_password
    })

    refresh_token = response.json()["refresh_token"]

    payload = jwt.decode(
        refresh_token,
        test_settings.jwt_secret_key,
        algorithms=["HS256"]
    )

    assert payload["sub"] == "test-user-id-123"
    assert payload["type"] == "refresh"
    assert "exp" in payload
    assert "iat" in payload

    exp_time = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    now = datetime.now(timezone.utc)
    time_diff_days = (exp_time - now).total_seconds() / 86400

    assert 6.99 < time_diff_days < 7.01


# --- Refresh Endpoint Tests ---

def test_refresh_with_valid_refresh_token(client, test_password):
    """Valid refresh token returns new access token."""
    login_response = client.post("/api/auth/login", json={
        "email": "test@example.com",
        "password": test_password
    })
    refresh_token = login_response.json()["refresh_token"]

    refresh_response = client.post("/api/auth/refresh", json={
        "refresh_token": refresh_token
    })

    assert refresh_response.status_code == 200
    data = refresh_response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert data["refresh_token"] == refresh_token


def test_refresh_with_access_token_rejected(client, test_password):
    """Access token (not refresh) is rejected at refresh endpoint."""
    login_response = client.post("/api/auth/login", json={
        "email": "test@example.com",
        "password": test_password
    })
    access_token = login_response.json()["access_token"]

    refresh_response = client.post("/api/auth/refresh", json={
        "refresh_token": access_token
    })

    assert refresh_response.status_code == 401
    assert "Invalid refresh token" in refresh_response.json()["detail"]


def test_refresh_with_invalid_token_rejected(client):
    """Garbage token is rejected at refresh endpoint."""
    response = client.post("/api/auth/refresh", json={
        "refresh_token": "invalid.garbage.token"
    })

    assert response.status_code == 401


# --- Protected Endpoint Tests ---

def test_protected_endpoint_with_valid_token(client, test_password):
    """Protected endpoint accepts valid access token."""
    login_response = client.post("/api/auth/login", json={
        "email": "test@example.com",
        "password": test_password
    })
    access_token = login_response.json()["access_token"]

    response = client.get(
        "/api/opportunities",
        headers={"Authorization": f"Bearer {access_token}"}
    )

    assert response.status_code not in [401, 403]


def test_protected_endpoint_without_token(client):
    """Protected endpoint rejects requests without token."""
    response = client.get("/api/opportunities")

    assert response.status_code == 401


def test_protected_endpoint_with_expired_token(client, test_settings):
    """Expired token is rejected at protected endpoints."""
    past_time = datetime.now(timezone.utc) - timedelta(hours=2)
    expired_payload = {
        "sub": "test-user-id-123",
        "exp": past_time,
        "iat": past_time - timedelta(hours=1),
        "type": "access"
    }

    expired_token = jwt.encode(
        expired_payload,
        test_settings.jwt_secret_key,
        algorithm="HS256"
    )

    response = client.get(
        "/api/opportunities",
        headers={"Authorization": f"Bearer {expired_token}"}
    )

    assert response.status_code == 401


# --- Registration Tests ---

def test_register_new_user(client):
    """Registration with valid data returns success message."""
    response = client.post("/api/auth/register", json={
        "email": "newuser@example.com",
        "password": "securepass123",
        "display_name": "New User"
    })

    assert response.status_code == 200
    assert "Registration successful" in response.json()["message"]


def test_register_duplicate_email(client):
    """Registration with existing email returns 409."""
    response = client.post("/api/auth/register", json={
        "email": "test@example.com",
        "password": "securepass123"
    })

    assert response.status_code == 409
    assert "already registered" in response.json()["detail"]


def test_register_short_password(client):
    """Registration with password < 8 chars returns 422."""
    response = client.post("/api/auth/register", json={
        "email": "short@example.com",
        "password": "short"
    })

    assert response.status_code == 422


# --- Email Verification Tests ---

def test_verify_email_valid_token(client, test_settings):
    """Valid verification token marks email as verified."""
    from nba_betting_agent.api.auth import create_email_verification_token

    token = create_email_verification_token("test-user-id-123", test_settings)

    response = client.post("/api/auth/verify-email", json={"token": token})

    assert response.status_code == 200
    assert "verified" in response.json()["message"].lower()


def test_verify_email_invalid_token(client):
    """Invalid verification token returns 400."""
    response = client.post("/api/auth/verify-email", json={"token": "garbage.token.here"})

    assert response.status_code == 400


def test_verify_email_expired_token(client, test_settings):
    """Expired verification token returns 400."""
    past = datetime.now(timezone.utc) - timedelta(hours=48)
    payload = {
        "sub": "test-user-id-123",
        "exp": past,
        "iat": past - timedelta(hours=24),
        "type": "email_verification",
    }
    token = jwt.encode(payload, test_settings.jwt_secret_key, algorithm="HS256")

    response = client.post("/api/auth/verify-email", json={"token": token})

    assert response.status_code == 400


# --- Login with unverified email ---

def test_login_unverified_email_rejected(client):
    """Login with unverified email returns 403."""
    # Register (creates unverified user)
    client.post("/api/auth/register", json={
        "email": "unverified@example.com",
        "password": "securepass123"
    })

    # Try to login
    response = client.post("/api/auth/login", json={
        "email": "unverified@example.com",
        "password": "securepass123"
    })

    assert response.status_code == 403
    assert "not verified" in response.json()["detail"].lower()


# --- Security Tests ---

def test_no_hardcoded_credentials():
    """auth.py source code contains no hardcoded credentials."""
    auth_file = Path(__file__).parent.parent / "nba_betting_agent" / "api" / "auth.py"
    content = auth_file.read_text()

    assert "Maxim03" not in content
    assert "nba-ev-dashboard-secret" not in content
    assert "_PASSWORD_HASH = " not in content or "hashlib" not in content
    assert "_SECRET = " not in content or 'os.getenv("DASHBOARD_SECRET"' not in content


def test_settings_crash_without_jwt_secret(monkeypatch):
    """Settings validation fails if JWT_SECRET_KEY is missing."""
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    monkeypatch.delenv("DASHBOARD_PASSWORD_HASH", raising=False)

    from nba_betting_agent.api.config import get_settings
    from pydantic import ValidationError

    get_settings.cache_clear()

    with pytest.raises(ValidationError):
        get_settings()

    get_settings.cache_clear()


# --- WebSocket Auth Tests ---

def test_verify_ws_token_valid(test_settings):
    """verify_ws_token returns user_id for valid access token."""
    from nba_betting_agent.api.auth import create_access_token, verify_ws_token

    access_token = create_access_token("test-user-id", test_settings)
    user_id = verify_ws_token(access_token)

    assert user_id == "test-user-id"


def test_verify_ws_token_invalid(test_settings):
    """verify_ws_token returns None for garbage token."""
    from nba_betting_agent.api.auth import verify_ws_token

    result = verify_ws_token("invalid.garbage.token")

    assert result is None
