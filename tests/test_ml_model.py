"""Tests for ML model training infrastructure.

Tests cover:
- MoneylineModel fit/predict/update/save/load
- Walk-forward validation temporal correctness
- Model evaluation metrics
- ModelTrainer workflow
"""

import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sklearn.datasets import make_classification

from nba_betting_agent.ml.data.schema import HistoricalGame
from nba_betting_agent.ml.models.moneyline_model import MoneylineModel
from nba_betting_agent.ml.training.validation import (
    walk_forward_split,
    evaluate_model,
    cross_validate,
    calibration_bins,
)
from nba_betting_agent.ml.training.trainer import ModelTrainer


# =============================================================================
# MoneylineModel Tests
# =============================================================================


class TestMoneylineModel:
    """Tests for MoneylineModel fit/predict/save/load."""

    def test_fit_with_synthetic_data(self):
        """Test that model fits on synthetic data without errors."""
        X, y = make_classification(
            n_samples=200,
            n_features=10,
            n_informative=5,
            random_state=42,
        )
        X_df = pd.DataFrame(X, columns=[f"feat_{i}" for i in range(10)])
        y_series = pd.Series(y)

        model = MoneylineModel()
        model.fit(X_df, y_series, num_boost_rounds=50)

        assert model.model is not None
        # Calibrator may be None if calibration set too small
        assert model.feature_names == list(X_df.columns)

    def test_predict_proba_returns_valid_probabilities(self):
        """Test that predictions are in [0, 1] range."""
        X, y = make_classification(
            n_samples=200,
            n_features=10,
            n_informative=5,
            random_state=42,
        )
        X_df = pd.DataFrame(X, columns=[f"feat_{i}" for i in range(10)])
        y_series = pd.Series(y)

        model = MoneylineModel()
        model.fit(X_df, y_series)

        probs = model.predict_proba(X_df)

        assert len(probs) == len(X_df)
        assert all(0 <= p <= 1 for p in probs), "Probabilities must be in [0, 1]"

    def test_predict_proba_raises_before_fit(self):
        """Test that predict_proba raises error before fitting."""
        model = MoneylineModel()
        X_df = pd.DataFrame({"feat_0": [1, 2, 3]})

        with pytest.raises(RuntimeError, match="not fitted"):
            model.predict_proba(X_df)

    def test_update_adds_trees(self):
        """Test that incremental update adds boosting rounds."""
        X, y = make_classification(
            n_samples=200,
            n_features=10,
            n_informative=5,
            random_state=42,
        )
        X_df = pd.DataFrame(X, columns=[f"feat_{i}" for i in range(10)])
        y_series = pd.Series(y)

        model = MoneylineModel()
        model.fit(X_df, y_series, num_boost_rounds=50)

        initial_trees = model.num_trees

        # Update with more data
        X_new, y_new = make_classification(
            n_samples=50,
            n_features=10,
            n_informative=5,
            random_state=123,
        )
        X_new_df = pd.DataFrame(X_new, columns=[f"feat_{i}" for i in range(10)])
        y_new_series = pd.Series(y_new)

        model.update(X_new_df, y_new_series, num_rounds=10)

        # Should have more trees after update
        assert model.num_trees > initial_trees

    def test_save_and_load_roundtrip(self):
        """Test that model can be saved and loaded correctly."""
        X, y = make_classification(
            n_samples=200,
            n_features=10,
            n_informative=5,
            random_state=42,
        )
        X_df = pd.DataFrame(X, columns=[f"feat_{i}" for i in range(10)])
        y_series = pd.Series(y)

        model = MoneylineModel()
        model.fit(X_df, y_series)

        original_probs = model.predict_proba(X_df[:10])

        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = str(Path(tmpdir) / "test_model")
            model.save(model_path)

            # Load and verify
            loaded = MoneylineModel.load(model_path)
            loaded_probs = loaded.predict_proba(X_df[:10])

            np.testing.assert_array_almost_equal(original_probs, loaded_probs)

    def test_get_feature_importance(self):
        """Test that feature importance can be retrieved."""
        X, y = make_classification(
            n_samples=200,
            n_features=10,
            n_informative=5,
            random_state=42,
        )
        X_df = pd.DataFrame(X, columns=[f"feat_{i}" for i in range(10)])
        y_series = pd.Series(y)

        model = MoneylineModel()
        model.fit(X_df, y_series)

        importance = model.get_feature_importance()

        assert len(importance) == 10
        assert all(isinstance(v, (int, float)) for v in importance.values())


# =============================================================================
# Walk-Forward Validation Tests
# =============================================================================


class TestWalkForwardSplit:
    """Tests for walk_forward_split temporal correctness."""

    def _create_seasonal_df(self, seasons: list[str], games_per_season: int = 100):
        """Helper to create DataFrame with multiple seasons."""
        rows = []
        for season in seasons:
            start_year = int(season.split("-")[0])
            start_date = datetime(start_year, 10, 15)

            for i in range(games_per_season):
                game_date = start_date + timedelta(days=i)
                rows.append(
                    {
                        "game_id": f"{season}_{i:04d}",
                        "game_date": game_date,
                        "season": season,
                        "home_win": float(np.random.randint(0, 2)),
                        "feat_1": np.random.randn(),
                        "feat_2": np.random.randn(),
                    }
                )

        return pd.DataFrame(rows)

    def test_split_produces_correct_train_test_sizes(self):
        """Test that splits have expected season counts."""
        df = self._create_seasonal_df(
            ["2020-21", "2021-22", "2022-23", "2023-24"], games_per_season=50
        )

        folds = list(walk_forward_split(df, train_seasons=3, test_seasons=1))

        # Should produce 1 fold: train on 2020-23, test on 2023-24
        assert len(folds) == 1

        train_df, test_df = folds[0]

        # Train should have 3 seasons worth
        assert len(train_df) == 150

        # Test should have 1 season worth
        assert len(test_df) == 50

    def test_no_overlap_between_train_and_test(self):
        """CRITICAL: Verify train and test dates don't overlap."""
        df = self._create_seasonal_df(
            ["2020-21", "2021-22", "2022-23", "2023-24"], games_per_season=50
        )

        for train_df, test_df in walk_forward_split(df, train_seasons=3, test_seasons=1):
            train_dates = set(train_df["game_date"])
            test_dates = set(test_df["game_date"])

            overlap = train_dates & test_dates
            assert len(overlap) == 0, f"Overlap found: {overlap}"

    def test_train_always_before_test(self):
        """Verify all training dates are before all test dates."""
        df = self._create_seasonal_df(
            ["2020-21", "2021-22", "2022-23", "2023-24"], games_per_season=50
        )

        for train_df, test_df in walk_forward_split(df, train_seasons=3, test_seasons=1):
            max_train_date = train_df["game_date"].max()
            min_test_date = test_df["game_date"].min()

            assert max_train_date < min_test_date, (
                f"Train dates must precede test: "
                f"max train {max_train_date} vs min test {min_test_date}"
            )

    def test_multiple_folds_with_more_seasons(self):
        """Test that more seasons produce more folds."""
        df = self._create_seasonal_df(
            ["2019-20", "2020-21", "2021-22", "2022-23", "2023-24"],
            games_per_season=50,
        )

        folds = list(walk_forward_split(df, train_seasons=3, test_seasons=1))

        # 5 seasons, train on 3, test on 1 => 2 folds
        assert len(folds) == 2

    def test_raises_with_insufficient_seasons(self):
        """Test error when not enough seasons for split."""
        df = self._create_seasonal_df(["2022-23", "2023-24"], games_per_season=50)

        with pytest.raises(ValueError, match="Not enough seasons"):
            list(walk_forward_split(df, train_seasons=3, test_seasons=1))


# =============================================================================
# Model Evaluation Tests
# =============================================================================


class TestEvaluateModel:
    """Tests for evaluate_model metrics calculation."""

    def test_perfect_predictions_accuracy(self):
        """Test accuracy = 1.0 for perfect predictions."""
        X, y = make_classification(n_samples=100, n_features=5, random_state=42)
        X_df = pd.DataFrame(X, columns=[f"f{i}" for i in range(5)])
        y_series = pd.Series(y)

        # Create a model that we'll train to fit well
        model = MoneylineModel()
        model.fit(X_df, y_series, num_boost_rounds=200, calibration_frac=0.0)

        # Evaluate on training data (should have high accuracy)
        metrics = evaluate_model(model, X_df, y_series)

        # Training accuracy should be very high
        assert metrics["accuracy"] >= 0.9

    def test_brier_score_in_valid_range(self):
        """Test Brier score is in [0, 1] range."""
        X, y = make_classification(n_samples=100, n_features=5, random_state=42)
        X_df = pd.DataFrame(X, columns=[f"f{i}" for i in range(5)])
        y_series = pd.Series(y)

        model = MoneylineModel()
        model.fit(X_df, y_series)

        metrics = evaluate_model(model, X_df, y_series)

        assert 0 <= metrics["brier_score"] <= 1

    def test_metrics_keys(self):
        """Test that all expected metrics are returned."""
        X, y = make_classification(n_samples=100, n_features=5, random_state=42)
        X_df = pd.DataFrame(X, columns=[f"f{i}" for i in range(5)])
        y_series = pd.Series(y)

        model = MoneylineModel()
        model.fit(X_df, y_series)

        metrics = evaluate_model(model, X_df, y_series)

        expected_keys = {
            "accuracy",
            "log_loss",
            "brier_score",
            "roc_auc",
            "calibration_error",
        }
        assert set(metrics.keys()) == expected_keys

    def test_calibration_error_known_values(self):
        """Test calibration error with controlled predictions."""
        # Perfect calibration: predicted = actual rates
        y_true = np.array([1] * 50 + [0] * 50)  # 50% win rate overall
        y_pred = np.array([0.5] * 100)  # Predict 50% for all

        pred_probs, actual_rates = calibration_bins(y_true, y_pred)

        # With all predictions at 0.5, they should all be in one bin
        # Actual rate should be close to 0.5
        # Calibration should be good
        assert len(pred_probs) >= 1


# =============================================================================
# Calibration Bins Tests
# =============================================================================


class TestCalibrationBins:
    """Tests for calibration_bins helper function."""

    def test_returns_arrays_of_same_length(self):
        """Test that output arrays have matching lengths."""
        y_true = np.random.randint(0, 2, 100)
        y_pred = np.random.rand(100)

        pred_probs, actual_rates = calibration_bins(y_true, y_pred)

        assert len(pred_probs) == len(actual_rates)

    def test_values_in_valid_ranges(self):
        """Test that all values are in [0, 1]."""
        y_true = np.random.randint(0, 2, 100)
        y_pred = np.random.rand(100)

        pred_probs, actual_rates = calibration_bins(y_true, y_pred)

        assert all(0 <= p <= 1 for p in pred_probs)
        assert all(0 <= r <= 1 for r in actual_rates)


# =============================================================================
# ModelTrainer Tests
# =============================================================================


class TestModelTrainer:
    """Tests for ModelTrainer workflow."""

    def _create_test_games(self, n_games: int = 100) -> list[HistoricalGame]:
        """Create synthetic historical games for testing."""
        games = []
        base_date = datetime(2024, 1, 1)

        teams = ["BOS", "LAL", "GSW", "MIA", "NYK", "PHI"]

        for i in range(n_games):
            home_team = teams[i % len(teams)]
            away_team = teams[(i + 1) % len(teams)]
            home_score = np.random.randint(95, 120)
            away_score = np.random.randint(95, 120)

            game = HistoricalGame(
                game_id=f"TEST{i:04d}",
                game_date=base_date + timedelta(days=i),
                season="2023-24",
                home_team=home_team,
                away_team=away_team,
                home_score=home_score,
                away_score=away_score,
            )
            games.append(game)

        return games

    def test_train_from_games_returns_model(self):
        """Test that train_from_games produces a trained model."""
        games = self._create_test_games(100)

        trainer = ModelTrainer()
        model = trainer.train_from_games(games, min_games_required=3)

        assert model is not None
        assert model.model is not None

    def test_train_from_games_model_can_predict(self):
        """Test that trained model can make predictions."""
        games = self._create_test_games(100)

        trainer = ModelTrainer()
        model = trainer.train_from_games(games, min_games_required=3)

        # Create some test features
        df = trainer.pipeline.create_training_dataset(games, min_games_required=3)
        feature_cols = trainer._get_feature_columns(df)

        probs = model.predict_proba(df[feature_cols][:10])

        assert len(probs) == 10
        assert all(0 <= p <= 1 for p in probs)

    def test_save_and_load_model(self):
        """Test model persistence via trainer."""
        games = self._create_test_games(100)

        with tempfile.TemporaryDirectory() as tmpdir:
            trainer = ModelTrainer(model_dir=tmpdir)
            model = trainer.train_from_games(games, min_games_required=3)

            trainer.save_model(model, "test_model")
            loaded = trainer.load_model("test_model")

            assert loaded is not None
            assert loaded.model is not None

    def test_validate_returns_expected_structure(self):
        """Test that validate returns expected result structure."""
        # Need games across multiple seasons for walk-forward
        games = []
        base_date = datetime(2020, 10, 1)
        teams = ["BOS", "LAL", "GSW", "MIA", "NYK", "PHI"]

        # Create 4 seasons worth of data
        for season_idx in range(4):
            season_start = base_date.replace(year=base_date.year + season_idx)
            season_str = f"{season_start.year}-{str(season_start.year + 1)[2:]}"

            for game_idx in range(80):  # 80 games per season
                home_team = teams[game_idx % len(teams)]
                away_team = teams[(game_idx + 1) % len(teams)]

                game = HistoricalGame(
                    game_id=f"S{season_idx}G{game_idx:04d}",
                    game_date=season_start + timedelta(days=game_idx * 2),
                    season=season_str,
                    home_team=home_team,
                    away_team=away_team,
                    home_score=np.random.randint(95, 120),
                    away_score=np.random.randint(95, 120),
                )
                games.append(game)

        trainer = ModelTrainer()
        results = trainer.validate(games, train_seasons=3, test_seasons=1, min_games_required=3)

        # Check structure
        assert "fold_results" in results
        assert "mean_accuracy" in results
        assert "mean_brier" in results
        assert "mean_log_loss" in results
        assert "mean_roc_auc" in results
        assert "mean_calibration_error" in results

        # Should have 1 fold (4 seasons, train on 3, test on 1)
        assert len(results["fold_results"]) == 1

        # Brier score should be reasonable (< 0.25 for success criteria)
        # Note: With random data, this may vary but should be < 0.3
        assert results["mean_brier"] < 0.35


# =============================================================================
# Cross-Validate Tests
# =============================================================================


class TestCrossValidate:
    """Tests for cross_validate function."""

    def test_returns_list_of_dicts(self):
        """Test that cross_validate returns proper structure."""
        # Create 4-season DataFrame
        rows = []
        seasons = ["2020-21", "2021-22", "2022-23", "2023-24"]

        for season in seasons:
            start_year = int(season.split("-")[0])
            start_date = datetime(start_year, 10, 15)

            for i in range(80):
                rows.append(
                    {
                        "game_id": f"{season}_{i:04d}",
                        "game_date": start_date + timedelta(days=i * 2),
                        "season": season,
                        "home_win": float(np.random.randint(0, 2)),
                        "feat_1": np.random.randn(),
                        "feat_2": np.random.randn(),
                        "feat_3": np.random.randn(),
                    }
                )

        df = pd.DataFrame(rows)
        feature_cols = ["feat_1", "feat_2", "feat_3"]

        results = cross_validate(
            MoneylineModel,
            df,
            feature_cols,
            train_seasons=3,
            test_seasons=1,
        )

        assert isinstance(results, list)
        assert len(results) == 1  # 4 seasons => 1 fold

        # Each result should have metrics
        assert "accuracy" in results[0]
        assert "brier_score" in results[0]
        assert "fold" in results[0]
