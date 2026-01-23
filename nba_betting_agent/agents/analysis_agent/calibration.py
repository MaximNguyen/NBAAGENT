"""Probability calibration module for converting raw model outputs to calibrated probabilities.

Uses Platt scaling (sigmoid calibration) via scikit-learn's LogisticRegression.
Calibrated probabilities are critical for accurate EV calculation - research shows
+34% ROI with calibration vs -35% without.

Example:
    >>> import numpy as np
    >>> from nba_betting_agent.agents.analysis_agent.calibration import ProbabilityCalibrator
    >>>
    >>> # Fit calibrator on historical data (overconfident model)
    >>> calibrator = ProbabilityCalibrator()
    >>> raw_probs = np.array([0.8] * 100)
    >>> outcomes = np.array([1] * 55 + [0] * 45)  # Only 55% win rate
    >>> calibrator.fit(raw_probs, outcomes)
    >>>
    >>> # Calibrate new predictions
    >>> calibrated = calibrator.calibrate_single(0.8)
    >>> print(f"Raw 0.8 -> Calibrated {calibrated:.3f}")
    Raw 0.8 -> Calibrated 0.550
"""

import pickle
from pathlib import Path
from typing import Optional

import numpy as np
from sklearn.linear_model import LogisticRegression


class ProbabilityCalibrator:
    """Calibrates raw probability estimates using Platt scaling.

    Platt scaling fits a logistic regression on raw probabilities to actual outcomes,
    correcting for systematic overconfidence or underconfidence in the base model.

    Attributes:
        method: Calibration method (currently only 'sigmoid' for Platt scaling)
        _calibrator: Fitted LogisticRegression model (None until fit() is called)
        _is_fitted: Whether the calibrator has been trained
    """

    def __init__(self, method: str = "sigmoid") -> None:
        """Initialize calibrator.

        Args:
            method: Calibration method. Only 'sigmoid' (Platt scaling) is supported.
                    This is the recommended method for small to medium datasets.

        Raises:
            ValueError: If method is not 'sigmoid'
        """
        if method != "sigmoid":
            raise ValueError(f"Only 'sigmoid' method is supported, got: {method}")

        self.method = method
        self._calibrator: Optional[LogisticRegression] = None
        self._is_fitted = False

    def fit(
        self, raw_probs: np.ndarray, outcomes: np.ndarray
    ) -> "ProbabilityCalibrator":
        """Train calibrator on historical (probability, outcome) pairs.

        Args:
            raw_probs: 1D array of raw probability estimates (0-1)
            outcomes: 1D array of actual binary outcomes (0 or 1)

        Returns:
            Self for method chaining

        Raises:
            ValueError: If inputs are invalid (wrong length, out of range, non-binary)

        Example:
            >>> calibrator = ProbabilityCalibrator()
            >>> raw = np.array([0.7, 0.8, 0.6, 0.9])
            >>> outcomes = np.array([1, 0, 1, 1])
            >>> calibrator.fit(raw, outcomes)
        """
        # Validate inputs
        if len(raw_probs) != len(outcomes):
            raise ValueError(
                f"raw_probs and outcomes must have same length: "
                f"{len(raw_probs)} != {len(outcomes)}"
            )

        if not np.all((raw_probs >= 0) & (raw_probs <= 1)):
            raise ValueError("raw_probs must be in [0, 1]")

        if not np.all(np.isin(outcomes, [0, 1])):
            raise ValueError("outcomes must be binary (0 or 1)")

        # Platt scaling: fit logistic regression on raw probabilities
        X = np.asarray(raw_probs).reshape(-1, 1)
        self._calibrator = LogisticRegression(solver="lbfgs", max_iter=1000)
        self._calibrator.fit(X, outcomes)
        self._is_fitted = True

        return self

    def calibrate(self, raw_probs: np.ndarray) -> np.ndarray:
        """Apply calibration to raw probability estimates.

        Args:
            raw_probs: 1D array of raw probability estimates

        Returns:
            1D array of calibrated probabilities

        Raises:
            RuntimeError: If calibrator not fitted yet

        Example:
            >>> calibrator.calibrate(np.array([0.6, 0.7, 0.8]))
            array([0.55, 0.62, 0.71])
        """
        if not self._is_fitted:
            raise RuntimeError("Calibrator not fitted. Call fit() first.")

        X = np.asarray(raw_probs).reshape(-1, 1)
        return self._calibrator.predict_proba(X)[:, 1]

    def calibrate_single(self, raw_prob: float) -> float:
        """Calibrate a single probability value.

        Convenience method for calibrating individual predictions.

        Args:
            raw_prob: Raw probability estimate (0-1)

        Returns:
            Calibrated probability

        Raises:
            RuntimeError: If calibrator not fitted yet

        Example:
            >>> calibrator.calibrate_single(0.75)
            0.68
        """
        if not self._is_fitted:
            raise RuntimeError("Calibrator not fitted. Call fit() first.")

        return float(self.calibrate(np.array([raw_prob]))[0])

    def save(self, path: Path) -> None:
        """Save calibrator to file for persistence.

        Args:
            path: Path to save calibrator (will be pickled)

        Raises:
            RuntimeError: If calibrator not fitted yet

        Example:
            >>> calibrator.save(Path("calibrator.pkl"))
        """
        if not self._is_fitted:
            raise RuntimeError("Cannot save unfitted calibrator")

        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "wb") as f:
            pickle.dump(
                {
                    "method": self.method,
                    "calibrator": self._calibrator,
                    "is_fitted": self._is_fitted,
                },
                f,
            )

    @classmethod
    def load(cls, path: Path) -> "ProbabilityCalibrator":
        """Load saved calibrator from file.

        Args:
            path: Path to saved calibrator

        Returns:
            Loaded ProbabilityCalibrator instance

        Raises:
            FileNotFoundError: If path doesn't exist

        Example:
            >>> calibrator = ProbabilityCalibrator.load(Path("calibrator.pkl"))
        """
        with open(path, "rb") as f:
            data = pickle.load(f)

        instance = cls(method=data["method"])
        instance._calibrator = data["calibrator"]
        instance._is_fitted = data["is_fitted"]

        return instance


def calibrate_probability(
    raw_prob: float, calibrator: Optional[ProbabilityCalibrator] = None
) -> float:
    """Calibrate a probability, or pass through if no calibrator provided.

    Useful for conditional calibration when calibrator may or may not be available.

    Args:
        raw_prob: Raw probability estimate (0-1)
        calibrator: Optional fitted calibrator. If None, returns raw_prob unchanged.

    Returns:
        Calibrated probability if calibrator provided, otherwise raw_prob

    Example:
        >>> # With calibrator
        >>> calibrate_probability(0.8, calibrator)
        0.72
        >>> # Without calibrator (passthrough)
        >>> calibrate_probability(0.8)
        0.8
    """
    if calibrator is None:
        return raw_prob

    return calibrator.calibrate_single(raw_prob)
