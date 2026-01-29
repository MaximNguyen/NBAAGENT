"""ML-based probability estimation for the Analysis Agent.

This module provides the MLProbabilityEstimator class, which integrates the
ML model, feature pipeline, SHAP explainer, and probability blender into a
single interface for the Analysis Agent.

Example:
    >>> from nba_betting_agent.agents.analysis_agent.ml_probability import MLProbabilityEstimator
    >>>
    >>> # Initialize with a trained model
    >>> estimator = MLProbabilityEstimator(model_path="models/moneyline_v1")
    >>>
    >>> # Estimate probability for a game
    >>> result = estimator.estimate_probability(
    ...     home_team="BOS",
    ...     away_team="LAL",
    ...     game_date=date(2026, 1, 30),
    ...     historical_games=games,
    ...     market_prob=0.62,
    ... )
    >>> print(f"Model: {result['model_prob']:.1%}, Blended: {result['blended_prob']:.1%}")
    >>> print(result['explanation'])
"""

from datetime import date, datetime
from typing import TYPE_CHECKING

import pandas as pd

from nba_betting_agent.ml.models.moneyline_model import MoneylineModel
from nba_betting_agent.ml.features.pipeline import FeaturePipeline
from nba_betting_agent.ml.explainability.shap_explainer import (
    SHAPExplainer,
    explain_prediction,
    format_explanation,
)
from nba_betting_agent.ml.blending.ensemble import (
    ProbabilityBlender,
    get_model_weight_from_env,
)

if TYPE_CHECKING:
    from nba_betting_agent.ml.data.schema import HistoricalGame


class MLProbabilityEstimator:
    """Generates ML-based probability estimates for betting analysis.

    Integrates:
    - MoneylineModel for win probability prediction
    - FeaturePipeline for real-time feature computation
    - SHAPExplainer for prediction explanations
    - ProbabilityBlender for model-market combination

    This class serves as the bridge between the ML module and the
    Analysis Agent, providing a clean interface for probability estimation.

    Attributes:
        model: Trained MoneylineModel (None until load_model called)
        pipeline: FeaturePipeline for feature computation
        blender: ProbabilityBlender for combining model/market probs
        explainer: SHAPExplainer for prediction explanations (None until model loaded)

    Example:
        >>> estimator = MLProbabilityEstimator(model_path="models/moneyline_v1")
        >>> result = estimator.estimate_probability(
        ...     home_team="BOS",
        ...     away_team="LAL",
        ...     game_date=date(2026, 1, 30),
        ...     historical_games=games,
        ...     market_prob=0.62,
        ... )
        >>> print(f"Model predicts: {result['model_prob']:.1%}")
        >>> print(result['explanation'])
    """

    def __init__(
        self,
        model_path: str | None = None,
        model_weight: float | None = None,
    ) -> None:
        """Initialize the ML probability estimator.

        Args:
            model_path: Path to trained model (optional, can load later)
            model_weight: Weight for model in blending (default from env or 0.7)
        """
        self.model: MoneylineModel | None = None
        self.pipeline = FeaturePipeline()
        self.explainer: SHAPExplainer | None = None

        # Get model weight from env if not specified
        if model_weight is None:
            model_weight = get_model_weight_from_env()
        self.blender = ProbabilityBlender(model_weight)

        if model_path:
            self.load_model(model_path)

    def load_model(self, path: str) -> None:
        """Load trained model from disk.

        Also initializes the SHAP explainer for the loaded model.

        Args:
            path: Base path to model files (without extension)

        Raises:
            FileNotFoundError: If model files don't exist
        """
        self.model = MoneylineModel.load(path)
        self.explainer = SHAPExplainer(self.model)

    def estimate_probability(
        self,
        home_team: str,
        away_team: str,
        game_date: date,
        historical_games: list["HistoricalGame"],
        market_prob: float | None = None,
    ) -> dict:
        """Generate ML probability estimate for a game.

        Computes features from historical games, generates model prediction,
        explains the prediction via SHAP, and optionally blends with market.

        Args:
            home_team: Home team abbreviation (e.g., "BOS")
            away_team: Away team abbreviation (e.g., "LAL")
            game_date: Date of the game
            historical_games: List of HistoricalGame objects for feature computation
            market_prob: Market-implied probability (optional, for blending)

        Returns:
            Dict with keys:
            - model_prob: ML model's estimated probability (float)
            - market_prob: Market probability if provided (float or None)
            - blended_prob: Blended probability (float)
            - model_weight_used: Effective weight used in blending (float)
            - confidence_interval: Tuple of (lower, upper) bounds (placeholder)
            - explanation: Human-readable explanation string
            - top_factors: List of (feature_name, impact, direction) tuples

        Raises:
            ValueError: If no model is loaded
        """
        if self.model is None:
            raise ValueError("No model loaded. Call load_model() first.")

        # Create a stub HistoricalGame for feature computation
        # The game_date is converted to datetime for compatibility
        from nba_betting_agent.ml.data.schema import HistoricalGame as HG

        target_datetime = datetime.combine(game_date, datetime.min.time())

        # Create a stub game (scores don't matter for prediction features)
        target_game = HG(
            game_id=f"prediction_{home_team}_{away_team}_{game_date}",
            game_date=target_datetime,
            season="2025-26",
            home_team=home_team,
            away_team=away_team,
            home_score=0,  # Placeholder
            away_score=0,  # Placeholder
        )

        # Compute features using historical games
        features = self.pipeline.create_features(historical_games, target_game)
        X = pd.DataFrame([features])

        # Get model prediction
        model_prob = float(self.model.predict_proba(X)[0])

        # Get explanation
        feature_names = list(features.keys())
        top_factors = explain_prediction(self.model, X, feature_names, top_k=5)
        explanation = format_explanation(top_factors)

        # Blend with market if available
        if market_prob is not None:
            blended, weight_used = self.blender.blend(model_prob, market_prob)
        else:
            blended = model_prob
            weight_used = 1.0

        # Placeholder confidence interval
        # In production, this would come from model calibration or bootstrap
        ci_width = 0.10
        confidence_interval = (
            max(0.0, model_prob - ci_width / 2),
            min(1.0, model_prob + ci_width / 2),
        )

        return {
            "model_prob": model_prob,
            "market_prob": market_prob,
            "blended_prob": blended,
            "model_weight_used": weight_used,
            "confidence_interval": confidence_interval,
            "explanation": explanation,
            "top_factors": top_factors,
        }

    def is_loaded(self) -> bool:
        """Check if a model is currently loaded.

        Returns:
            True if model is loaded and ready for prediction
        """
        return self.model is not None
