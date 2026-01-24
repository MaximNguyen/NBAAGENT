"""Analysis agent for calculating expected value and identifying +EV betting opportunities.

This module provides the mathematical foundation for bet analysis:
- Vig removal to calculate fair odds
- Expected value calculations
- Kelly criterion bet sizing
- LLM-powered qualitative matchup analysis
"""

from nba_betting_agent.agents.analysis_agent.ev_calculator import (
    calculate_ev,
    calculate_kelly_bet,
    evaluate_opportunity,
)
from nba_betting_agent.agents.analysis_agent.llm_analyzer import (
    LLMAnalyzer,
    MatchupAnalysis,
    analyze_matchup,
)
from nba_betting_agent.agents.analysis_agent.vig_removal import (
    calculate_fair_odds,
    get_market_vig,
    remove_vig,
)

__all__ = [
    "remove_vig",
    "calculate_fair_odds",
    "get_market_vig",
    "calculate_ev",
    "calculate_kelly_bet",
    "evaluate_opportunity",
    "LLMAnalyzer",
    "MatchupAnalysis",
    "analyze_matchup",
]
