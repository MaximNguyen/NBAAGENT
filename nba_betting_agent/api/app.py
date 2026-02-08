"""FastAPI application factory."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from nba_betting_agent import __version__
from nba_betting_agent.api.auth import get_current_user
from nba_betting_agent.api.config import get_settings
from nba_betting_agent.api.middleware import (
    RequestLoggingMiddleware,
    SecurityHeadersMiddleware,
)
from nba_betting_agent.api.routers import auth, health


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown hooks."""
    # Validate configuration at startup (crashes if secrets missing)
    settings = get_settings()

    from nba_betting_agent.monitoring import configure_logging

    log_mode = settings.environment
    configure_logging(log_mode)
    yield


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="NBA Betting Agent Dashboard",
        description="Analytics dashboard for NBA +EV betting opportunities",
        version=__version__,
        lifespan=lifespan,
    )

    # Middleware stack (runs in REVERSE order of registration)
    # Last added = first executed

    # 3. Request logging (executes last, captures final response)
    app.add_middleware(RequestLoggingMiddleware)

    # 2. Security headers (executes second, adds headers to response)
    app.add_middleware(SecurityHeadersMiddleware)

    # 1. CORS (executes first, handles preflight + sets CORS headers)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://localhost:3000",
            "http://127.0.0.1:5173",
            "https://sportagent.lol",
            "https://www.sportagent.lol",
        ],
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Content-Type", "Authorization"],
    )

    # Public routes (no auth required)
    app.include_router(auth.router, prefix="/api")
    app.include_router(health.router, prefix="/api")

    # Protected routes (require valid JWT)
    from nba_betting_agent.api.routers import (
        analysis,
        history,
        metrics,
        odds,
        opportunities,
        ws,
    )

    protected = [
        opportunities.router,
        analysis.router,
        odds.router,
        metrics.router,
        history.router,
    ]
    for router in protected:
        app.include_router(
            router,
            prefix="/api",
            dependencies=[Depends(get_current_user)],
        )

    # WebSocket handles its own token validation via query param
    app.include_router(ws.router)

    # Serve built frontend if available (production)
    static_dir = Path(__file__).parent.parent.parent / "dashboard" / "dist"
    if static_dir.exists():
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="frontend")

    return app
