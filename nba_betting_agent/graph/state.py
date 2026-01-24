"""State management for multi-agent betting analysis.

Uses TypedDict for performance (not Pydantic) with reducers for parallel execution.
"""

import operator
from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages
from nba_betting_agent.agents.analysis_agent.agent import BettingOpportunity


class BettingAnalysisState(TypedDict):
    """State shared across all agents in the betting analysis workflow.

    Input fields:
        query: Natural language input from CLI
        game_date: Parsed date like "tonight", "2026-01-24", or None
        teams: Parsed team names like ["celtics", "lakers"]
        filter_params: Filter criteria from parser (min_ev, confidence, limit)

    Lines Agent outputs:
        odds_data: Scraped odds from sportsbooks
        line_discrepancies: Differences between books

    Stats Agent outputs:
        team_stats: Team performance data
        player_stats: Individual player data
        injuries: Injury reports

    Analysis Agent outputs:
        estimated_probabilities: Probability estimates per outcome
        expected_values: EV calculations for each bet (dict form)
        opportunities: Typed BettingOpportunity objects for display

    Communication Agent outputs:
        recommendation: Formatted output for user

    Metadata (with reducers for parallel execution):
        messages: Message history with add_messages reducer
        errors: Error accumulation with add reducer
    """

    # Input fields
    query: str
    game_date: str | None
    teams: list[str]
    filter_params: dict

    # Lines Agent outputs
    odds_data: list[dict]
    line_discrepancies: list[dict]

    # Stats Agent outputs
    team_stats: dict
    player_stats: dict
    injuries: list[dict]

    # Analysis Agent outputs
    estimated_probabilities: dict
    expected_values: list[dict]
    opportunities: list[BettingOpportunity]  # Typed objects for formatters

    # Communication Agent outputs
    recommendation: str

    # Metadata with reducers (CRITICAL for parallel execution)
    messages: Annotated[list, add_messages]
    errors: Annotated[list[str], operator.add]
