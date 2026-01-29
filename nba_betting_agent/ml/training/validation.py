"""Walk-forward validation and model evaluation for temporal betting data.

Walk-forward validation is critical for sports betting models because:
1. It prevents temporal leakage (using future data to predict past)
2. It simulates real-world model deployment
3. It provides realistic performance estimates

Example:
    >>> from nba_betting_agent.ml.training.validation import walk_forward_split, evaluate_model
    >>>
    >>> # Generate temporal train/test splits
    >>> for train_df, test_df in walk_forward_split(df, train_seasons=3, test_seasons=1):
    ...     model.fit(train_df[features], train_df['home_win'])
    ...     metrics = evaluate_model(model, test_df[features], test_df['home_win'])
    ...     print(f"Brier: {metrics['brier_score']:.4f}")
"""

from collections.abc import Iterator
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    brier_score_loss,
    log_loss,
    roc_auc_score,
)

if TYPE_CHECKING:
    from nba_betting_agent.ml.models.base import BaseBettingModel


def walk_forward_split(
    df: pd.DataFrame,
    train_seasons: int = 3,
    test_seasons: int = 1,
    date_col: str = "game_date",
    season_col: str = "season",
) -> Iterator[tuple[pd.DataFrame, pd.DataFrame]]:
    """Generate walk-forward train/test splits respecting temporal order.

    Each fold trains on N seasons and tests on the next M seasons.
    This prevents data leakage from using future data to train models.

    Args:
        df: DataFrame with season and date columns
        train_seasons: Number of seasons to train on
        test_seasons: Number of seasons to test on
        date_col: Name of date column for sorting
        season_col: Name of season column for splitting

    Yields:
        Tuples of (train_df, test_df) for each fold

    Example:
        >>> # With seasons 2020-21, 2021-22, 2022-23, 2023-24:
        >>> # Fold 1: train on 20-21,21-22,22-23 -> test on 23-24
        >>> for train, test in walk_forward_split(df, train_seasons=3, test_seasons=1):
        ...     print(f"Train: {len(train)}, Test: {len(test)}")

    Note:
        If no season column exists, the function will attempt to extract
        seasons from dates (Oct-Jun spans). If that fails, it splits by date.
    """
    # Sort by date first
    df_sorted = df.sort_values(date_col).reset_index(drop=True)

    # Get unique seasons
    if season_col not in df.columns:
        # Try to infer season from dates
        df_sorted = _add_season_column(df_sorted, date_col, season_col)

    seasons = sorted(df_sorted[season_col].unique())

    if len(seasons) < train_seasons + test_seasons:
        raise ValueError(
            f"Not enough seasons for walk-forward split. "
            f"Have {len(seasons)}, need {train_seasons + test_seasons}."
        )

    # Generate folds
    total_needed = train_seasons + test_seasons
    num_folds = len(seasons) - total_needed + 1

    for fold_idx in range(num_folds):
        train_season_list = seasons[fold_idx : fold_idx + train_seasons]
        test_season_list = seasons[
            fold_idx + train_seasons : fold_idx + train_seasons + test_seasons
        ]

        train_mask = df_sorted[season_col].isin(train_season_list)
        test_mask = df_sorted[season_col].isin(test_season_list)

        train_df = df_sorted[train_mask].copy()
        test_df = df_sorted[test_mask].copy()

        yield train_df, test_df


def _add_season_column(
    df: pd.DataFrame,
    date_col: str,
    season_col: str,
) -> pd.DataFrame:
    """Add a season column based on date (NBA season spans Oct-Jun).

    Args:
        df: DataFrame with date column
        date_col: Name of date column
        season_col: Name for new season column

    Returns:
        DataFrame with added season column
    """
    df = df.copy()
    dates = pd.to_datetime(df[date_col])

    def get_season(dt: pd.Timestamp) -> str:
        # NBA season: October Year X -> June Year X+1
        # Format: "2023-24" for Oct 2023 - Jun 2024
        if dt.month >= 10:
            start_year = dt.year
        else:
            start_year = dt.year - 1
        end_year = start_year + 1
        return f"{start_year}-{str(end_year)[2:]}"

    df[season_col] = dates.apply(get_season)
    return df


def evaluate_model(
    model: "BaseBettingModel",
    X_test: pd.DataFrame,
    y_test: pd.Series,
) -> dict[str, float]:
    """Evaluate model predictions against actual outcomes.

    Computes standard metrics for probability model evaluation:
    - accuracy: Classification accuracy at 0.5 threshold
    - log_loss: Negative log likelihood (lower is better)
    - brier_score: Mean squared error of probabilities (lower is better)
    - roc_auc: Area under ROC curve (higher is better)
    - calibration_error: Mean |predicted - actual| in bins

    Args:
        model: Fitted model with predict_proba method
        X_test: Test features
        y_test: True outcomes (0/1)

    Returns:
        Dictionary of metric names to values

    Example:
        >>> metrics = evaluate_model(model, X_test, y_test)
        >>> print(f"Brier: {metrics['brier_score']:.4f}")
        >>> print(f"AUC: {metrics['roc_auc']:.4f}")
    """
    y_pred = model.predict_proba(X_test)
    y_true = np.asarray(y_test)

    # Binary predictions at 0.5 threshold
    y_pred_binary = (y_pred >= 0.5).astype(int)

    # Compute metrics
    metrics = {
        "accuracy": accuracy_score(y_true, y_pred_binary),
        "log_loss": log_loss(y_true, y_pred),
        "brier_score": brier_score_loss(y_true, y_pred),
        "roc_auc": roc_auc_score(y_true, y_pred),
        "calibration_error": _compute_calibration_error(y_true, y_pred),
    }

    return metrics


def _compute_calibration_error(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    n_bins: int = 10,
) -> float:
    """Compute Expected Calibration Error (ECE).

    ECE is the weighted average of |predicted_prob - actual_rate|
    across probability bins.

    Args:
        y_true: True binary outcomes
        y_pred: Predicted probabilities
        n_bins: Number of probability bins

    Returns:
        Expected calibration error (lower is better)
    """
    bin_edges = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    total = len(y_true)

    for i in range(n_bins):
        in_bin = (y_pred >= bin_edges[i]) & (y_pred < bin_edges[i + 1])
        # Include right edge in last bin
        if i == n_bins - 1:
            in_bin = (y_pred >= bin_edges[i]) & (y_pred <= bin_edges[i + 1])

        n_in_bin = in_bin.sum()
        if n_in_bin > 0:
            actual_rate = y_true[in_bin].mean()
            predicted_prob = y_pred[in_bin].mean()
            ece += (n_in_bin / total) * abs(predicted_prob - actual_rate)

    return ece


def cross_validate(
    model_class: type["BaseBettingModel"],
    df: pd.DataFrame,
    feature_cols: list[str],
    target_col: str = "home_win",
    train_seasons: int = 3,
    test_seasons: int = 1,
    model_params: dict | None = None,
) -> list[dict]:
    """Run walk-forward cross-validation.

    Trains a fresh model for each fold and collects evaluation metrics.

    Args:
        model_class: Model class to instantiate
        df: Full DataFrame with features and target
        feature_cols: List of feature column names
        target_col: Target column name
        train_seasons: Seasons to train on per fold
        test_seasons: Seasons to test on per fold
        model_params: Parameters to pass to model constructor

    Returns:
        List of metric dictionaries, one per fold

    Example:
        >>> results = cross_validate(MoneylineModel, df, feature_cols)
        >>> mean_brier = np.mean([r['brier_score'] for r in results])
        >>> print(f"Mean Brier: {mean_brier:.4f}")
    """
    results = []

    for fold_idx, (train_df, test_df) in enumerate(
        walk_forward_split(df, train_seasons, test_seasons)
    ):
        # Create fresh model for each fold
        model = model_class(model_params)

        # Train
        X_train = train_df[feature_cols]
        y_train = train_df[target_col]
        model.fit(X_train, y_train)

        # Evaluate
        X_test = test_df[feature_cols]
        y_test = test_df[target_col]
        metrics = evaluate_model(model, X_test, y_test)
        metrics["fold"] = fold_idx

        results.append(metrics)

    return results


def calibration_bins(
    y_true: np.ndarray | pd.Series,
    y_pred: np.ndarray,
    n_bins: int = 10,
) -> tuple[np.ndarray, np.ndarray]:
    """Compute calibration curve data for plotting.

    Returns the mean predicted probability and actual win rate
    for each probability bin, suitable for calibration plots.

    Args:
        y_true: True binary outcomes
        y_pred: Predicted probabilities
        n_bins: Number of probability bins

    Returns:
        Tuple of (predicted_probs, actual_rates) arrays for plotting

    Example:
        >>> pred_probs, actual_rates = calibration_bins(y_true, y_pred)
        >>> plt.plot([0, 1], [0, 1], 'k--')  # Perfect calibration
        >>> plt.scatter(pred_probs, actual_rates)
        >>> plt.xlabel("Predicted Probability")
        >>> plt.ylabel("Actual Win Rate")
    """
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)

    bin_edges = np.linspace(0, 1, n_bins + 1)
    predicted_probs = []
    actual_rates = []

    for i in range(n_bins):
        in_bin = (y_pred >= bin_edges[i]) & (y_pred < bin_edges[i + 1])
        # Include right edge in last bin
        if i == n_bins - 1:
            in_bin = (y_pred >= bin_edges[i]) & (y_pred <= bin_edges[i + 1])

        n_in_bin = in_bin.sum()
        if n_in_bin > 0:
            predicted_probs.append(y_pred[in_bin].mean())
            actual_rates.append(y_true[in_bin].mean())

    return np.array(predicted_probs), np.array(actual_rates)
