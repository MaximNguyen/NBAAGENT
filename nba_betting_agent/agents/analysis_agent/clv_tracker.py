"""Closing Line Value (CLV) tracking for measuring bet quality.

CLV is the gold standard metric for evaluating betting performance. It measures
whether your bets beat the closing line - the sharpest, most efficient price
available before the game starts.

Positive CLV means you consistently get better odds than the closing price,
indicating +EV betting even if individual bets lose. Research shows consistent
positive CLV is the best predictor of long-term profitability.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional
import json
import statistics


@dataclass
class CLVResult:
    """Closing line value calculation result.

    Attributes:
        bet_odds: Decimal odds when bet was placed
        closing_odds: Decimal odds at game start (closing line)
        clv_percentage: CLV as percentage (positive = beat the close)
        beat_closing: True if bet odds were better than closing
        bet_implied_prob: Implied probability of bet odds
        closing_implied_prob: Implied probability of closing odds
    """

    bet_odds: float
    closing_odds: float
    clv_percentage: float
    beat_closing: bool
    bet_implied_prob: float
    closing_implied_prob: float


def calculate_clv(bet_odds: float, closing_odds: float) -> CLVResult:
    """Calculate closing line value for a bet.

    CLV measures how much better (or worse) your bet odds were compared to
    the closing line. Positive CLV indicates you got better value.

    Formula:
        CLV% = ((closing_implied - bet_implied) / bet_implied) × 100

    Args:
        bet_odds: Decimal odds when bet was placed
        closing_odds: Decimal odds at game start

    Returns:
        CLVResult with detailed breakdown

    Example:
        >>> # Bet at 2.10 (+110), closed at 1.95 (-105)
        >>> result = calculate_clv(bet_odds=2.10, closing_odds=1.95)
        >>> result.clv_percentage
        7.69  # You beat the closing line by 7.69%
        >>> result.beat_closing
        True

    Notes:
        - Bet odds of 2.10 = 47.6% implied probability
        - Closing odds of 1.95 = 51.3% implied probability
        - CLV = ((0.513 - 0.476) / 0.476) × 100 = 7.69%
        - Higher closing implied prob means the market moved against your bet
        - But you locked in better odds, so positive CLV
    """
    # Calculate implied probabilities
    bet_implied_prob = 1.0 / bet_odds
    closing_implied_prob = 1.0 / closing_odds

    # Calculate CLV
    # Positive CLV = closing line moved against you (implied prob increased)
    # but you got better odds by betting early
    clv_percentage = ((closing_implied_prob - bet_implied_prob) / bet_implied_prob) * 100

    beat_closing = clv_percentage > 0

    return CLVResult(
        bet_odds=bet_odds,
        closing_odds=closing_odds,
        clv_percentage=clv_percentage,
        beat_closing=beat_closing,
        bet_implied_prob=bet_implied_prob,
        closing_implied_prob=closing_implied_prob,
    )


@dataclass
class BetRecord:
    """Record of a placed bet with optional CLV tracking.

    Attributes:
        game_id: Unique identifier for the game
        placed_at: When the bet was placed
        bet_odds: Decimal odds when bet was placed
        outcome_name: What was bet on (e.g., "Boston Celtics ML")
        closing_odds: Closing line odds (None until recorded)
        clv: CLV result (None until closing odds recorded)
        result: Bet outcome - "won", "lost", "push", or None if not settled
    """

    game_id: str
    placed_at: datetime
    bet_odds: float
    outcome_name: str
    closing_odds: Optional[float] = None
    clv: Optional[CLVResult] = None
    result: Optional[str] = None


class CLVTracker:
    """Track closing line value across multiple bets.

    This class maintains a record of all bets and calculates aggregate
    CLV statistics to measure betting performance over time.

    Example:
        >>> tracker = CLVTracker()
        >>> tracker.record_bet("game1", bet_odds=2.10, outcome_name="Celtics ML")
        >>> tracker.record_closing("game1", "Celtics ML", closing_odds=1.95)
        >>> stats = tracker.get_clv_stats()
        >>> stats["avg_clv"]
        7.69
    """

    def __init__(self, storage_path: Optional[Path] = None):
        """Initialize CLV tracker.

        Args:
            storage_path: Path to JSON file for persistence (optional)
        """
        self.bets: list[BetRecord] = []
        self.storage_path = storage_path

        if storage_path and storage_path.exists():
            self.load()

    def record_bet(
        self,
        game_id: str,
        bet_odds: float,
        outcome_name: str,
        placed_at: Optional[datetime] = None,
    ) -> BetRecord:
        """Record a new bet.

        Args:
            game_id: Unique game identifier
            bet_odds: Decimal odds when bet was placed
            outcome_name: What was bet on
            placed_at: When bet was placed (defaults to now)

        Returns:
            BetRecord for the recorded bet
        """
        if placed_at is None:
            placed_at = datetime.now()

        bet = BetRecord(
            game_id=game_id,
            placed_at=placed_at,
            bet_odds=bet_odds,
            outcome_name=outcome_name,
        )

        self.bets.append(bet)

        if self.storage_path:
            self.save()

        return bet

    def record_closing(
        self,
        game_id: str,
        outcome_name: str,
        closing_odds: float,
    ) -> None:
        """Record closing odds for a bet and calculate CLV.

        Args:
            game_id: Game identifier
            outcome_name: Outcome that was bet on
            closing_odds: Decimal odds at game start

        Raises:
            ValueError: If no matching bet found
        """
        # Find matching bet
        bet = None
        for b in self.bets:
            if b.game_id == game_id and b.outcome_name == outcome_name:
                bet = b
                break

        if not bet:
            raise ValueError(
                f"No bet found for game_id={game_id}, outcome={outcome_name}"
            )

        # Calculate and record CLV
        bet.closing_odds = closing_odds
        bet.clv = calculate_clv(bet.bet_odds, closing_odds)

        if self.storage_path:
            self.save()

    def get_clv_stats(self) -> dict:
        """Calculate aggregate CLV statistics.

        Returns:
            Dictionary with:
                - total_bets: Total number of bets recorded
                - bets_with_closing: Bets with closing odds recorded
                - avg_clv: Average CLV percentage
                - median_clv: Median CLV percentage
                - pct_beat_closing: Percentage of bets that beat closing line
                - clv_std: Standard deviation of CLV

        Example:
            >>> stats = tracker.get_clv_stats()
            >>> print(f"Average CLV: {stats['avg_clv']:.2f}%")
            >>> print(f"Beat closing: {stats['pct_beat_closing']:.1f}% of bets")
        """
        total_bets = len(self.bets)
        bets_with_clv = [b for b in self.bets if b.clv is not None]
        bets_with_closing = len(bets_with_clv)

        if bets_with_closing == 0:
            return {
                "total_bets": total_bets,
                "bets_with_closing": 0,
                "avg_clv": 0.0,
                "median_clv": 0.0,
                "pct_beat_closing": 0.0,
                "clv_std": 0.0,
            }

        # Extract CLV values
        clv_values = [b.clv.clv_percentage for b in bets_with_clv]
        beat_closing_count = sum(1 for b in bets_with_clv if b.clv.beat_closing)

        return {
            "total_bets": total_bets,
            "bets_with_closing": bets_with_closing,
            "avg_clv": statistics.mean(clv_values),
            "median_clv": statistics.median(clv_values),
            "pct_beat_closing": (beat_closing_count / bets_with_closing) * 100,
            "clv_std": statistics.stdev(clv_values) if bets_with_closing > 1 else 0.0,
        }

    def save(self) -> None:
        """Save bet records to storage path."""
        if not self.storage_path:
            raise ValueError("No storage_path configured")

        # Create parent directory if needed
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert bets to JSON-serializable format
        data = []
        for bet in self.bets:
            bet_dict = {
                "game_id": bet.game_id,
                "placed_at": bet.placed_at.isoformat(),
                "bet_odds": bet.bet_odds,
                "outcome_name": bet.outcome_name,
                "closing_odds": bet.closing_odds,
                "result": bet.result,
            }
            # Include CLV if available
            if bet.clv:
                bet_dict["clv"] = {
                    "clv_percentage": bet.clv.clv_percentage,
                    "beat_closing": bet.clv.beat_closing,
                }
            data.append(bet_dict)

        with open(self.storage_path, "w") as f:
            json.dump(data, f, indent=2)

    def load(self) -> None:
        """Load bet records from storage path."""
        if not self.storage_path or not self.storage_path.exists():
            return

        with open(self.storage_path) as f:
            data = json.load(f)

        self.bets = []
        for bet_dict in data:
            placed_at = datetime.fromisoformat(bet_dict["placed_at"])

            bet = BetRecord(
                game_id=bet_dict["game_id"],
                placed_at=placed_at,
                bet_odds=bet_dict["bet_odds"],
                outcome_name=bet_dict["outcome_name"],
                closing_odds=bet_dict.get("closing_odds"),
                result=bet_dict.get("result"),
            )

            # Recalculate CLV if closing odds available
            if bet.closing_odds:
                bet.clv = calculate_clv(bet.bet_odds, bet.closing_odds)

            self.bets.append(bet)

    @classmethod
    def from_file(cls, path: Path) -> "CLVTracker":
        """Load tracker from file.

        Args:
            path: Path to JSON file

        Returns:
            CLVTracker with loaded data
        """
        tracker = cls(storage_path=path)
        return tracker
