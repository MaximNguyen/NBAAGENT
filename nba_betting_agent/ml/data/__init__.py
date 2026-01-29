"""Data loading and schema definitions for ML training.

Provides:
- HistoricalGame: Individual game results with outcomes
- HistoricalOdds: Betting odds snapshots
- TrainingDataset: Combined games and odds for model training
- load_historical_games: Fetch historical NBA games
- load_historical_odds: Fetch historical betting odds
"""

from nba_betting_agent.ml.data.schema import (
    HistoricalGame,
    HistoricalOdds,
    TrainingDataset,
)
from nba_betting_agent.ml.data.historical import (
    load_historical_games,
    load_historical_odds,
)

__all__ = [
    "HistoricalGame",
    "HistoricalOdds",
    "TrainingDataset",
    "load_historical_games",
    "load_historical_odds",
]
