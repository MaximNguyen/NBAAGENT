"""Machine Learning module for NBA Betting Agent.

This module provides ML-based probability estimation:
- Historical data collection (games and odds)
- Feature engineering for predictive modeling
- Model training and inference
- Probability calibration
- Model explainability (SHAP)
- Probability blending (model + market)
- Backtesting for model validation

Submodules:
    data: Historical data loading and schemas
    features: Feature engineering pipeline
    models: Betting probability models (MoneylineModel)
    training: Model training and validation infrastructure
    explainability: SHAP-based prediction explanations
    blending: Model-market probability ensemble
    backtesting: Model validation via historical simulation
"""

from nba_betting_agent.ml.data import schema, historical
from nba_betting_agent.ml import features, models, training, explainability, blending, backtesting

__all__ = [
    "schema",
    "historical",
    "features",
    "models",
    "training",
    "explainability",
    "blending",
    "backtesting",
]
