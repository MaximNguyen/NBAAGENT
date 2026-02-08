"""Opportunities endpoints - list and filter +EV betting opportunities."""

from typing import Optional

from fastapi import APIRouter, Path, Query, Request

from nba_betting_agent.api.middleware.rate_limit import limiter
from nba_betting_agent.api.schemas import OpportunitiesListResponse, OpportunityResponse
from nba_betting_agent.api.state import analysis_store
from nba_betting_agent.cli.filters import filter_opportunities, sort_opportunities

router = APIRouter(tags=["opportunities"])


def _opportunity_to_response(opp) -> OpportunityResponse:
    """Convert a BettingOpportunity dataclass to a Pydantic response."""
    return OpportunityResponse(**opp.__dict__)


@router.get("/opportunities", response_model=OpportunitiesListResponse)
@limiter.limit("100/minute")
async def list_opportunities(
    request: Request,
    min_ev: Optional[float] = Query(None, ge=-1.0, le=1.0, description="Minimum EV % threshold"),
    max_ev: Optional[float] = Query(None, ge=-1.0, le=1.0, description="Maximum EV % threshold"),
    confidence: Optional[str] = Query(None, max_length=20, description="Confidence level: high/medium/low"),
    team: Optional[str] = Query(None, max_length=10, description="Team code (e.g., BOS, LAL)"),
    market: Optional[str] = Query(None, max_length=50, description="Market type: h2h, spreads, totals"),
    sort_by: str = Query("ev_pct", max_length=50, description="Sort field"),
    limit: Optional[int] = Query(None, ge=1, le=100, description="Max results to return"),
):
    """List +EV opportunities from the latest completed analysis run."""
    latest = analysis_store.get_latest()
    if not latest or not latest.result:
        return OpportunitiesListResponse(opportunities=[], total=0)

    opportunities = latest.result.get("opportunities", [])

    # Apply filters (reuse existing CLI filter logic)
    filtered = filter_opportunities(
        opportunities,
        min_ev=min_ev,
        max_ev=max_ev,
        confidence=confidence,
        team=team,
        market=market,
    )

    # Sort
    sorted_opps = sort_opportunities(filtered, sort_by=sort_by)

    # Limit
    if limit and limit > 0:
        sorted_opps = sorted_opps[:limit]

    responses = [_opportunity_to_response(opp) for opp in sorted_opps]

    return OpportunitiesListResponse(
        opportunities=responses,
        total=len(responses),
        filters_applied={
            k: v
            for k, v in {
                "min_ev": min_ev,
                "max_ev": max_ev,
                "confidence": confidence,
                "team": team,
                "market": market,
            }.items()
            if v is not None
        },
    )


@router.get("/opportunities/{game_id}", response_model=list[OpportunityResponse])
@limiter.limit("100/minute")
async def get_opportunities_for_game(
    request: Request,
    game_id: str = Path(..., max_length=100)
):
    """Get all opportunities for a specific game."""
    latest = analysis_store.get_latest()
    if not latest or not latest.result:
        return []

    opportunities = latest.result.get("opportunities", [])
    game_opps = [opp for opp in opportunities if opp.game_id == game_id]
    return [_opportunity_to_response(opp) for opp in game_opps]
