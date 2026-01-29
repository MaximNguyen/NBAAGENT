"""Base model interface for NBA betting probability models.

All betting models must implement the BaseBettingModel interface to ensure
consistent behavior for training, prediction, persistence, and incremental updates.
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from typing import Self


class BaseBettingModel(ABC):
    """Abstract base class for all betting probability models.

    Defines the contract that all betting models must fulfill:
    - fit(): Train the model on historical data
    - predict_proba(): Generate calibrated win probabilities
    - update(): Incrementally update with new data
    - save()/load(): Model persistence

    Example:
        >>> class MyModel(BaseBettingModel):
        ...     def fit(self, X, y):
        ...         # Training logic
        ...         pass
        ...     # ... implement other methods
    """

    @abstractmethod
    def fit(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        num_boost_rounds: int = 100,
        calibration_frac: float = 0.2,
    ) -> None:
        """Train the model on historical data.

        Args:
            X: Feature DataFrame with one row per game
            y: Target Series (1 = home win, 0 = away win)
            num_boost_rounds: Number of boosting rounds for gradient boosting models
            calibration_frac: Fraction of data to hold out for probability calibration

        Note:
            Implementations should split off calibration data from the END
            of the dataset (most recent games) to maintain temporal ordering.
        """
        pass

    @abstractmethod
    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Return probability of home team winning for each row.

        Args:
            X: Feature DataFrame with same columns as training data

        Returns:
            1D numpy array of probabilities in [0, 1]

        Note:
            Implementations should return CALIBRATED probabilities,
            not raw model outputs.
        """
        pass

    @abstractmethod
    def update(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        num_rounds: int = 10,
    ) -> None:
        """Incrementally update model with new data.

        More efficient than full retraining for small updates.
        Does NOT recalibrate - call fit() periodically for recalibration.

        Args:
            X: New feature DataFrame
            y: New target Series
            num_rounds: Number of additional boosting rounds
        """
        pass

    @abstractmethod
    def save(self, path: str) -> None:
        """Save model to disk.

        Args:
            path: Base path for model files (implementation may create
                  multiple files with different extensions)
        """
        pass

    @classmethod
    @abstractmethod
    def load(cls, path: str) -> "BaseBettingModel":
        """Load model from disk.

        Args:
            path: Base path used in save()

        Returns:
            Loaded model instance
        """
        pass
