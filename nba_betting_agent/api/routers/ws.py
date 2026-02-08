"""WebSocket endpoint for real-time analysis updates."""

import asyncio
import json
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from queue import Empty, Queue
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from nba_betting_agent.api.auth import verify_ws_token
from nba_betting_agent.api.state import analysis_store

router = APIRouter(tags=["websocket"])
_ws_executor = ThreadPoolExecutor(max_workers=2)


def extract_token_from_protocol(websocket: WebSocket) -> str | None:
    """Extract JWT from Sec-WebSocket-Protocol header.

    Client sends: Sec-WebSocket-Protocol: jwt.token.<base64_jwt>
    The JWT itself contains dots, so rejoin everything after the "jwt.token." prefix.
    """
    protocol = websocket.headers.get("sec-websocket-protocol")
    if not protocol:
        return None

    prefix = "jwt.token."
    if not protocol.startswith(prefix):
        return None

    return protocol[len(prefix):]


class ConnectionManager:
    """Manage WebSocket connections with per-user limits (RATE-04)."""

    def __init__(self, max_per_user: int = 2):
        self.active_connections: dict[str, list[WebSocket]] = defaultdict(list)
        self.max_per_user = max_per_user

    async def connect(self, websocket: WebSocket, username: str) -> bool:
        """Accept connection if under limit, reject with 4003 otherwise.

        Args:
            websocket: WebSocket connection to manage
            username: User identifier

        Returns:
            True if connection accepted, False if rejected
        """
        if len(self.active_connections[username]) >= self.max_per_user:
            await websocket.close(code=4003, reason="Maximum concurrent connections exceeded")
            return False
        # Echo subprotocol on accept (required by WebSocket spec)
        protocol = websocket.headers.get("sec-websocket-protocol")
        await websocket.accept(subprotocol=protocol)
        self.active_connections[username].append(websocket)
        return True

    def disconnect(self, websocket: WebSocket, username: str):
        """Remove connection from tracking.

        Args:
            websocket: WebSocket connection to remove
            username: User identifier
        """
        try:
            self.active_connections[username].remove(websocket)
            if not self.active_connections[username]:
                del self.active_connections[username]
        except (ValueError, KeyError):
            pass

    def get_connection_count(self, username: str) -> int:
        """Get current connection count for a user.

        Args:
            username: User identifier

        Returns:
            Number of active connections
        """
        return len(self.active_connections[username])


connection_manager = ConnectionManager(max_per_user=2)


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

    start = time.time()
    analysis_store.update_run_status(run_id, "running", started_at=start)

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

                analysis_store.update_run(run_id, current_step=agent_name)

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
        analysis_store.update_run_status(
            run_id,
            "completed",
            result=state,
            completed_at=time.time(),
            current_step=None,
            errors=state.get("errors", [])
        )

        opp_count = len(state.get("opportunities", []))
        message_queue.put({
            "type": "complete",
            "total_opportunities": opp_count,
            "duration_ms": duration_ms,
        })

    except Exception as e:
        run = analysis_store.get_run(run_id)
        errors = run.errors + [str(e)] if run else [str(e)]
        analysis_store.update_run_status(
            run_id,
            "error",
            errors=errors,
            completed_at=time.time(),
            current_step=None
        )
        message_queue.put({"type": "error", "message": str(e)})


@router.websocket("/ws/analysis/{run_id}")
async def websocket_analysis(websocket: WebSocket, run_id: str):
    """WebSocket for real-time analysis progress.

    Authenticates via Sec-WebSocket-Protocol header with format: jwt.token.<jwt>

    Message protocol:
        {"type": "status", "status": "running", "step": "lines_agent"}
        {"type": "agent_complete", "agent": "lines_agent", "duration_ms": 2340}
        {"type": "opportunity", "opportunity": {...}}
        {"type": "complete", "total_opportunities": 5, "duration_ms": 12500}
        {"type": "error", "message": "..."}
    """
    # Extract and validate token from Sec-WebSocket-Protocol header
    token = extract_token_from_protocol(websocket)
    if not token:
        await websocket.close(code=4001, reason="Missing or invalid protocol header")
        return

    username = verify_ws_token(token)
    if not username:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    # Check connection limit and accept/reject
    connected = await connection_manager.connect(websocket, username)
    if not connected:
        return  # Rejected due to limit (close code 4003 sent by manager)

    try:
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
        connection_manager.disconnect(websocket, username)
        try:
            await websocket.close()
        except Exception:
            pass
