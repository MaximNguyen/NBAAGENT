"""Analysis agent for calculating expected value and identifying +EV betting opportunities.

This module provides the mathematical foundation for bet analysis:
- Vig removal to calculate fair odds
- Expected value calculations
- Kelly criterion bet sizing
- Probability calibration (Platt scaling)
- Sharp/soft book comparison
- Reverse line movement detection
- CLV tracking
- LLM-powered qualitative matchup analysis
"""

from nba_betting_agent.agents.analysis_agent.agent import (
    analyze_bets,
    analysis_agent_impl,
    AnalysisResult,
    BettingOpportunity,
)
from nba_betting_agent.agents.analysis_agent.calibration import (
    ProbabilityCalibrator,
    calibrate_probability,
)
from nba_betting_agent.agents.analysis_agent.clv_tracker import (
    calculate_clv,
    CLVTracker,
)
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
from nba_betting_agent.agents.analysis_agent.rlm_detector import detect_rlm, RLMSignal
from nba_betting_agent.agents.analysis_agent.sharp_comparison import (
    find_soft_book_edges,
    compare_sharp_soft,
    SHARP_BOOKS,
)
from nba_betting_agent.agents.analysis_agent.vig_removal import (
    calculate_fair_odds,
    get_market_vig,
    remove_vig,
)

__all__ = [
    # Main agent
    "analyze_bets",
    "analysis_agent_impl",
    "AnalysisResult",
    "BettingOpportunity",
    # Vig removal
    "remove_vig",
    "calculate_fair_odds",
    "get_market_vig",
    # EV calculation
    "calculate_ev",
    "calculate_kelly_bet",
    "evaluate_opportunity",
    # Calibration
    "ProbabilityCalibrator",
    "calibrate_probability",
    # Sharp comparison
    "find_soft_book_edges",
    "compare_sharp_soft",
    "SHARP_BOOKS",
    # RLM detection
    "detect_rlm",
    "RLMSignal",
    # CLV tracking
    "calculate_clv",
    "CLVTracker",
    # LLM analysis
    "LLMAnalyzer",
    "MatchupAnalysis",
    "analyze_matchup",
]
