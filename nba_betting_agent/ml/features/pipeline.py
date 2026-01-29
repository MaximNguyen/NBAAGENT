"""Feature pipeline for creating ML-ready training datasets.

Orchestrates all feature computation and outputs clean DataFrames
suitable for model training.
"""

from datetime import datetime

import pandas as pd

from nba_betting_agent.ml.data.schema import HistoricalGame
from nba_betting_agent.ml.features.team_features import compute_team_features
from nba_betting_agent.ml.features.situational import compute_situational_features


class FeaturePipeline:
    """Orchestrates feature computation for ML training.

    Combines team-level and situational features into a unified
    feature set suitable for model training.

    Attributes:
        lookback_games: Number of recent games for rolling stats
        feature_names: List of feature names (populated after first run)
    """

    def __init__(self, lookback_games: int = 10):
        """Initialize the feature pipeline.

        Args:
            lookback_games: Number of recent games for rolling stats (default: 10)
        """
        self.lookback_games = lookback_games
        self.feature_names: list[str] = []

    def create_features(
        self,
        games: list[HistoricalGame],
        target_game: HistoricalGame,
    ) -> dict[str, float]:
        """Create all features for a single game.

        Uses only games BEFORE target_game.game_date to prevent
        look-ahead bias in training.

        Args:
            games: List of all historical games
            target_game: The game to create features for

        Returns:
            Dictionary of feature names to float values
        """
        team_feats = compute_team_features(
            games=games,
            game_date=target_game.game_date,
            home_team=target_game.home_team,
            away_team=target_game.away_team,
            lookback_games=self.lookback_games,
        )

        situational_feats = compute_situational_features(
            games=games,
            game_date=target_game.game_date,
            home_team=target_game.home_team,
            away_team=target_game.away_team,
        )

        # Combine all features
        all_features = {**team_feats, **situational_feats}

        # Store feature names on first run
        if not self.feature_names:
            self.feature_names = sorted(all_features.keys())

        return all_features

    def create_training_dataset(
        self,
        games: list[HistoricalGame],
        min_games_required: int = 5,
    ) -> pd.DataFrame:
        """Create full training dataset from historical games.

        Iterates through all games, computing features for each.
        Skips early-season games that don't have enough history.

        Args:
            games: List of all historical games
            min_games_required: Minimum games each team needs before
                creating features (to avoid sparse early-season data)

        Returns:
            DataFrame with columns:
            - game_id: Unique game identifier
            - game_date: Date of the game
            - home_team, away_team: Team abbreviations
            - [feature columns]: All computed features
            - home_win: Target variable (1 if home won, 0 otherwise)
        """
        # Sort games by date for proper temporal processing
        sorted_games = sorted(games, key=lambda g: g.game_date)

        rows = []
        for i, target_game in enumerate(sorted_games):
            # Use only prior games as history
            prior_games = sorted_games[:i]

            # Skip if not enough history for either team
            home_count = sum(
                1 for g in prior_games
                if g.home_team == target_game.home_team or g.away_team == target_game.home_team
            )
            away_count = sum(
                1 for g in prior_games
                if g.home_team == target_game.away_team or g.away_team == target_game.away_team
            )

            if home_count < min_games_required or away_count < min_games_required:
                continue

            # Compute features
            features = self.create_features(prior_games, target_game)

            # Build row with metadata + features + target
            row = {
                "game_id": target_game.game_id,
                "game_date": (
                    target_game.game_date.date()
                    if isinstance(target_game.game_date, datetime)
                    else target_game.game_date
                ),
                "home_team": target_game.home_team,
                "away_team": target_game.away_team,
                **features,
                "home_win": 1.0 if target_game.home_win else 0.0,
            }
            rows.append(row)

        if not rows:
            # Return empty DataFrame with expected columns
            return pd.DataFrame(columns=[
                "game_id", "game_date", "home_team", "away_team", "home_win"
            ])

        df = pd.DataFrame(rows)

        # Ensure no NaN values (fill with sensible defaults)
        df = df.fillna(0.0)

        return df


def create_training_features(
    games: list[HistoricalGame],
    lookback_games: int = 10,
    min_games_required: int = 5,
) -> pd.DataFrame:
    """Convenience function to create training features.

    Creates a FeaturePipeline and generates a training dataset
    from the provided games.

    Args:
        games: List of historical games
        lookback_games: Number of recent games for rolling stats
        min_games_required: Minimum games each team needs before
            creating features

    Returns:
        DataFrame ready for model training
    """
    pipeline = FeaturePipeline(lookback_games=lookback_games)
    return pipeline.create_training_dataset(games, min_games_required=min_games_required)
