"""WebSocket endpoint for real-time analysis updates."""

import asyncio
import json
import time
from concurrent.futures import ThreadPoolExecutor
from queue import Empty, Queue
from typing import Optional

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from nba_betting_agent.api.auth import verify_ws_token
from nba_betting_agent.api.state import analysis_store

router = APIRouter(tags=["websocket"])
_ws_executor = ThreadPoolExecutor(max_workers=2)


def _run_streaming_analysis(
    run_id: str,
    query: str,
    min_ev: Optional[float],
    message_queue: Queue,
):
    """Run analysis and push step-by-step messages to the queue."""
    from nba_betting_agent.cli.parser import parse_query
    from nba_betting_agent.graph.graph import app

    run = analysis_store.get_run(run_id)
    if not run:
        message_queue.put({"type": "error", "message": "Run not found"})
        return

    run.status = "running"
    run.started_at = time.time()
    start = time.time()

    try:
        parsed = parse_query(query)

        filter_params = {
            "min_ev": min_ev if min_ev is not None else (parsed.min_ev or 0.02),
            "confidence": parsed.confidence,
            "limit": parsed.limit or 10,
        }

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

        message_queue.put({"type": "status", "status": "running", "step": "starting"})

        # Use app.stream() for step-by-step output
        steps = ["lines", "stats", "analysis", "communication"]
        step_names = {
            "lines": "lines_agent",
            "stats": "stats_agent",
            "analysis": "analysis_agent",
            "communication": "communication_agent",
        }

        for chunk in app.stream(state):
            for node_name, node_output in chunk.items():
                step_start = time.time()
                agent_name = step_names.get(node_name, node_name)

                message_queue.put({
                    "type": "status",
                    "status": "running",
                    "step": agent_name,
                })

                run.current_step = agent_name

                # If analysis node, emit opportunities
                if node_name == "analysis" and "opportunities" in node_output:
                    for opp in node_output["opportunities"]:
                        message_queue.put({
                            "type": "opportunity",
                            "opportunity": opp.__dict__,
                        })

                step_duration = int((time.time() - step_start) * 1000)
                message_queue.put({
                    "type": "agent_complete",
                    "agent": agent_name,
                    "duration_ms": step_duration,
                })

                # Merge node output into state for final result
                state.update(node_output)

        duration_ms = int((time.time() - start) * 1000)
        run.result = state
        run.status = "completed"
        run.completed_at = time.time()
        run.current_step = None
        run.errors = state.get("errors", [])

        opp_count = len(state.get("opportunities", []))
        message_queue.put({
            "type": "complete",
            "total_opportunities": opp_count,
            "duration_ms": duration_ms,
        })

    except Exception as e:
        run.status = "error"
        run.errors.append(str(e))
        run.completed_at = time.time()
        run.current_step = None
        message_queue.put({"type": "error", "message": str(e)})


@router.websocket("/ws/analysis/{run_id}")
async def websocket_analysis(websocket: WebSocket, run_id: str, token: str = Query(...)):
    """WebSocket for real-time analysis progress.

    Requires ?token=<jwt> query parameter for authentication.

    Message protocol:
        {"type": "status", "status": "running", "step": "lines_agent"}
        {"type": "agent_complete", "agent": "lines_agent", "duration_ms": 2340}
        {"type": "opportunity", "opportunity": {...}}
        {"type": "complete", "total_opportunities": 5, "duration_ms": 12500}
        {"type": "error", "message": "..."}
    """
    # Validate token before accepting
    username = verify_ws_token(token)
    if not username:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    await websocket.accept()

    run = analysis_store.get_run(run_id)
    if not run:
        await websocket.send_json({"type": "error", "message": f"Run {run_id} not found"})
        await websocket.close()
        return

    # If run is already completed, send results immediately
    if run.status == "completed":
        opp_count = len(run.result.get("opportunities", [])) if run.result else 0
        await websocket.send_json({
            "type": "complete",
            "total_opportunities": opp_count,
            "duration_ms": run.duration_ms,
        })
        await websocket.close()
        return

    # Start streaming analysis in background thread
    message_queue: Queue = Queue()

    loop = asyncio.get_event_loop()
    loop.run_in_executor(
        _ws_executor,
        _run_streaming_analysis,
        run_id,
        run.query,
        None,
        message_queue,
    )

    try:
        # Relay messages from queue to WebSocket
        while True:
            try:
                msg = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: message_queue.get(timeout=0.5)
                )
                await websocket.send_json(msg)

                # Close on terminal messages
                if msg.get("type") in ("complete", "error"):
                    break

            except Empty:
                # Send heartbeat
                try:
                    await websocket.send_json({"type": "heartbeat"})
                except Exception:
                    break

    except WebSocketDisconnect:
        pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
