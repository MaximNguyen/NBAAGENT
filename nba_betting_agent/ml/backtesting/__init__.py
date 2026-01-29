"""Backtesting framework for validating betting model performance.

This module provides tools for simulating betting decisions over historical
data and measuring model ROI and calibration.

Main components:
- BacktestMetrics: Performance metrics dataclass
- BacktestEngine: Walk-forward backtesting simulation
- generate_report: Human-readable backtest reports
"""

from nba_betting_agent.ml.backtesting.metrics import (
    BacktestMetrics,
    calculate_roi,
    calculate_brier_score,
    calculate_calibration_error,
    calculate_clv,
)
from nba_betting_agent.ml.backtesting.engine import (
    BacktestEngine,
    BacktestResult,
    run_backtest,
)
from nba_betting_agent.ml.backtesting.report import (
    BacktestReport,
    generate_report,
    format_report,
)

__all__ = [
    # Metrics
    "BacktestMetrics",
    "calculate_roi",
    "calculate_brier_score",
    "calculate_calibration_error",
    "calculate_clv",
    # Engine
    "BacktestEngine",
    "BacktestResult",
    "run_backtest",
    # Report
    "BacktestReport",
    "generate_report",
    "format_report",
]
