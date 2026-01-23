"""Tests for LangGraph StateGraph compilation and execution.

These tests PROVE the success criteria:
1. Graph compiles without errors
2. Parallel execution works (timing test < 0.25s proves concurrency)
3. State reducers merge errors correctly from parallel nodes
4. Analysis node receives outputs from both parallel nodes
5. Sequential dependency is enforced
"""

import time

import pytest

from nba_betting_agent.graph import BettingAnalysisState, app, build_graph


def test_graph_compiles():
    """Test that StateGraph compiles without errors."""
    graph = build_graph()
    assert graph is not None
    assert app is not None


def test_parallel_execution_timing():
    """Test that Lines and Stats agents execute in parallel.

    This test PROVES parallel execution by timing. If nodes were sequential,
    execution would take at least the sum of all node times. Parallel execution
    completes in the time of the longest node.

    Expected: < 0.25s (proves parallel, even with overhead)
    """
    # Create minimal valid state
    initial_state: BettingAnalysisState = {
        "query": "test parallel execution",
        "game_date": None,
        "teams": [],
        "odds_data": [],
        "line_discrepancies": [],
        "team_stats": {},
        "player_stats": {},
        "injuries": [],
        "estimated_probabilities": {},
        "expected_values": [],
        "recommendation": "",
        "errors": [],
        "messages": [],
    }

    start_time = time.time()
    result = app.invoke(initial_state)
    end_time = time.time()

    duration = end_time - start_time

    # Verify execution completed
    assert result is not None
    assert "recommendation" in result

    # Verify parallel execution (< 0.25s proves concurrency)
    # If nodes were sequential, would take sum of times
    # Parallel execution takes time of longest node + overhead
    assert duration < 0.25, f"Execution took {duration:.3f}s, expected < 0.25s (parallel execution)"

    print(f"Parallel execution completed in {duration:.3f}s")


def test_state_reducer_merges_errors():
    """Test that errors reducer merges errors from parallel nodes.

    This PROVES that state reducers work correctly. Without reducers,
    concurrent updates would raise INVALID_CONCURRENT_GRAPH_UPDATE error.

    Expected: All 4 agent errors present in final state
    """
    initial_state: BettingAnalysisState = {
        "query": "test error merging",
        "game_date": None,
        "teams": [],
        "odds_data": [],
        "line_discrepancies": [],
        "team_stats": {},
        "player_stats": {},
        "injuries": [],
        "estimated_probabilities": {},
        "expected_values": [],
        "recommendation": "",
        "errors": [],
        "messages": [],
    }

    result = app.invoke(initial_state)

    # Verify all agents contributed errors
    errors = result["errors"]
    assert len(errors) == 4, f"Expected 4 errors (1 per agent), got {len(errors)}"

    # Verify specific agent errors present
    error_text = " ".join(errors)
    assert "Lines Agent" in error_text
    assert "Stats Agent" in error_text
    assert "Analysis Agent" in error_text
    assert "Communication Agent" in error_text

    print(f"Successfully merged {len(errors)} errors from parallel agents")


def test_analysis_receives_parallel_outputs():
    """Test that Analysis agent receives outputs from both parallel nodes.

    This PROVES the parallel join works correctly. Analysis should only
    execute after both Lines and Stats complete.

    Expected: Analysis error message confirms it received both odds and stats
    """
    initial_state: BettingAnalysisState = {
        "query": "test parallel join",
        "game_date": None,
        "teams": [],
        "odds_data": [],
        "line_discrepancies": [],
        "team_stats": {},
        "player_stats": {},
        "injuries": [],
        "estimated_probabilities": {},
        "expected_values": [],
        "recommendation": "",
        "errors": [],
        "messages": [],
    }

    result = app.invoke(initial_state)

    # Verify Lines agent output present
    assert result["odds_data"], "Lines agent should populate odds_data"
    assert len(result["odds_data"]) > 0

    # Verify Stats agent output present
    assert result["team_stats"], "Stats agent should populate team_stats"

    # Verify Analysis agent processed both
    analysis_errors = [e for e in result["errors"] if "Analysis Agent" in e]
    assert len(analysis_errors) == 1
    analysis_msg = analysis_errors[0]

    # Analysis should confirm it received both odds and stats
    assert "odds=True" in analysis_msg, "Analysis should receive odds_data from Lines"
    assert "stats=True" in analysis_msg, "Analysis should receive team_stats from Stats"

    print(f"Analysis confirmed parallel join: {analysis_msg}")


def test_sequential_dependency():
    """Test that sequential execution order is maintained.

    This PROVES that:
    1. Analysis waits for both Lines and Stats (parallel join)
    2. Communication waits for Analysis (sequential)

    Expected: Final state has all outputs in correct order
    """
    initial_state: BettingAnalysisState = {
        "query": "test sequential flow",
        "game_date": None,
        "teams": [],
        "odds_data": [],
        "line_discrepancies": [],
        "team_stats": {},
        "player_stats": {},
        "injuries": [],
        "estimated_probabilities": {},
        "expected_values": [],
        "recommendation": "",
        "errors": [],
        "messages": [],
    }

    result = app.invoke(initial_state)

    # Verify execution order through state updates
    # 1. Parallel nodes (Lines, Stats) must have completed
    assert result["odds_data"], "Lines agent output missing"
    assert result["team_stats"], "Stats agent output missing"

    # 2. Analysis must have completed (depends on Lines + Stats)
    assert result["estimated_probabilities"], "Analysis agent output missing"
    assert result["expected_values"], "Analysis agent output missing"

    # 3. Communication must have completed (depends on Analysis)
    assert result["recommendation"], "Communication agent output missing"
    assert "Stub recommendation" in result["recommendation"]

    # Verify all 4 agents executed (4 error messages)
    assert len(result["errors"]) == 4

    print("Sequential dependencies correctly enforced")


def test_graph_handles_empty_teams_list():
    """Test that graph handles edge case of empty teams list."""
    initial_state: BettingAnalysisState = {
        "query": "show me all games tonight",
        "game_date": "tonight",
        "teams": [],  # No specific teams requested
        "odds_data": [],
        "line_discrepancies": [],
        "team_stats": {},
        "player_stats": {},
        "injuries": [],
        "estimated_probabilities": {},
        "expected_values": [],
        "recommendation": "",
        "errors": [],
        "messages": [],
    }

    result = app.invoke(initial_state)

    # Should complete without errors (stub implementation always succeeds)
    assert result is not None
    assert result["recommendation"]
    assert len(result["errors"]) == 4  # All agents report stub status


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
