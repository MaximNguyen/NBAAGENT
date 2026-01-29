"""SHAP-based prediction explainer for betting models.

This module provides SHAP (SHapley Additive exPlanations) integration for
understanding why the model predicts certain win probabilities. SHAP values
show how each feature contributes to pushing the prediction above or below
the baseline.

Example:
    >>> from nba_betting_agent.ml.models import MoneylineModel
    >>> from nba_betting_agent.ml.explainability import SHAPExplainer
    >>>
    >>> model = MoneylineModel.load("models/moneyline_v1")
    >>> explainer = SHAPExplainer(model)
    >>>
    >>> # Explain a prediction
    >>> explanations = explainer.explain(X_sample, top_k=5)
    >>> print(explanations[0]['top_factors'])
    [{'feature': 'rest_advantage', 'impact': 0.032, 'direction': 'positive'}, ...]
"""

import logging
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from nba_betting_agent.ml.models.base import BaseBettingModel


log = logging.getLogger(__name__)


class SHAPExplainer:
    """SHAP TreeExplainer wrapper for betting model explanations.

    Uses SHAP's TreeExplainer optimized for tree-based models like LightGBM
    to efficiently compute feature contributions to predictions.

    Attributes:
        explainer: SHAP TreeExplainer instance
        base_value: Expected baseline probability (average prediction)

    Example:
        >>> explainer = SHAPExplainer(model)
        >>> results = explainer.explain(X, top_k=3)
        >>> for result in results:
        ...     print(f"Prediction: {result['prediction']:.1%}")
        ...     for factor in result['top_factors']:
        ...         print(f"  {factor['feature']}: {factor['impact']:+.1%}")
    """

    def __init__(self, model: "BaseBettingModel") -> None:
        """Initialize SHAP TreeExplainer for the model.

        Args:
            model: Trained model (must have .model attribute with LightGBM booster)

        Raises:
            ValueError: If model is not fitted (model.model is None)
        """
        import shap

        if model.model is None:
            raise ValueError(
                "Cannot create explainer for unfitted model. "
                "Call model.fit() first."
            )

        # Get the underlying LightGBM booster
        booster = model.model
        self.explainer = shap.TreeExplainer(booster)

        # Store base value (expected value / baseline probability)
        # For binary classification, this is the average log-odds or probability
        base = self.explainer.expected_value
        if isinstance(base, np.ndarray):
            base = float(base[0]) if len(base) > 0 else 0.5
        self.base_value = float(base)

    def explain(
        self,
        X: pd.DataFrame,
        feature_names: list[str] | None = None,
        top_k: int = 5,
    ) -> list[dict]:
        """Explain predictions for given samples.

        Computes SHAP values and identifies the most impactful features
        for each prediction.

        Args:
            X: Feature DataFrame (one or more samples)
            feature_names: Optional list of feature names (uses X.columns if None)
            top_k: Number of top factors to include (default: 5)

        Returns:
            List of dicts (one per sample):
            [
                {
                    'base_prob': 0.52,  # Expected baseline
                    'prediction': 0.65,  # Final prediction (base + contributions)
                    'top_factors': [
                        {'feature': 'rest_advantage', 'impact': 0.05, 'direction': 'positive'},
                        {'feature': 'net_rtg_diff', 'impact': 0.03, 'direction': 'positive'},
                        ...
                    ]
                }
            ]
        """
        try:
            # Use provided feature names or extract from DataFrame
            if feature_names is None:
                feature_names = list(X.columns)

            # Compute SHAP values
            shap_values = self.explainer.shap_values(X)

            # Handle different SHAP output formats
            if isinstance(shap_values, list):
                # Binary classification may return [class_0, class_1]
                shap_values = shap_values[1] if len(shap_values) > 1 else shap_values[0]

            # Ensure 2D array
            if shap_values.ndim == 1:
                shap_values = shap_values.reshape(1, -1)

            results = []
            for i in range(len(X)):
                sample_shap = shap_values[i]

                # Calculate prediction from base + SHAP contributions
                prediction = self.base_value + sum(sample_shap)

                # Get top-k factors by absolute impact
                abs_impacts = np.abs(sample_shap)
                top_indices = np.argsort(abs_impacts)[-top_k:][::-1]

                top_factors = []
                for idx in top_indices:
                    impact = float(sample_shap[idx])
                    if abs(impact) < 1e-6:
                        continue  # Skip negligible impacts

                    factor = {
                        "feature": feature_names[idx],
                        "impact": impact,
                        "direction": "positive" if impact > 0 else "negative",
                    }
                    top_factors.append(factor)

                results.append({
                    "base_prob": self.base_value,
                    "prediction": prediction,
                    "top_factors": top_factors,
                })

            return results

        except Exception as e:
            log.warning(
                "SHAP explanation failed: %s. Returning empty explanations.",
                str(e),
            )
            # Return empty explanations on failure
            return [
                {
                    "base_prob": self.base_value,
                    "prediction": self.base_value,
                    "top_factors": [],
                }
                for _ in range(len(X))
            ]


def explain_prediction(
    model: "BaseBettingModel",
    X_sample: pd.DataFrame,
    feature_names: list[str],
    top_k: int = 5,
) -> list[tuple[str, float, str]]:
    """Convenience function to explain a single prediction.

    Creates a temporary explainer and returns simplified output format.

    Args:
        model: Trained model with .model attribute
        X_sample: Feature DataFrame (typically single row)
        feature_names: List of feature column names
        top_k: Number of top factors to return

    Returns:
        List of tuples: [(feature_name, impact_pct, direction), ...]
        Impact is expressed as percentage points (e.g., 0.032 = 3.2%)

    Example:
        >>> factors = explain_prediction(model, X, features, top_k=3)
        >>> for name, impact, direction in factors:
        ...     print(f"{name}: {impact:+.1%} ({direction})")
        rest_advantage: +3.2% (positive)
        net_rtg_diff: +2.1% (positive)
        away_offensive_rating: -1.5% (negative)
    """
    if model.model is None:
        raise ValueError("Cannot explain predictions for unfitted model.")

    explainer = SHAPExplainer(model)
    results = explainer.explain(X_sample, feature_names, top_k)

    # Flatten to list of tuples for first sample
    if results and results[0]["top_factors"]:
        return [
            (f["feature"], f["impact"], f["direction"])
            for f in results[0]["top_factors"]
        ]

    return []


def format_explanation(factors: list[tuple[str, float, str]]) -> str:
    """Format explanation factors as human-readable string.

    Args:
        factors: List of (feature_name, impact, direction) tuples

    Returns:
        Formatted string like: "Key factors: Rest advantage +3.2%, Net rating diff +2.1%"

    Example:
        >>> factors = [('rest_advantage', 0.032, 'positive'), ('net_rtg_diff', -0.015, 'negative')]
        >>> format_explanation(factors)
        'Key factors: Rest advantage +3.2%, Net rating diff -1.5%'
    """
    if not factors:
        return "No significant factors identified."

    # Format each factor
    formatted_parts = []
    for feature_name, impact, _ in factors:
        # Convert feature name to human-readable format
        readable_name = feature_name.replace("_", " ").title()

        # Format impact as percentage with sign
        impact_pct = impact * 100
        sign = "+" if impact_pct >= 0 else ""
        formatted_parts.append(f"{readable_name} {sign}{impact_pct:.1f}%")

    return "Key factors: " + ", ".join(formatted_parts)
