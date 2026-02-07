"""Integration tests for authentication system.

Tests PyJWT-based authentication, bcrypt password hashing, token refresh,
and security requirements for the dashboard API.
"""

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
import pytest
from fastapi.testclient import TestClient
from passlib.context import CryptContext


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
def test_settings(monkeypatch, test_password_hash):
    """Set up test environment variables before importing app."""
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-that-is-at-least-32-characters-long")
    monkeypatch.setenv("DASHBOARD_PASSWORD_HASH", test_password_hash)
    monkeypatch.setenv("ENVIRONMENT", "test")

    # Clear settings cache to pick up new env vars
    from nba_betting_agent.api.config import get_settings
    get_settings.cache_clear()

    yield get_settings()

    # Clean up
    get_settings.cache_clear()


@pytest.fixture
def client(test_settings):
    """Test client with test settings."""
    from nba_betting_agent.api.app import create_app
    app = create_app()
    return TestClient(app)


# --- Login Tests ---

def test_login_valid_credentials(client, test_password):
    """Valid credentials return 200 with access_token, refresh_token, and token_type."""
    response = client.post("/api/auth/login", json={
        "username": "test",
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
        "username": "test",
        "password": "wrongpassword"
    })

    assert response.status_code == 401
    assert "Invalid username or password" in response.json()["detail"]


def test_login_empty_password(client):
    """Empty password returns 422 (Pydantic validation)."""
    response = client.post("/api/auth/login", json={
        "username": "test",
        "password": ""
    })

    assert response.status_code == 422


def test_login_password_too_long(client):
    """Password longer than 72 chars returns 422."""
    response = client.post("/api/auth/login", json={
        "username": "test",
        "password": "a" * 73
    })

    assert response.status_code == 422


# --- Token Claims Tests ---

def test_access_token_has_correct_claims(client, test_password, test_settings):
    """Access token contains correct claims: sub, type=access, exp ~1hr."""
    response = client.post("/api/auth/login", json={
        "username": "test",
        "password": test_password
    })

    access_token = response.json()["access_token"]

    # Decode without verification to inspect claims
    payload = jwt.decode(
        access_token,
        test_settings.jwt_secret_key,
        algorithms=["HS256"]
    )

    assert payload["sub"] == "dashboard"  # Single-user system
    assert payload["type"] == "access"
    assert "exp" in payload
    assert "iat" in payload

    # Check expiry is approximately 1 hour from now
    exp_time = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    now = datetime.now(timezone.utc)
    time_diff = (exp_time - now).total_seconds()

    # Should be close to 60 minutes (allow 5 second tolerance)
    assert 3595 < time_diff < 3605


def test_refresh_token_has_correct_claims(client, test_password, test_settings):
    """Refresh token contains correct claims: sub, type=refresh, exp ~7 days."""
    response = client.post("/api/auth/login", json={
        "username": "test",
        "password": test_password
    })

    refresh_token = response.json()["refresh_token"]

    payload = jwt.decode(
        refresh_token,
        test_settings.jwt_secret_key,
        algorithms=["HS256"]
    )

    assert payload["sub"] == "dashboard"
    assert payload["type"] == "refresh"
    assert "exp" in payload
    assert "iat" in payload

    # Check expiry is approximately 7 days from now
    exp_time = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    now = datetime.now(timezone.utc)
    time_diff_days = (exp_time - now).total_seconds() / 86400

    # Should be close to 7 days (allow 1 minute tolerance)
    assert 6.99 < time_diff_days < 7.01


# --- Refresh Endpoint Tests ---

def test_refresh_with_valid_refresh_token(client, test_password):
    """Valid refresh token returns new access token."""
    # Login to get tokens
    login_response = client.post("/api/auth/login", json={
        "username": "test",
        "password": test_password
    })
    refresh_token = login_response.json()["refresh_token"]

    # Use refresh token
    refresh_response = client.post("/api/auth/refresh", json={
        "refresh_token": refresh_token
    })

    assert refresh_response.status_code == 200
    data = refresh_response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"

    # Refresh token should be the same
    assert data["refresh_token"] == refresh_token


def test_refresh_with_access_token_rejected(client, test_password):
    """Access token (not refresh) is rejected at refresh endpoint."""
    # Login to get tokens
    login_response = client.post("/api/auth/login", json={
        "username": "test",
        "password": test_password
    })
    access_token = login_response.json()["access_token"]

    # Try to use access token at refresh endpoint (should fail)
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
    # Login to get access token
    login_response = client.post("/api/auth/login", json={
        "username": "test",
        "password": test_password
    })
    access_token = login_response.json()["access_token"]

    # Access protected endpoint
    response = client.get(
        "/api/opportunities",
        headers={"Authorization": f"Bearer {access_token}"}
    )

    # Should not be 401/403 (actual response depends on data availability)
    assert response.status_code not in [401, 403]


def test_protected_endpoint_without_token(client):
    """Protected endpoint rejects requests without token."""
    response = client.get("/api/opportunities")

    assert response.status_code == 401  # OAuth2PasswordBearer returns 401 for missing token


def test_protected_endpoint_with_expired_token(client, test_settings):
    """Expired token is rejected at protected endpoints."""
    # Create an expired token manually
    past_time = datetime.now(timezone.utc) - timedelta(hours=2)
    expired_payload = {
        "sub": "dashboard",
        "exp": past_time,
        "iat": past_time - timedelta(hours=1),
        "type": "access"
    }

    expired_token = jwt.encode(
        expired_payload,
        test_settings.jwt_secret_key,
        algorithm="HS256"
    )

    # Try to use expired token
    response = client.get(
        "/api/opportunities",
        headers={"Authorization": f"Bearer {expired_token}"}
    )

    assert response.status_code == 401


# --- Security Tests ---

def test_no_hardcoded_credentials():
    """auth.py source code contains no hardcoded credentials."""
    auth_file = Path(__file__).parent.parent / "nba_betting_agent" / "api" / "auth.py"
    content = auth_file.read_text()

    # Check for old hardcoded values
    assert "Maxim03" not in content
    assert "nba-ev-dashboard-secret" not in content
    assert "_PASSWORD_HASH = " not in content or "hashlib" not in content
    assert "_SECRET = " not in content or 'os.getenv("DASHBOARD_SECRET"' not in content


def test_settings_crash_without_env_vars(monkeypatch):
    """Settings validation fails if required env vars are missing."""
    # Clear all auth env vars
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
    """verify_ws_token returns username for valid access token."""
    from nba_betting_agent.api.auth import create_access_token, verify_ws_token

    access_token = create_access_token("testuser", test_settings)
    username = verify_ws_token(access_token)

    assert username == "testuser"


def test_verify_ws_token_invalid(test_settings):
    """verify_ws_token returns None for garbage token."""
    from nba_betting_agent.api.auth import verify_ws_token

    result = verify_ws_token("invalid.garbage.token")

    assert result is None
