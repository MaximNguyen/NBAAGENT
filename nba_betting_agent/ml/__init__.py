"""Machine Learning module for NBA Betting Agent.

This module provides ML-based probability estimation:
- Historical data collection (games and odds)
- Feature engineering for predictive modeling
- Model training and inference
- Probability calibration

Submodules:
    data: Historical data loading and schemas
"""

from nba_betting_agent.ml.data import schema, historical

__all__ = ["schema", "historical"]
