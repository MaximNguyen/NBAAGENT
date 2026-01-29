"""Performance metrics for backtesting betting models.

Provides calculations for:
- ROI (Return on Investment)
- Brier score (probability calibration)
- Calibration error (binned calibration accuracy)
- CLV (Closing Line Value)
"""

from dataclasses import dataclass

import numpy as np


@dataclass
class BacktestMetrics:
    """Performance metrics from a backtest simulation.

    Attributes:
        total_bets: Number of bets placed
        wins: Number of winning bets
        losses: Number of losing bets
        win_rate: Winning percentage (wins / total_bets)
        total_wagered: Total amount wagered across all bets
        total_returned: Total amount returned (payouts)
        net_profit: total_returned - total_wagered
        roi_pct: Return on investment percentage
        brier_score: Mean squared error of predictions (lower is better, target <0.25)
        calibration_error: Mean absolute calibration error
        avg_edge: Average predicted EV on taken bets
        clv_pct: Average closing line value percentage (if closing odds available)
    """

    total_bets: int
    wins: int
    losses: int
    win_rate: float
    total_wagered: float
    total_returned: float
    net_profit: float
    roi_pct: float
    brier_score: float
    calibration_error: float
    avg_edge: float
    clv_pct: float | None = None


def calculate_roi(bets: list[dict]) -> float:
    """Calculate ROI percentage from a list of bets.

    Args:
        bets: List of bet dictionaries, each with:
            - wagered: Amount bet
            - returned: Amount returned (payout)
            - won: Boolean indicating win/loss (optional)

    Returns:
        ROI percentage. Formula: ((returned - wagered) / wagered) * 100
        Returns 0.0 if no wagers.

    Example:
        >>> bets = [
        ...     {"wagered": 100, "returned": 190, "won": True},
        ...     {"wagered": 100, "returned": 0, "won": False},
        ... ]
        >>> calculate_roi(bets)
        -5.0  # Lost $10 on $200 wagered = -5%
    """
    if not bets:
        return 0.0

    total_wagered = sum(bet.get("wagered", bet.get("wager", 0)) for bet in bets)
    total_returned = sum(bet.get("returned", 0) for bet in bets)

    if total_wagered == 0:
        return 0.0

    return ((total_returned - total_wagered) / total_wagered) * 100


def calculate_brier_score(
    predictions: list[float],
    outcomes: list[int],
) -> float:
    """Calculate Brier score for probability predictions.

    The Brier score is the mean squared error between predicted
    probabilities and actual outcomes. Lower is better.

    Target: <0.25 for a useful model (random = 0.25 for 50/50)

    Args:
        predictions: List of predicted probabilities [0, 1]
        outcomes: List of actual outcomes (0 or 1)

    Returns:
        Brier score (mean squared error)

    Example:
        >>> predictions = [0.7, 0.3, 0.8]
        >>> outcomes = [1, 0, 1]  # Perfect predictions
        >>> calculate_brier_score(predictions, outcomes)
        0.046...  # Very low = good calibration
    """
    if not predictions or not outcomes:
        return 0.0

    if len(predictions) != len(outcomes):
        raise ValueError(
            f"Length mismatch: {len(predictions)} predictions vs {len(outcomes)} outcomes"
        )

    pred_arr = np.array(predictions)
    outcome_arr = np.array(outcomes)

    return float(np.mean((pred_arr - outcome_arr) ** 2))


def calculate_calibration_error(
    predictions: list[float],
    outcomes: list[int],
    n_bins: int = 10,
) -> float:
    """Calculate mean absolute calibration error.

    Bins predictions by predicted probability, then computes the
    mean absolute difference between predicted and actual win rates.

    Args:
        predictions: List of predicted probabilities [0, 1]
        outcomes: List of actual outcomes (0 or 1)
        n_bins: Number of bins for grouping predictions

    Returns:
        Mean absolute calibration error

    Example:
        >>> predictions = [0.55, 0.52, 0.48, 0.73, 0.71]
        >>> outcomes = [1, 1, 0, 1, 0]
        >>> calculate_calibration_error(predictions, outcomes, n_bins=2)
        # Bin 1: pred ~0.52, actual 0.67 -> |0.52-0.67|
        # Bin 2: pred ~0.72, actual 0.50 -> |0.72-0.50|
    """
    if not predictions or not outcomes:
        return 0.0

    if len(predictions) != len(outcomes):
        raise ValueError(
            f"Length mismatch: {len(predictions)} predictions vs {len(outcomes)} outcomes"
        )

    pred_arr = np.array(predictions)
    outcome_arr = np.array(outcomes)

    # Create bin edges
    bin_edges = np.linspace(0, 1, n_bins + 1)

    calibration_errors = []

    for i in range(n_bins):
        lower = bin_edges[i]
        upper = bin_edges[i + 1]

        # Find predictions in this bin
        mask = (pred_arr >= lower) & (pred_arr < upper)
        if i == n_bins - 1:  # Include upper edge in last bin
            mask = (pred_arr >= lower) & (pred_arr <= upper)

        if np.sum(mask) == 0:
            continue  # Skip empty bins

        bin_pred_mean = np.mean(pred_arr[mask])
        bin_actual_rate = np.mean(outcome_arr[mask])

        calibration_errors.append(abs(bin_pred_mean - bin_actual_rate))

    if not calibration_errors:
        return 0.0

    return float(np.mean(calibration_errors))


def calculate_clv(
    bet_odds: float,
    closing_odds: float,
) -> float:
    """Calculate Closing Line Value percentage.

    CLV measures whether you got a better price than the closing line.
    Positive CLV indicates +EV betting regardless of individual results.

    Formula: ((closing_implied - bet_implied) / bet_implied) * 100
    where implied_prob = 1 / decimal_odds

    Args:
        bet_odds: Decimal odds when bet was placed
        closing_odds: Decimal odds at game start (closing line)

    Returns:
        CLV percentage. Positive = bet at better price than close.

    Example:
        >>> calculate_clv(bet_odds=2.0, closing_odds=1.9)
        5.26  # Got 2.0 when close was 1.9 = positive CLV
    """
    if bet_odds <= 1.0 or closing_odds <= 1.0:
        return 0.0

    bet_implied = 1 / bet_odds
    closing_implied = 1 / closing_odds

    # CLV = (closing_implied - bet_implied) / bet_implied * 100
    # Positive when closing implied > bet implied (you got better odds)
    return ((closing_implied - bet_implied) / bet_implied) * 100
