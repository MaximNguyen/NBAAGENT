"""Health check endpoint."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from nba_betting_agent import __version__
from nba_betting_agent.api.deps import get_db_session
from nba_betting_agent.api.schemas import HealthResponse
from nba_betting_agent.db.repositories.games import GamesRepository

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check(session: AsyncSession = Depends(get_db_session)):
    """Check API and database health."""
    repo = GamesRepository(session)
    db_ok = await repo.check_health()

    return HealthResponse(
        status="ok" if db_ok else "degraded",
        version=__version__,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
