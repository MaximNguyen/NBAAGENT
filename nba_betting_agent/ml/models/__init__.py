"""ML models for NBA betting probability estimation.

This module provides trained models for predicting game outcomes:
- MoneylineModel: LightGBM-based win probability with Platt scaling calibration

Example:
    >>> from nba_betting_agent.ml.models import MoneylineModel
    >>> model = MoneylineModel()
    >>> model.fit(X_train, y_train)
    >>> probs = model.predict_proba(X_test)
"""

from nba_betting_agent.ml.models.base import BaseBettingModel
from nba_betting_agent.ml.models.moneyline_model import MoneylineModel

__all__ = ["BaseBettingModel", "MoneylineModel"]
