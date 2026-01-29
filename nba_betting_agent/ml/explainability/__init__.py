"""SHAP-based model explainability for NBA Betting Agent.

This module provides tools for explaining ML model predictions using SHAP
(SHapley Additive exPlanations) values. These explanations help users
understand why the model predicts a certain win probability.

Key components:
    SHAPExplainer: Class for generating SHAP-based explanations
    explain_prediction: Convenience function for single predictions
    format_explanation: Human-readable explanation formatting
"""

from nba_betting_agent.ml.explainability.shap_explainer import (
    SHAPExplainer,
    explain_prediction,
    format_explanation,
)

__all__ = ["SHAPExplainer", "explain_prediction", "format_explanation"]
