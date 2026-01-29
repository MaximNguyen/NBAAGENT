"""Walk-forward backtesting engine for betting model validation.

Simulates betting decisions over historical data using the model's
predicted probabilities and EV calculations.

Key principle: At each point in time, the model only knows past data.
This prevents look-ahead bias and provides realistic performance estimates.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import pandas as pd

from nba_betting_agent.ml.backtesting.metrics import (
    BacktestMetrics,
    calculate_brier_score,
    calculate_calibration_error,
    calculate_clv,
    calculate_roi,
)
from nba_betting_agent.ml.data.schema import HistoricalGame, HistoricalOdds
from nba_betting_agent.ml.features.pipeline import FeaturePipeline
from nba_betting_agent.ml.models.base import BaseBettingModel


@dataclass
class BacktestResult:
    """Results from a backtest simulation.

    Attributes:
        bets: List of individual bet records
        metrics: Aggregated performance metrics
        train_seasons: Seasons used for initial training
        test_seasons: Seasons used for simulation
        final_bankroll: Ending bankroll after all bets
        predictions: All predictions made (for calibration analysis)
        outcomes: Actual outcomes corresponding to predictions
    """

    bets: list[dict]
    metrics: BacktestMetrics
    train_seasons: list[str]
    test_seasons: list[str]
    final_bankroll: float
    predictions: list[float] = field(default_factory=list)
    outcomes: list[int] = field(default_factory=list)


class BacktestEngine:
    """Simulates betting decisions over historical data.

    Key principle: Walk-forward backtesting.
    - At each point in time, model only knows past data
    - Model is retrained periodically (e.g., monthly)
    - No future information leakage

    Example:
        >>> engine = BacktestEngine(
        ...     model_class=MoneylineModel,
        ...     feature_pipeline=FeaturePipeline(),
        ...     min_ev_threshold=0.05,
        ... )
        >>> result = engine.run(games, odds, ["2022-23"], ["2023-24"])
        >>> print(f"ROI: {result.metrics.roi_pct:.2f}%")
    """

    def __init__(
        self,
        model_class: type[BaseBettingModel],
        feature_pipeline: FeaturePipeline,
        min_ev_threshold: float = 0.05,
        bankroll: float = 10000.0,
        kelly_fraction: float = 0.25,
        retrain_frequency: str = "monthly",
    ) -> None:
        """Initialize the backtest engine.

        Args:
            model_class: Class (not instance) of the model to use
            feature_pipeline: Pipeline for creating features
            min_ev_threshold: Minimum EV to place a bet (default 5%)
            bankroll: Starting bankroll for simulation
            kelly_fraction: Fraction of Kelly criterion for bet sizing
            retrain_frequency: How often to retrain ('monthly', 'weekly', 'never')
        """
        self.model_class = model_class
        self.pipeline = feature_pipeline
        self.min_ev = min_ev_threshold
        self.initial_bankroll = bankroll
        self.bankroll = bankroll
        self.kelly_fraction = kelly_fraction
        self.retrain_freq = retrain_frequency

        self._last_retrain_month: int | None = None
        self._last_retrain_week: int | None = None
        self._model: BaseBettingModel | None = None

    def run(
        self,
        games: list[HistoricalGame],
        odds: list[HistoricalOdds],
        train_seasons: list[str],
        test_seasons: list[str],
    ) -> BacktestResult:
        """Run backtest simulation.

        Args:
            games: All historical games
            odds: Historical odds data
            train_seasons: Seasons for initial training
            test_seasons: Seasons to simulate betting

        Returns:
            BacktestResult with all bets and metrics
        """
        # Reset bankroll for new run
        self.bankroll = self.initial_bankroll
        self._last_retrain_month = None
        self._last_retrain_week = None

        # 1. Initial training on train_seasons
        train_games = [g for g in games if g.season in train_seasons]
        self._model = self._train_model(train_games)

        # 2. Simulate betting on test_seasons
        test_games = sorted(
            [g for g in games if g.season in test_seasons],
            key=lambda g: g.game_date,
        )

        bets: list[dict] = []
        predictions: list[float] = []
        outcomes: list[int] = []

        # Build odds lookup for efficiency
        odds_lookup = self._build_odds_lookup(odds)

        for game in test_games:
            # Get odds for this game (h2h market for home team)
            game_odds = self._find_odds(game, odds_lookup)
            if not game_odds:
                continue

            # Compute features using only pre-game data (strict temporal ordering)
            prior_games = [g for g in games if g.game_date < game.game_date]
            if len(prior_games) < 10:
                continue

            features = self.pipeline.create_features(prior_games, game)
            X = pd.DataFrame([features])

            # Get prediction
            pred_prob = self._model.predict_proba(X)[0]
            predictions.append(float(pred_prob))
            outcomes.append(1 if game.home_win else 0)

            # Calculate EV
            market_odds = game_odds.price
            ev = (pred_prob * market_odds) - 1

            # Decide whether to bet
            if ev >= self.min_ev:
                # Calculate bet size (Kelly)
                kelly_bet = self._kelly_bet(pred_prob, market_odds)
                wager = min(kelly_bet, self.bankroll * 0.05)  # Cap at 5% bankroll

                # Ensure wager is positive and within bankroll
                if wager <= 0 or wager > self.bankroll:
                    continue

                # Simulate outcome
                won = game.home_win
                returned = wager * market_odds if won else 0

                bets.append(
                    {
                        "game_id": game.game_id,
                        "game_date": game.game_date,
                        "home_team": game.home_team,
                        "away_team": game.away_team,
                        "pred_prob": pred_prob,
                        "market_odds": market_odds,
                        "ev": ev,
                        "wager": wager,
                        "returned": returned,
                        "won": won,
                        "profit": returned - wager,
                    }
                )

                self.bankroll += returned - wager

            # Periodic retraining
            if self._should_retrain(game.game_date):
                train_data = [g for g in games if g.game_date < game.game_date]
                # Use last ~3 seasons of data for retraining
                self._model = self._train_model(train_data[-3000:])

        # Calculate metrics
        metrics = self._calculate_metrics(bets, predictions, outcomes)

        return BacktestResult(
            bets=bets,
            metrics=metrics,
            train_seasons=train_seasons,
            test_seasons=test_seasons,
            final_bankroll=self.bankroll,
            predictions=predictions,
            outcomes=outcomes,
        )

    def _train_model(self, games: list[HistoricalGame]) -> BaseBettingModel:
        """Train a new model on the given games."""
        if len(games) < 50:
            raise ValueError(f"Not enough training games: {len(games)}. Need at least 50.")

        # Create training dataset
        df = self.pipeline.create_training_dataset(games)
        if len(df) < 30:
            raise ValueError(f"Not enough training samples after feature creation: {len(df)}")

        # Identify feature columns (exclude metadata and target)
        non_feature_cols = {"game_id", "game_date", "home_team", "away_team", "home_win"}
        feature_cols = [c for c in df.columns if c not in non_feature_cols]

        X = df[feature_cols]
        y = df["home_win"]

        # Create and train model
        model = self.model_class()
        model.fit(X, y)

        return model

    def _build_odds_lookup(
        self, odds: list[HistoricalOdds]
    ) -> dict[str, list[HistoricalOdds]]:
        """Build efficient lookup by game_id."""
        lookup: dict[str, list[HistoricalOdds]] = {}
        for o in odds:
            if o.game_id not in lookup:
                lookup[o.game_id] = []
            lookup[o.game_id].append(o)
        return lookup

    def _find_odds(
        self,
        game: HistoricalGame,
        odds_lookup: dict[str, list[HistoricalOdds]],
    ) -> HistoricalOdds | None:
        """Find h2h odds for home team in a game."""
        game_odds = odds_lookup.get(game.game_id, [])

        # Look for h2h market with home team outcome
        for o in game_odds:
            if o.market == "h2h" and o.outcome == game.home_team:
                return o

        # Fallback: any h2h odds
        for o in game_odds:
            if o.market == "h2h":
                return o

        return None

    def _kelly_bet(self, win_prob: float, odds: float) -> float:
        """Calculate Kelly criterion bet size.

        Kelly formula: (bp - q) / b
        where:
            b = decimal odds - 1 (net payout)
            p = win probability
            q = 1 - p
        """
        b = odds - 1
        p = win_prob
        q = 1 - p

        if b <= 0:
            return 0.0

        kelly_fraction = (b * p - q) / b

        # Apply fractional Kelly (more conservative)
        kelly_bet = kelly_fraction * self.kelly_fraction * self.bankroll

        # Never bet negative
        return max(0.0, kelly_bet)

    def _should_retrain(self, game_date: datetime) -> bool:
        """Check if model should be retrained based on frequency."""
        if self.retrain_freq == "never":
            return False

        # Ensure game_date is datetime
        if hasattr(game_date, "month"):
            month = game_date.month
            week = (
                game_date.isocalendar()[1]
                if hasattr(game_date, "isocalendar")
                else month * 4
            )
        else:
            return False

        if self.retrain_freq == "monthly":
            if self._last_retrain_month is None:
                self._last_retrain_month = month
                return False
            if month != self._last_retrain_month:
                self._last_retrain_month = month
                return True
            return False

        if self.retrain_freq == "weekly":
            if self._last_retrain_week is None:
                self._last_retrain_week = week
                return False
            if week != self._last_retrain_week:
                self._last_retrain_week = week
                return True
            return False

        return False

    def _calculate_metrics(
        self,
        bets: list[dict],
        predictions: list[float],
        outcomes: list[int],
    ) -> BacktestMetrics:
        """Calculate aggregated metrics from bets and predictions."""
        if not bets:
            return BacktestMetrics(
                total_bets=0,
                wins=0,
                losses=0,
                win_rate=0.0,
                total_wagered=0.0,
                total_returned=0.0,
                net_profit=0.0,
                roi_pct=0.0,
                brier_score=0.0,
                calibration_error=0.0,
                avg_edge=0.0,
                clv_pct=None,
            )

        wins = sum(1 for b in bets if b["won"])
        losses = len(bets) - wins
        total_wagered = sum(b["wager"] for b in bets)
        total_returned = sum(b["returned"] for b in bets)
        net_profit = total_returned - total_wagered

        return BacktestMetrics(
            total_bets=len(bets),
            wins=wins,
            losses=losses,
            win_rate=wins / len(bets) if bets else 0.0,
            total_wagered=total_wagered,
            total_returned=total_returned,
            net_profit=net_profit,
            roi_pct=calculate_roi(bets),
            brier_score=calculate_brier_score(predictions, outcomes),
            calibration_error=calculate_calibration_error(predictions, outcomes),
            avg_edge=sum(b["ev"] for b in bets) / len(bets) if bets else 0.0,
            clv_pct=None,  # Would need closing odds to calculate
        )


def run_backtest(
    games: list[HistoricalGame],
    odds: list[HistoricalOdds],
    model_class: type[BaseBettingModel],
    train_seasons: list[str],
    test_seasons: list[str],
    min_ev_threshold: float = 0.05,
    bankroll: float = 10000.0,
    kelly_fraction: float = 0.25,
    retrain_frequency: str = "monthly",
    lookback_games: int = 10,
) -> BacktestResult:
    """Convenience function to run a backtest.

    Creates a BacktestEngine with the specified parameters and runs
    the backtest.

    Args:
        games: All historical games
        odds: Historical odds data
        model_class: Class of model to use
        train_seasons: Seasons for initial training
        test_seasons: Seasons for betting simulation
        min_ev_threshold: Minimum EV to place bet
        bankroll: Starting bankroll
        kelly_fraction: Fraction of Kelly for bet sizing
        retrain_frequency: How often to retrain
        lookback_games: Games for rolling stats

    Returns:
        BacktestResult with bets and metrics
    """
    pipeline = FeaturePipeline(lookback_games=lookback_games)

    engine = BacktestEngine(
        model_class=model_class,
        feature_pipeline=pipeline,
        min_ev_threshold=min_ev_threshold,
        bankroll=bankroll,
        kelly_fraction=kelly_fraction,
        retrain_frequency=retrain_frequency,
    )

    return engine.run(games, odds, train_seasons, test_seasons)
