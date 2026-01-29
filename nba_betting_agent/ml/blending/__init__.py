"""Probability blending for combining ML model predictions with market odds.

This module provides tools for blending model-generated probabilities with
market-implied probabilities. The rationale is that markets are efficient
but not perfect, and a calibrated ML model can identify edges.

Key components:
    blend_probabilities: Simple weighted average blending
    ProbabilityBlender: Full-featured blender with confidence adjustment
    get_model_weight_from_env: Environment-based configuration
"""

from nba_betting_agent.ml.blending.ensemble import (
    blend_probabilities,
    ProbabilityBlender,
    get_model_weight_from_env,
)

__all__ = ["blend_probabilities", "ProbabilityBlender", "get_model_weight_from_env"]
