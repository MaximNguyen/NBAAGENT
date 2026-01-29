"""ML training infrastructure for NBA betting models.

This module provides model training and validation utilities:
- Walk-forward cross-validation for temporal data
- Model evaluation metrics (accuracy, Brier, calibration)
- ModelTrainer for orchestrating training workflow

Example:
    >>> from nba_betting_agent.ml.training import ModelTrainer
    >>> trainer = ModelTrainer()
    >>> model = trainer.train_from_games(games)
    >>> results = trainer.validate(games)
"""

from nba_betting_agent.ml.training.validation import (
    walk_forward_split,
    evaluate_model,
    cross_validate,
    calibration_bins,
)
from nba_betting_agent.ml.training.trainer import ModelTrainer

__all__ = [
    "walk_forward_split",
    "evaluate_model",
    "cross_validate",
    "calibration_bins",
    "ModelTrainer",
]
