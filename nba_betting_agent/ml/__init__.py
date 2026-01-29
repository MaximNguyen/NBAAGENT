"""Machine Learning module for NBA Betting Agent.

This module provides ML-based probability estimation:
- Historical data collection (games and odds)
- Feature engineering for predictive modeling
- Model training and inference
- Probability calibration

Submodules:
    data: Historical data loading and schemas
    features: Feature engineering pipeline
    models: Betting probability models (MoneylineModel)
    training: Model training and validation infrastructure
"""

from nba_betting_agent.ml.data import schema, historical
from nba_betting_agent.ml import features, models, training

__all__ = ["schema", "historical", "features", "models", "training"]
