"""LangGraph StateGraph compilation with parallel and sequential execution.

This module builds the multi-agent workflow with:
- Parallel execution: Lines and Stats agents run concurrently
- Sequential execution: Analysis waits for both, Communication waits for Analysis
- State reducers: Prevent INVALID_CONCURRENT_GRAPH_UPDATE errors
"""

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
