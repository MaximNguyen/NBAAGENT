"""LightGBM-based moneyline win probability model with Platt scaling calibration.

This model predicts home team win probability using gradient boosted trees
with calibrated probability output via Platt scaling (sigmoid calibration).

Key features:
- LightGBM for fast, accurate predictions
- Platt scaling for calibrated probabilities
- Incremental learning support for updating with new games
- Persistence via .lgb model file + .calibrator pickle

Example:
    >>> from nba_betting_agent.ml.models import MoneylineModel
    >>> import pandas as pd
    >>>
    >>> # Training
    >>> model = MoneylineModel()
    >>> model.fit(X_train, y_train)
    >>>
    >>> # Prediction (calibrated probabilities)
    >>> probs = model.predict_proba(X_test)
    >>>
    >>> # Incremental update with new games
    >>> model.update(X_new, y_new, num_rounds=10)
    >>>
    >>> # Persistence
    >>> model.save("models/moneyline")
    >>> loaded = MoneylineModel.load("models/moneyline")
"""

from pathlib import Path
from typing import Any

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from nba_betting_agent.ml.models.base import BaseBettingModel


# Default LightGBM parameters optimized for NBA betting
DEFAULT_PARAMS: dict[str, Any] = {
    "objective": "binary",
    "metric": "binary_logloss",
    "boosting_type": "gbdt",
    "num_leaves": 31,
    "learning_rate": 0.05,
    "feature_fraction": 0.8,
    "bagging_fraction": 0.8,
    "bagging_freq": 5,
    "lambda_l1": 0.1,
    "lambda_l2": 0.1,
    "verbose": -1,
    "seed": 42,
}


class MoneylineModel(BaseBettingModel):
    """LightGBM win probability model with Platt scaling calibration.

    This model combines LightGBM's powerful gradient boosting with
    Platt scaling to produce well-calibrated probability estimates
    suitable for betting EV calculations.

    Attributes:
        params: LightGBM parameters
        model: Trained LightGBM Booster (None until fit)
        calibrator: Fitted Platt scaling model (None until fit)
        feature_names: List of feature column names

    Example:
        >>> model = MoneylineModel({"learning_rate": 0.1})
        >>> model.fit(X, y)
        >>> probs = model.predict_proba(X_test)
        >>> assert all(0 <= p <= 1 for p in probs)
    """

    def __init__(self, params: dict[str, Any] | None = None) -> None:
        """Initialize the model.

        Args:
            params: LightGBM parameters to override defaults.
                    Merged with DEFAULT_PARAMS.
        """
        self.params = {**DEFAULT_PARAMS, **(params or {})}
        self.model: lgb.Booster | None = None
        self.calibrator: LogisticRegression | None = None
        self.feature_names: list[str] = []

    def fit(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        num_boost_rounds: int = 100,
        calibration_frac: float = 0.2,
    ) -> None:
        """Train the model and fit Platt scaling calibrator.

        Splits data temporally: trains LightGBM on first portion,
        then fits Platt scaling on held-out calibration set from END
        of data to maintain temporal ordering.

        Args:
            X: Feature DataFrame
            y: Target Series (1 = home win, 0 = away win)
            num_boost_rounds: Number of boosting iterations
            calibration_frac: Fraction of data for calibration (from end)

        Example:
            >>> model.fit(X_train, y_train, num_boost_rounds=200)
        """
        self.feature_names = list(X.columns)
        n = len(X)
        cal_size = int(n * calibration_frac)
        train_size = n - cal_size

        # Ensure minimum sizes
        if train_size < 10:
            raise ValueError(
                f"Not enough training data: {train_size} samples. "
                "Need at least 10 for training."
            )
        if cal_size < 5:
            # If not enough for calibration, use all data for training
            # and skip calibration (use raw probs)
            cal_size = 0
            train_size = n

        # Split temporally (calibration from END)
        X_train = X.iloc[:train_size]
        y_train = y.iloc[:train_size]

        # Create LightGBM dataset
        train_data = lgb.Dataset(
            X_train,
            label=y_train,
            feature_name=self.feature_names,
        )

        # Train model
        self.model = lgb.train(
            self.params,
            train_data,
            num_boost_round=num_boost_rounds,
        )

        # Fit calibrator on held-out calibration set
        if cal_size > 0:
            X_cal = X.iloc[train_size:]
            y_cal = y.iloc[train_size:]

            # Get raw predictions for calibration set
            raw_probs = self.model.predict(X_cal)

            # Fit Platt scaling
            self.calibrator = LogisticRegression(solver="lbfgs", max_iter=1000)
            self.calibrator.fit(raw_probs.reshape(-1, 1), y_cal)
        else:
            self.calibrator = None

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Return calibrated probability of home team winning.

        Args:
            X: Feature DataFrame

        Returns:
            1D array of probabilities in [0, 1]

        Raises:
            RuntimeError: If model not fitted
        """
        if self.model is None:
            raise RuntimeError("Model not fitted. Call fit() first.")

        # Ensure column order matches training
        X_ordered = X[self.feature_names] if self.feature_names else X

        # Get raw LightGBM predictions
        raw_probs = self.model.predict(X_ordered)

        # Apply Platt scaling calibration if available
        if self.calibrator is not None:
            calibrated = self.calibrator.predict_proba(raw_probs.reshape(-1, 1))[:, 1]
            return calibrated

        return raw_probs

    def update(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        num_rounds: int = 10,
    ) -> None:
        """Incrementally update model with new data.

        Uses LightGBM's init_model feature to continue training
        from current model state. More efficient than full retraining.

        Note: Does NOT recalibrate the Platt scaling model.
        For recalibration, call fit() with accumulated data.

        Args:
            X: New feature DataFrame
            y: New target Series
            num_rounds: Additional boosting rounds
        """
        if self.model is None:
            raise RuntimeError(
                "Model not fitted. Call fit() for initial training."
            )

        # Ensure column order matches training
        X_ordered = X[self.feature_names] if self.feature_names else X

        # Create dataset for new data
        new_data = lgb.Dataset(
            X_ordered,
            label=y,
            feature_name=self.feature_names,
        )

        # Continue training from current model
        self.model = lgb.train(
            self.params,
            new_data,
            num_boost_round=num_rounds,
            init_model=self.model,
        )

    def save(self, path: str) -> None:
        """Save model to disk.

        Creates two files:
        - {path}.lgb: LightGBM model
        - {path}.calibrator: Platt scaling calibrator (joblib)
        - {path}.features: Feature names (joblib)

        Args:
            path: Base path (without extension)
        """
        if self.model is None:
            raise RuntimeError("Cannot save unfitted model.")

        base = Path(path)
        base.parent.mkdir(parents=True, exist_ok=True)

        # Save LightGBM model
        self.model.save_model(str(base) + ".lgb")

        # Save calibrator if fitted
        if self.calibrator is not None:
            joblib.dump(self.calibrator, str(base) + ".calibrator")

        # Save feature names
        joblib.dump(self.feature_names, str(base) + ".features")

    @classmethod
    def load(cls, path: str) -> "MoneylineModel":
        """Load model from disk.

        Args:
            path: Base path (without extension)

        Returns:
            Loaded MoneylineModel instance
        """
        base = Path(path)

        instance = cls()

        # Load LightGBM model
        lgb_path = str(base) + ".lgb"
        if not Path(lgb_path).exists():
            raise FileNotFoundError(f"Model file not found: {lgb_path}")
        instance.model = lgb.Booster(model_file=lgb_path)

        # Load calibrator if exists
        cal_path = str(base) + ".calibrator"
        if Path(cal_path).exists():
            instance.calibrator = joblib.load(cal_path)

        # Load feature names if exists
        feat_path = str(base) + ".features"
        if Path(feat_path).exists():
            instance.feature_names = joblib.load(feat_path)

        return instance

    def get_feature_importance(self) -> dict[str, float]:
        """Get feature importance scores.

        Returns:
            Dictionary mapping feature names to importance scores

        Raises:
            RuntimeError: If model not fitted
        """
        if self.model is None:
            raise RuntimeError("Model not fitted.")

        importance = self.model.feature_importance(importance_type="gain")
        return dict(zip(self.feature_names, importance))

    @property
    def num_trees(self) -> int:
        """Return the number of trees in the model."""
        if self.model is None:
            return 0
        return self.model.num_trees()
