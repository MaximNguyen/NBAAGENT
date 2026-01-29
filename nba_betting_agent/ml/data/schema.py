"""Data schemas for historical ML training data.

Defines immutable dataclasses for:
- HistoricalGame: Individual NBA game results
- HistoricalOdds: Betting odds snapshots from sportsbooks
- TrainingDataset: Combined data for model training
"""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class HistoricalGame:
    """Represents a completed NBA game with outcome data.

    Used for training ML models to predict game outcomes.
    The home_win field is automatically derived from scores.

    Attributes:
        game_id: Unique NBA game identifier (e.g., "0022300001")
        game_date: Date and time of the game
        season: NBA season string (e.g., "2023-24")
        home_team: Home team abbreviation (e.g., "BOS")
        away_team: Away team abbreviation (e.g., "LAL")
        home_score: Final home team score
        away_score: Final away team score
        home_win: Whether home team won (derived from scores)
        spread: Point difference (home_score - away_score), positive = home win margin
        total: Combined final score (home_score + away_score)
    """

    game_id: str
    game_date: datetime
    season: str
    home_team: str
    away_team: str
    home_score: int
    away_score: int
    home_win: bool = field(init=False)
    spread: float = field(init=False)
    total: float = field(init=False)

    def __post_init__(self) -> None:
        """Derive home_win, spread, and total from scores."""
        # Use object.__setattr__ since dataclass is frozen
        object.__setattr__(self, "home_win", self.home_score > self.away_score)
        object.__setattr__(self, "spread", float(self.home_score - self.away_score))
        object.__setattr__(self, "total", float(self.home_score + self.away_score))


@dataclass(frozen=True)
class HistoricalOdds:
    """Represents betting odds snapshot from a sportsbook.

    Captures odds at a specific point in time for backtesting
    and model evaluation.

    Attributes:
        game_id: NBA game identifier this odds relates to
        game_date: Date of the game
        bookmaker: Sportsbook name (e.g., "draftkings", "fanduel")
        market: Market type ("h2h", "spreads", "totals")
        outcome: Outcome name (team name for h2h/spreads, "Over"/"Under" for totals)
        price: Decimal odds (e.g., 1.91 for -110 American)
        point: Point spread or total line (None for h2h)
        timestamp: When these odds were captured
    """

    game_id: str
    game_date: datetime
    bookmaker: str
    market: str
    outcome: str
    price: float
    point: float | None
    timestamp: datetime


@dataclass(frozen=True)
class TrainingDataset:
    """Combined historical games and odds for model training.

    Bundles games with their corresponding odds data and metadata
    about the season range covered.

    Attributes:
        games: List of historical games with outcomes
        odds: List of historical odds snapshots
        season_range: Tuple of (start_season, end_season) e.g., ("2021-22", "2023-24")
    """

    games: tuple[HistoricalGame, ...]
    odds: tuple[HistoricalOdds, ...]
    season_range: tuple[str, str]

    @classmethod
    def from_lists(
        cls,
        games: list[HistoricalGame],
        odds: list[HistoricalOdds],
        season_range: tuple[str, str],
    ) -> "TrainingDataset":
        """Create TrainingDataset from mutable lists.

        Converts lists to tuples for immutability.

        Args:
            games: List of historical games
            odds: List of historical odds
            season_range: Season range tuple

        Returns:
            New TrainingDataset instance
        """
        return cls(
            games=tuple(games),
            odds=tuple(odds),
            season_range=season_range,
        )
