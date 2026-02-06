"""Authentication endpoint."""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from nba_betting_agent.api.auth import create_token, verify_credentials

router = APIRouter(tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    username: str


@router.post("/auth/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """Authenticate and receive a JWT token."""
    if not verify_credentials(request.username, request.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    token = create_token(request.username)
    return LoginResponse(token=token, username=request.username)
