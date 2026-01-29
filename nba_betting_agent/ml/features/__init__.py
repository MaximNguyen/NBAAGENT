"""Feature engineering module for ML probability models.

Provides:
- compute_team_features: Net rating, pace, form features
- compute_situational_features: Rest days, back-to-backs, schedule density
- FeaturePipeline: Orchestrates all feature computation
- create_training_features: Convenience function for full dataset
"""

from nba_betting_agent.ml.features.team_features import compute_team_features
from nba_betting_agent.ml.features.situational import compute_situational_features
from nba_betting_agent.ml.features.pipeline import FeaturePipeline, create_training_features

__all__ = [
    "compute_team_features",
    "compute_situational_features",
    "FeaturePipeline",
    "create_training_features",
]
