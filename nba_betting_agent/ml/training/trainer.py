"""Model training orchestration for NBA betting models.

ModelTrainer handles the full training workflow:
1. Loading/creating training features from historical games
2. Training models with configurable parameters
3. Running walk-forward validation
4. Saving/loading trained models

Example:
    >>> from nba_betting_agent.ml.training import ModelTrainer
    >>> from nba_betting_agent.ml.data.historical import load_historical_games
    >>>
    >>> games = load_historical_games(["2022-23", "2023-24"])
    >>> trainer = ModelTrainer()
    >>> model = trainer.train_from_games(games)
    >>> trainer.save_model(model, "moneyline_v1")
"""

from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from nba_betting_agent.ml.features.pipeline import FeaturePipeline
from nba_betting_agent.ml.models.base import BaseBettingModel
from nba_betting_agent.ml.models.moneyline_model import MoneylineModel
from nba_betting_agent.ml.training.validation import cross_validate

if TYPE_CHECKING:
    from nba_betting_agent.ml.data.schema import HistoricalGame


class ModelTrainer:
    """Orchestrates model training and validation workflow.

    Provides high-level methods for training models from raw game data,
    running cross-validation, and managing model persistence.

    Attributes:
        model_class: Model class to instantiate
        pipeline: Feature pipeline for data transformation
        model_dir: Directory for saved models

    Example:
        >>> trainer = ModelTrainer()
        >>> model = trainer.train_from_games(games)
        >>> results = trainer.validate(games)
        >>> print(f"Mean Brier: {results['mean_brier']:.4f}")
    """

    def __init__(
        self,
        model_class: type[BaseBettingModel] = MoneylineModel,
        feature_pipeline: FeaturePipeline | None = None,
        model_dir: str = ".models",
    ) -> None:
        """Initialize the trainer.

        Args:
            model_class: Model class to use (default: MoneylineModel)
            feature_pipeline: Pipeline for feature creation (created if None)
            model_dir: Directory for saving/loading models
        """
        self.model_class = model_class
        self.pipeline = feature_pipeline or FeaturePipeline()
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)

    def train_from_games(
        self,
        games: list["HistoricalGame"],
        model_params: dict | None = None,
        min_games_required: int = 5,
        num_boost_rounds: int = 100,
        calibration_frac: float = 0.2,
    ) -> BaseBettingModel:
        """Train a model from raw historical game data.

        Full training workflow:
        1. Create training features from games
        2. Instantiate model with parameters
        3. Fit model on feature data

        Args:
            games: List of historical games
            model_params: Parameters for model constructor
            min_games_required: Minimum games per team before including
            num_boost_rounds: Number of boosting iterations
            calibration_frac: Fraction of data for calibration

        Returns:
            Trained model instance

        Example:
            >>> games = load_historical_games(["2022-23", "2023-24"])
            >>> model = trainer.train_from_games(games, {"learning_rate": 0.1})
        """
        # Create training dataset
        df = self.pipeline.create_training_dataset(
            games, min_games_required=min_games_required
        )

        if len(df) == 0:
            raise ValueError(
                "No training samples created. Need more games or lower min_games_required."
            )

        # Identify feature columns
        feature_cols = self._get_feature_columns(df)

        # Instantiate and train model
        model = self.model_class(model_params)
        model.fit(
            df[feature_cols],
            df["home_win"],
            num_boost_rounds=num_boost_rounds,
            calibration_frac=calibration_frac,
        )

        return model

    def validate(
        self,
        games: list["HistoricalGame"],
        train_seasons: int = 3,
        test_seasons: int = 1,
        min_games_required: int = 5,
        model_params: dict | None = None,
    ) -> dict:
        """Run walk-forward validation on historical games.

        Trains models on sequential season windows and evaluates
        on held-out future seasons.

        Args:
            games: List of historical games (need 4+ seasons for default params)
            train_seasons: Number of seasons to train on per fold
            test_seasons: Number of seasons to test on per fold
            min_games_required: Minimum games per team before including
            model_params: Parameters for model constructor

        Returns:
            Dictionary with:
            - fold_results: List of metric dicts per fold
            - mean_accuracy: Average accuracy across folds
            - mean_brier: Average Brier score across folds
            - mean_log_loss: Average log loss across folds
            - mean_roc_auc: Average AUC across folds
            - mean_calibration_error: Average calibration error

        Example:
            >>> results = trainer.validate(games)
            >>> print(f"Mean Brier: {results['mean_brier']:.4f}")
        """
        # Create training dataset
        df = self.pipeline.create_training_dataset(
            games, min_games_required=min_games_required
        )

        if len(df) == 0:
            raise ValueError(
                "No training samples created. Need more games or lower min_games_required."
            )

        # Add season column if not present (needed for walk-forward split)
        if "season" not in df.columns:
            df = self._add_season_column(df)

        # Identify feature columns
        feature_cols = self._get_feature_columns(df)

        # Run cross-validation
        fold_results = cross_validate(
            model_class=self.model_class,
            df=df,
            feature_cols=feature_cols,
            target_col="home_win",
            train_seasons=train_seasons,
            test_seasons=test_seasons,
            model_params=model_params,
        )

        # Aggregate results
        return {
            "fold_results": fold_results,
            "mean_accuracy": np.mean([r["accuracy"] for r in fold_results]),
            "mean_brier": np.mean([r["brier_score"] for r in fold_results]),
            "mean_log_loss": np.mean([r["log_loss"] for r in fold_results]),
            "mean_roc_auc": np.mean([r["roc_auc"] for r in fold_results]),
            "mean_calibration_error": np.mean(
                [r["calibration_error"] for r in fold_results]
            ),
        }

    def save_model(self, model: BaseBettingModel, name: str = "moneyline") -> Path:
        """Save a trained model.

        Args:
            model: Trained model to save
            name: Model name (becomes filename prefix)

        Returns:
            Path where model was saved

        Example:
            >>> model = trainer.train_from_games(games)
            >>> path = trainer.save_model(model, "moneyline_v2")
            >>> print(f"Saved to: {path}")
        """
        model_path = self.model_dir / name
        model.save(str(model_path))
        return model_path

    def load_model(self, name: str = "moneyline") -> BaseBettingModel:
        """Load a previously saved model.

        Args:
            name: Model name (filename prefix used in save_model)

        Returns:
            Loaded model instance

        Example:
            >>> model = trainer.load_model("moneyline_v2")
            >>> probs = model.predict_proba(X)
        """
        model_path = self.model_dir / name
        return self.model_class.load(str(model_path))

    def _get_feature_columns(self, df) -> list[str]:
        """Extract feature column names from DataFrame.

        Excludes metadata and target columns.
        """
        exclude_cols = {
            "game_id",
            "game_date",
            "home_team",
            "away_team",
            "home_win",
            "season",
        }
        return [c for c in df.columns if c not in exclude_cols]

    def _add_season_column(self, df):
        """Add season column based on game dates."""
        import pandas as pd

        df = df.copy()
        dates = pd.to_datetime(df["game_date"])

        def get_season(dt):
            if dt.month >= 10:
                start_year = dt.year
            else:
                start_year = dt.year - 1
            end_year = start_year + 1
            return f"{start_year}-{str(end_year)[2:]}"

        df["season"] = dates.apply(get_season)
        return df
