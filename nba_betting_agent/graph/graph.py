"""LangGraph StateGraph compilation with parallel and sequential execution.

This module builds the multi-agent workflow with:
- Parallel execution: Lines and Stats agents run concurrently
- Sequential execution: Analysis waits for both, Communication waits for Analysis
- State reducers: Prevent INVALID_CONCURRENT_GRAPH_UPDATE errors
- LangSmith tracing: Optional observability when LANGSMITH_TRACING=true
"""

import os
from typing import Any

from langgraph.graph import END, START, StateGraph

from nba_betting_agent.graph.nodes import (
    analysis_agent,
    communication_agent,
    lines_agent,
    stats_agent,
)
from nba_betting_agent.graph.state import BettingAnalysisState


def build_graph() -> StateGraph:
    """Build the betting analysis StateGraph with parallel and sequential edges.

    Graph structure:
        START
          ├─> lines_agent ──┐
          └─> stats_agent ──┤
                             ├─> analysis_agent -> communication_agent -> END

    Returns:
        Compiled StateGraph ready for invocation
    """
    # Create graph with typed state
    graph = StateGraph(BettingAnalysisState)

    # Add all agent nodes
    graph.add_node("lines", lines_agent)
    graph.add_node("stats", stats_agent)
    graph.add_node("analysis", analysis_agent)
    graph.add_node("communication", communication_agent)

    # Parallel edges: Both Lines and Stats start immediately
    graph.add_edge(START, "lines")
    graph.add_edge(START, "stats")

    # Sequential edges: Analysis waits for both parallel nodes
    graph.add_edge("lines", "analysis")
    graph.add_edge("stats", "analysis")

    # Sequential edges: Communication waits for Analysis
    graph.add_edge("analysis", "communication")

    # End after Communication
    graph.add_edge("communication", END)

    return graph.compile()


# Pre-compiled app for easy import and invocation
app = build_graph()


def invoke_with_tracing(
    state: dict[str, Any],
    tags: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Invoke the graph with optional LangSmith tracing metadata.

    LangSmith tracing is automatically enabled when LANGSMITH_TRACING=true.
    This function adds optional tags and metadata for trace filtering and analysis.

    Args:
        state: Initial state dict for the workflow
        tags: Optional list of tags for trace filtering (e.g., ["production", "high-confidence"])
        metadata: Optional metadata dict for trace context (e.g., {"user_id": "123", "session": "abc"})

    Returns:
        Final state dict after workflow execution

    Example:
        >>> result = invoke_with_tracing(
        ...     {"query": "find +ev games tonight", "teams": [], ...},
        ...     tags=["cli", "production"],
        ...     metadata={"query_type": "tonight", "min_ev": 0.02}
        ... )
    """
    # Check if LangSmith tracing is enabled via environment variable
    tracing_enabled = os.getenv("LANGSMITH_TRACING", "false").lower() == "true"

    # Build config for invocation
    config: dict[str, Any] = {}

    if tracing_enabled and (tags or metadata):
        # Add tags and metadata only if tracing is enabled
        if tags:
            config["tags"] = tags
        if metadata:
            config["metadata"] = metadata

    # Invoke graph with or without config
    if config:
        return app.invoke(state, config=config)
    else:
        return app.invoke(state)
