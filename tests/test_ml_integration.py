"""Tests for ML integration: SHAP explainability, probability blending, and MLProbabilityEstimator.

These tests verify:
1. SHAPExplainer produces correct explanation structure
2. ProbabilityBlender combines model/market probs correctly
3. MLProbabilityEstimator integrates all components
"""

import os
import tempfile
from datetime import datetime
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest


# =============================================================================
# SHAPExplainer Tests
# =============================================================================


class TestSHAPExplainer:
    """Tests for SHAP-based prediction explanations."""

    def test_explainer_requires_fitted_model(self):
        """Test that SHAPExplainer raises error for unfitted model."""
        from nba_betting_agent.ml.explainability.shap_explainer import SHAPExplainer
        from nba_betting_agent.ml.models.moneyline_model import MoneylineModel

        model = MoneylineModel()  # Not fitted
        with pytest.raises(ValueError, match="unfitted model"):
            SHAPExplainer(model)

    def test_explain_returns_correct_structure(self):
        """Test that explain() returns expected dict structure."""
        from nba_betting_agent.ml.explainability.shap_explainer import SHAPExplainer
        from nba_betting_agent.ml.models.moneyline_model import MoneylineModel

        # Create and fit a small model
        model = MoneylineModel()
        X = pd.DataFrame({
            "feature_a": [0.1, 0.2, 0.3, 0.4, 0.5] * 10,
            "feature_b": [0.5, 0.4, 0.3, 0.2, 0.1] * 10,
            "feature_c": [0.3, 0.3, 0.3, 0.3, 0.3] * 10,
        })
        y = pd.Series([1, 0, 1, 0, 1] * 10)
        model.fit(X, y, num_boost_rounds=10)

        # Create explainer and explain
        explainer = SHAPExplainer(model)
        results = explainer.explain(X.iloc[:2], top_k=2)

        # Check structure
        assert len(results) == 2
        for result in results:
            assert "base_prob" in result
            assert "prediction" in result
            assert "top_factors" in result
            assert isinstance(result["top_factors"], list)

    def test_top_k_limits_factors(self):
        """Test that top_k parameter limits number of factors."""
        from nba_betting_agent.ml.explainability.shap_explainer import SHAPExplainer
        from nba_betting_agent.ml.models.moneyline_model import MoneylineModel

        # Create model with many features
        model = MoneylineModel()
        n_features = 10
        X = pd.DataFrame(
            np.random.randn(50, n_features),
            columns=[f"feat_{i}" for i in range(n_features)],
        )
        y = pd.Series([1, 0] * 25)
        model.fit(X, y, num_boost_rounds=10)

        explainer = SHAPExplainer(model)

        # Test different top_k values
        for top_k in [1, 3, 5]:
            results = explainer.explain(X.iloc[:1], top_k=top_k)
            # May have fewer if some impacts are negligible
            assert len(results[0]["top_factors"]) <= top_k

    def test_factors_have_required_keys(self):
        """Test that each factor has feature, impact, and direction."""
        from nba_betting_agent.ml.explainability.shap_explainer import SHAPExplainer
        from nba_betting_agent.ml.models.moneyline_model import MoneylineModel

        model = MoneylineModel()
        X = pd.DataFrame({
            "rest_advantage": np.random.randn(50),
            "net_rtg_diff": np.random.randn(50),
        })
        y = pd.Series([1, 0] * 25)
        model.fit(X, y, num_boost_rounds=10)

        explainer = SHAPExplainer(model)
        results = explainer.explain(X.iloc[:1], top_k=2)

        for factor in results[0]["top_factors"]:
            assert "feature" in factor
            assert "impact" in factor
            assert "direction" in factor
            assert factor["direction"] in ["positive", "negative"]


class TestExplainPrediction:
    """Tests for explain_prediction convenience function."""

    def test_returns_list_of_tuples(self):
        """Test that explain_prediction returns list of (name, impact, direction)."""
        from nba_betting_agent.ml.explainability.shap_explainer import explain_prediction
        from nba_betting_agent.ml.models.moneyline_model import MoneylineModel

        model = MoneylineModel()
        X = pd.DataFrame({
            "feature_a": np.random.randn(50),
            "feature_b": np.random.randn(50),
        })
        y = pd.Series([1, 0] * 25)
        model.fit(X, y, num_boost_rounds=10)

        factors = explain_prediction(model, X.iloc[:1], ["feature_a", "feature_b"], top_k=2)

        assert isinstance(factors, list)
        for item in factors:
            assert isinstance(item, tuple)
            assert len(item) == 3
            name, impact, direction = item
            assert isinstance(name, str)
            assert isinstance(impact, float)
            assert direction in ["positive", "negative"]


class TestFormatExplanation:
    """Tests for format_explanation helper function."""

    def test_formats_factors_correctly(self):
        """Test that factors are formatted as human-readable string."""
        from nba_betting_agent.ml.explainability.shap_explainer import format_explanation

        factors = [
            ("rest_advantage", 0.032, "positive"),
            ("net_rtg_diff", -0.015, "negative"),
        ]

        result = format_explanation(factors)

        assert "Key factors:" in result
        assert "Rest Advantage" in result
        assert "+3.2%" in result
        assert "-1.5%" in result

    def test_empty_factors_returns_message(self):
        """Test that empty factors list returns appropriate message."""
        from nba_betting_agent.ml.explainability.shap_explainer import format_explanation

        result = format_explanation([])
        assert "No significant factors" in result


# =============================================================================
# ProbabilityBlender Tests
# =============================================================================


class TestBlendProbabilities:
    """Tests for blend_probabilities function."""

    def test_simple_blend(self):
        """Test basic probability blending with default weight."""
        from nba_betting_agent.ml.blending.ensemble import blend_probabilities

        # 70% model (0.65) + 30% market (0.60) = 0.455 + 0.18 = 0.635
        result = blend_probabilities(0.65, 0.60, model_weight=0.7)
        assert abs(result - 0.635) < 0.001

    def test_blend_clamped_to_valid_range(self):
        """Test that result is clamped to [0.01, 0.99]."""
        from nba_betting_agent.ml.blending.ensemble import blend_probabilities

        # Test near 1.0
        result = blend_probabilities(1.0, 1.0)
        assert result <= 0.99

        # Test near 0.0
        result = blend_probabilities(0.0, 0.0)
        assert result >= 0.01

    def test_custom_model_weight(self):
        """Test blending with custom model weight."""
        from nba_betting_agent.ml.blending.ensemble import blend_probabilities

        # 50% model (0.70) + 50% market (0.50) = 0.35 + 0.25 = 0.60
        result = blend_probabilities(0.70, 0.50, model_weight=0.5)
        assert abs(result - 0.60) < 0.001

    def test_pure_model_weight(self):
        """Test with 100% model weight."""
        from nba_betting_agent.ml.blending.ensemble import blend_probabilities

        result = blend_probabilities(0.75, 0.50, model_weight=1.0)
        assert abs(result - 0.75) < 0.001

    def test_pure_market_weight(self):
        """Test with 0% model weight (100% market)."""
        from nba_betting_agent.ml.blending.ensemble import blend_probabilities

        result = blend_probabilities(0.75, 0.50, model_weight=0.0)
        assert abs(result - 0.50) < 0.001


class TestProbabilityBlender:
    """Tests for ProbabilityBlender class."""

    def test_blend_without_confidence(self):
        """Test blending without confidence adjustment."""
        from nba_betting_agent.ml.blending.ensemble import ProbabilityBlender

        blender = ProbabilityBlender(model_weight=0.7)
        blended, weight = blender.blend(0.65, 0.60)

        assert abs(blended - 0.635) < 0.001
        assert weight == 0.7

    def test_blend_with_narrow_confidence(self):
        """Test that narrow confidence doesn't reduce weight."""
        from nba_betting_agent.ml.blending.ensemble import ProbabilityBlender

        blender = ProbabilityBlender(model_weight=0.7, min_model_confidence=0.1)
        _, weight = blender.blend(0.65, 0.60, confidence_width=0.05)

        # Weight should be unchanged (0.05 < 0.1 threshold)
        assert weight == 0.7

    def test_blend_with_wide_confidence(self):
        """Test that wide confidence interval reduces weight."""
        from nba_betting_agent.ml.blending.ensemble import ProbabilityBlender

        blender = ProbabilityBlender(model_weight=0.7, min_model_confidence=0.1)
        _, weight = blender.blend(0.65, 0.60, confidence_width=0.25)

        # Weight should be reduced
        assert weight < 0.7

    def test_explain_blend_format(self):
        """Test explain_blend returns proper format."""
        from nba_betting_agent.ml.blending.ensemble import ProbabilityBlender

        blender = ProbabilityBlender()
        explanation = blender.explain_blend(0.65, 0.62, 0.641)

        assert "Model:" in explanation
        assert "65.0%" in explanation
        assert "+3.0%" in explanation  # Model is 3% higher than market
        assert "Market: 62.0%" in explanation
        assert "Blended:" in explanation


class TestGetModelWeightFromEnv:
    """Tests for get_model_weight_from_env function."""

    def test_default_value(self):
        """Test default value when env var not set."""
        from nba_betting_agent.ml.blending.ensemble import get_model_weight_from_env

        # Clear env var if set
        os.environ.pop("ML_MODEL_WEIGHT", None)

        result = get_model_weight_from_env()
        assert result == 0.7

    def test_reads_env_value(self):
        """Test reading value from environment."""
        from nba_betting_agent.ml.blending.ensemble import get_model_weight_from_env

        os.environ["ML_MODEL_WEIGHT"] = "0.8"
        try:
            result = get_model_weight_from_env()
            assert result == 0.8
        finally:
            os.environ.pop("ML_MODEL_WEIGHT", None)

    def test_clamps_invalid_values(self):
        """Test that out-of-range values are clamped."""
        from nba_betting_agent.ml.blending.ensemble import get_model_weight_from_env

        # Test > 1.0
        os.environ["ML_MODEL_WEIGHT"] = "1.5"
        try:
            result = get_model_weight_from_env()
            assert result == 1.0
        finally:
            os.environ.pop("ML_MODEL_WEIGHT", None)

        # Test < 0.0
        os.environ["ML_MODEL_WEIGHT"] = "-0.5"
        try:
            result = get_model_weight_from_env()
            assert result == 0.0
        finally:
            os.environ.pop("ML_MODEL_WEIGHT", None)


# =============================================================================
# MLProbabilityEstimator Tests
# =============================================================================


class TestMLProbabilityEstimator:
    """Tests for MLProbabilityEstimator integration class."""

    def test_raises_without_model(self):
        """Test that estimate_probability raises when no model loaded."""
        from datetime import date
        from nba_betting_agent.agents.analysis_agent.ml_probability import MLProbabilityEstimator

        estimator = MLProbabilityEstimator()

        with pytest.raises(ValueError, match="No model loaded"):
            estimator.estimate_probability(
                home_team="BOS",
                away_team="LAL",
                game_date=date(2026, 1, 30),
                historical_games=[],
            )

    def test_is_loaded_false_initially(self):
        """Test is_loaded returns False before model load."""
        from nba_betting_agent.agents.analysis_agent.ml_probability import MLProbabilityEstimator

        estimator = MLProbabilityEstimator()
        assert not estimator.is_loaded()

    def test_load_model_and_is_loaded(self):
        """Test loading a model sets is_loaded to True."""
        from nba_betting_agent.agents.analysis_agent.ml_probability import MLProbabilityEstimator
        from nba_betting_agent.ml.models.moneyline_model import MoneylineModel

        # Create and save a model
        model = MoneylineModel()
        X = pd.DataFrame({
            "home_offensive_rating": np.random.randn(50),
            "away_defensive_rating": np.random.randn(50),
        })
        y = pd.Series([1, 0] * 25)
        model.fit(X, y, num_boost_rounds=10)

        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = f"{tmpdir}/test_model"
            model.save(model_path)

            estimator = MLProbabilityEstimator()
            assert not estimator.is_loaded()

            estimator.load_model(model_path)
            assert estimator.is_loaded()

    def test_estimate_returns_all_fields(self):
        """Test estimate_probability returns all expected fields."""
        from datetime import date
        from nba_betting_agent.agents.analysis_agent.ml_probability import MLProbabilityEstimator
        from nba_betting_agent.ml.models.moneyline_model import MoneylineModel
        from nba_betting_agent.ml.data.schema import HistoricalGame

        # Create and save a model with real feature names from FeaturePipeline
        # These are the exact features computed by compute_team_features + compute_situational_features
        feature_names = [
            # From team_features.py
            "home_net_rtg_l10", "away_net_rtg_l10", "net_rtg_diff",
            "home_pace_l10", "away_pace_l10", "pace_diff",
            "home_win_pct_l10", "away_win_pct_l10", "form_diff",
            "home_team_home_record", "away_team_away_record",
            # From situational.py
            "home_rest_days", "away_rest_days", "rest_advantage",
            "home_b2b", "away_b2b", "b2b_disadvantage",
            "home_games_last_7", "away_games_last_7", "schedule_density_diff",
            "games_into_season", "season_pct",
        ]

        model = MoneylineModel()
        X = pd.DataFrame({
            name: np.random.randn(50) for name in feature_names
        })
        y = pd.Series([1, 0] * 25)
        model.fit(X, y, num_boost_rounds=10)

        # Create mock historical games
        games = [
            HistoricalGame(
                game_id=f"game_{i}",
                game_date=datetime(2026, 1, 1 + (i // 2)),  # Spread across days
                season="2025-26",
                home_team="BOS" if i % 2 == 0 else "LAL",
                away_team="LAL" if i % 2 == 0 else "BOS",
                home_score=100 + i,
                away_score=95 + i,
            )
            for i in range(20)
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = f"{tmpdir}/test_model"
            model.save(model_path)

            estimator = MLProbabilityEstimator(model_path=model_path)
            result = estimator.estimate_probability(
                home_team="BOS",
                away_team="LAL",
                game_date=date(2026, 1, 30),
                historical_games=games,
                market_prob=0.62,
            )

            # Check all fields present
            assert "model_prob" in result
            assert "market_prob" in result
            assert "blended_prob" in result
            assert "model_weight_used" in result
            assert "confidence_interval" in result
            assert "explanation" in result
            assert "top_factors" in result

            # Check types
            assert isinstance(result["model_prob"], float)
            assert result["market_prob"] == 0.62
            assert isinstance(result["blended_prob"], float)
            assert isinstance(result["model_weight_used"], float)
            assert isinstance(result["confidence_interval"], tuple)
            assert isinstance(result["explanation"], str)
            assert isinstance(result["top_factors"], list)

    def test_estimate_without_market_prob(self):
        """Test estimation without market probability (pure model mode)."""
        from datetime import date
        from nba_betting_agent.agents.analysis_agent.ml_probability import MLProbabilityEstimator
        from nba_betting_agent.ml.models.moneyline_model import MoneylineModel
        from nba_betting_agent.ml.data.schema import HistoricalGame

        # Create model with real feature names from FeaturePipeline
        feature_names = [
            # From team_features.py
            "home_net_rtg_l10", "away_net_rtg_l10", "net_rtg_diff",
            "home_pace_l10", "away_pace_l10", "pace_diff",
            "home_win_pct_l10", "away_win_pct_l10", "form_diff",
            "home_team_home_record", "away_team_away_record",
            # From situational.py
            "home_rest_days", "away_rest_days", "rest_advantage",
            "home_b2b", "away_b2b", "b2b_disadvantage",
            "home_games_last_7", "away_games_last_7", "schedule_density_diff",
            "games_into_season", "season_pct",
        ]

        model = MoneylineModel()
        X = pd.DataFrame({
            name: np.random.randn(50) for name in feature_names
        })
        y = pd.Series([1, 0] * 25)
        model.fit(X, y, num_boost_rounds=10)

        games = [
            HistoricalGame(
                game_id=f"game_{i}",
                game_date=datetime(2026, 1, 1 + (i // 2)),  # Spread across days
                season="2025-26",
                home_team="BOS" if i % 2 == 0 else "LAL",
                away_team="LAL" if i % 2 == 0 else "BOS",
                home_score=100,
                away_score=95,
            )
            for i in range(20)
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = f"{tmpdir}/test_model"
            model.save(model_path)

            estimator = MLProbabilityEstimator(model_path=model_path)
            result = estimator.estimate_probability(
                home_team="BOS",
                away_team="LAL",
                game_date=date(2026, 1, 30),
                historical_games=games,
                market_prob=None,  # No market probability
            )

            # Without market, blended == model
            assert result["market_prob"] is None
            assert result["model_weight_used"] == 1.0
            assert result["blended_prob"] == result["model_prob"]

    def test_model_weight_from_init(self):
        """Test that model_weight can be set at initialization."""
        from nba_betting_agent.agents.analysis_agent.ml_probability import MLProbabilityEstimator

        estimator = MLProbabilityEstimator(model_weight=0.5)
        assert estimator.blender.model_weight == 0.5
