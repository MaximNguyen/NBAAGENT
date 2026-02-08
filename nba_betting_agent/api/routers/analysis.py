"""Analysis endpoints - trigger and monitor analysis pipeline runs."""

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from fastapi import APIRouter, Path

from nba_betting_agent.api.schemas import (
    AnalysisRunRequest,
    AnalysisRunResponse,
    AnalysisStatusResponse,
    OpportunityResponse,
)
from nba_betting_agent.api.state import analysis_store

router = APIRouter(tags=["analysis"])
_executor = ThreadPoolExecutor(max_workers=2)


def _run_analysis_sync(run_id: str, query: str, min_ev: float, confidence: Optional[str], limit: Optional[int]):
    """Run the analysis pipeline synchronously (called in executor)."""
    from nba_betting_agent.cli.parser import parse_query
    from nba_betting_agent.graph.graph import invoke_with_tracing

    run = analysis_store.get_run(run_id)
    if not run:
        return

    run.status = "running"
    run.started_at = time.time()

    try:
        # Parse the query (reuse CLI parser)
        parsed = parse_query(query)

        # Build filter params
        filter_params = {}
        if min_ev is not None:
            filter_params["min_ev"] = min_ev
        elif parsed.min_ev is not None:
            filter_params["min_ev"] = parsed.min_ev
        else:
            filter_params["min_ev"] = 0.02
        filter_params["confidence"] = confidence or parsed.confidence
        filter_params["limit"] = limit or parsed.limit or 10

        # Build initial state (same shape as cli/main.py lines 147-163)
        state = {
            "query": query,
            "game_date": parsed.game_date,
            "teams": parsed.teams or [],
            "filter_params": filter_params,
            "errors": [],
            "messages": [],
            "odds_data": [],
            "line_discrepancies": [],
            "team_stats": {},
            "player_stats": {},
            "injuries": [],
            "estimated_probabilities": {},
            "expected_values": [],
            "opportunities": [],
            "recommendation": "",
        }

        # Track steps
        run.current_step = "lines_agent"

        # Invoke the graph (same as CLI)
        result = invoke_with_tracing(
            state=state,
            tags=["dashboard", "api"],
            metadata={
                "query_type": "dashboard_analysis",
                "run_id": run_id,
                "min_ev_threshold": filter_params.get("min_ev", 0),
            },
        )

        run.result = result
        run.errors = result.get("errors", [])
        run.status = "completed"
        run.current_step = None

    except Exception as e:
        run.status = "error"
        run.errors.append(str(e))
        run.current_step = None
    finally:
        run.completed_at = time.time()


@router.post("/analysis/run", response_model=AnalysisRunResponse)
async def trigger_analysis(request: AnalysisRunRequest):
    """Trigger a new analysis pipeline run.

    Returns immediately with a run_id. Poll /api/analysis/{run_id} for status.
    """
    run = analysis_store.create_run(request.query)

    # Run in background thread (graph is sync)
    loop = asyncio.get_event_loop()
    loop.run_in_executor(
        _executor,
        _run_analysis_sync,
        run.run_id,
        request.query,
        request.min_ev,
        request.confidence,
        request.limit,
    )

    return AnalysisRunResponse(
        run_id=run.run_id,
        status="pending",
        message="Analysis started. Poll /api/analysis/{run_id} for status.",
    )


@router.get("/analysis/latest", response_model=AnalysisStatusResponse)
async def get_latest_analysis():
    """Get the most recent completed analysis run."""
    run = analysis_store.get_latest()
    if not run:
        return AnalysisStatusResponse(
            run_id="none",
            status="no_runs",
        )

    opportunities = []
    recommendation = None
    if run.result:
        opps = run.result.get("opportunities", [])
        opportunities = [OpportunityResponse(**opp.__dict__) for opp in opps]
        recommendation = run.result.get("recommendation")

    return AnalysisStatusResponse(
        run_id=run.run_id,
        status=run.status,
        started_at=str(run.started_at) if run.started_at else None,
        completed_at=str(run.completed_at) if run.completed_at else None,
        duration_ms=run.duration_ms,
        current_step=run.current_step,
        opportunities=opportunities,
        errors=run.errors,
        recommendation=recommendation,
    )


@router.get("/analysis/{run_id}", response_model=AnalysisStatusResponse)
async def get_analysis_status(run_id: str = Path(..., max_length=100)):
    """Get the status and results of an analysis run."""
    run = analysis_store.get_run(run_id)
    if not run:
        return AnalysisStatusResponse(
            run_id=run_id,
            status="not_found",
        )

    opportunities = []
    recommendation = None
    if run.result:
        opps = run.result.get("opportunities", [])
        opportunities = [OpportunityResponse(**opp.__dict__) for opp in opps]
        recommendation = run.result.get("recommendation")

    return AnalysisStatusResponse(
        run_id=run.run_id,
        status=run.status,
        started_at=str(run.started_at) if run.started_at else None,
        completed_at=str(run.completed_at) if run.completed_at else None,
        duration_ms=run.duration_ms,
        current_step=run.current_step,
        opportunities=opportunities,
        errors=run.errors,
        recommendation=recommendation,
    )
