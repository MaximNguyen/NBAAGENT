"""Tests for closing line value tracker."""

from datetime import datetime
from pathlib import Path
import tempfile

import pytest

from nba_betting_agent.agents.analysis_agent.clv_tracker import (
    BetRecord,
    CLVResult,
    CLVTracker,
    calculate_clv,
)


def test_calculate_clv_positive():
    """Test positive CLV when bet odds beat closing line."""
    # Bet at +110 (2.10), closed at -105 (1.952)
    result = calculate_clv(bet_odds=2.10, closing_odds=1.952)

    assert result.bet_odds == 2.10
    assert result.closing_odds == 1.952
    assert result.clv_percentage > 0  # Positive CLV
    assert result.beat_closing is True
    assert result.bet_implied_prob < result.closing_implied_prob
    # Bet implied ~47.6%, closing implied ~51.2%
    assert abs(result.bet_implied_prob - 0.476) < 0.01
    assert abs(result.closing_implied_prob - 0.512) < 0.01


def test_calculate_clv_negative():
    """Test negative CLV when closing line was better."""
    # Bet at -105 (1.952), closed at +110 (2.10)
    result = calculate_clv(bet_odds=1.952, closing_odds=2.10)

    assert result.clv_percentage < 0  # Negative CLV
    assert result.beat_closing is False
    assert result.bet_implied_prob > result.closing_implied_prob


def test_calculate_clv_zero():
    """Test zero CLV when odds unchanged."""
    result = calculate_clv(bet_odds=2.00, closing_odds=2.00)

    assert abs(result.clv_percentage) < 0.01  # Essentially zero
    assert result.bet_implied_prob == result.closing_implied_prob
    assert result.bet_implied_prob == 0.5


def test_clv_result_fields():
    """Test that CLVResult has all expected fields populated."""
    result = calculate_clv(bet_odds=2.10, closing_odds=1.95)

    assert isinstance(result.bet_odds, float)
    assert isinstance(result.closing_odds, float)
    assert isinstance(result.clv_percentage, float)
    assert isinstance(result.beat_closing, bool)
    assert isinstance(result.bet_implied_prob, float)
    assert isinstance(result.closing_implied_prob, float)
    assert result.bet_implied_prob > 0
    assert result.closing_implied_prob > 0


def test_tracker_record_bet():
    """Test recording a new bet."""
    tracker = CLVTracker()

    placed_at = datetime(2026, 1, 23, 10, 0, 0)
    bet = tracker.record_bet(
        game_id="game1",
        bet_odds=2.10,
        outcome_name="Boston Celtics ML",
        placed_at=placed_at,
    )

    assert isinstance(bet, BetRecord)
    assert bet.game_id == "game1"
    assert bet.bet_odds == 2.10
    assert bet.outcome_name == "Boston Celtics ML"
    assert bet.placed_at == placed_at
    assert bet.closing_odds is None
    assert bet.clv is None
    assert len(tracker.bets) == 1


def test_tracker_record_closing():
    """Test recording closing odds and calculating CLV."""
    tracker = CLVTracker()

    # Record bet
    tracker.record_bet(
        game_id="game1",
        bet_odds=2.10,
        outcome_name="Boston Celtics ML",
    )

    # Record closing odds
    tracker.record_closing(
        game_id="game1",
        outcome_name="Boston Celtics ML",
        closing_odds=1.95,
    )

    bet = tracker.bets[0]
    assert bet.closing_odds == 1.95
    assert bet.clv is not None
    assert bet.clv.clv_percentage > 0
    assert bet.clv.beat_closing is True


def test_tracker_get_stats_empty():
    """Test stats with no bets."""
    tracker = CLVTracker()
    stats = tracker.get_clv_stats()

    assert stats["total_bets"] == 0
    assert stats["bets_with_closing"] == 0
    assert stats["avg_clv"] == 0.0
    assert stats["median_clv"] == 0.0
    assert stats["pct_beat_closing"] == 0.0


def test_tracker_get_stats_with_data():
    """Test aggregate statistics with multiple bets."""
    tracker = CLVTracker()

    # Record 3 bets with varying CLV
    bets = [
        ("game1", 2.10, 1.95),  # Positive CLV
        ("game2", 1.90, 2.00),  # Negative CLV
        ("game3", 2.05, 1.90),  # Positive CLV
    ]

    for game_id, bet_odds, closing_odds in bets:
        tracker.record_bet(game_id=game_id, bet_odds=bet_odds, outcome_name="Test")
        tracker.record_closing(game_id=game_id, outcome_name="Test", closing_odds=closing_odds)

    stats = tracker.get_clv_stats()

    assert stats["total_bets"] == 3
    assert stats["bets_with_closing"] == 3
    # 2 out of 3 beat closing
    assert stats["pct_beat_closing"] > 60
    assert stats["pct_beat_closing"] < 70
    assert isinstance(stats["avg_clv"], float)
    assert isinstance(stats["median_clv"], float)
    assert stats["clv_std"] > 0


def test_tracker_save_load(tmp_path):
    """Test persistence with save and load."""
    storage_path = tmp_path / "clv_tracker.json"
    tracker = CLVTracker(storage_path=storage_path)

    # Record bets
    tracker.record_bet(game_id="game1", bet_odds=2.10, outcome_name="Celtics ML")
    tracker.record_closing(game_id="game1", outcome_name="Celtics ML", closing_odds=1.95)

    # Save
    tracker.save()
    assert storage_path.exists()

    # Load into new tracker
    new_tracker = CLVTracker.from_file(storage_path)

    assert len(new_tracker.bets) == 1
    assert new_tracker.bets[0].game_id == "game1"
    assert new_tracker.bets[0].bet_odds == 2.10
    assert new_tracker.bets[0].closing_odds == 1.95
    assert new_tracker.bets[0].clv is not None
    assert new_tracker.bets[0].clv.beat_closing is True


def test_calculate_clv_extreme_movement():
    """Test CLV calculation with large line movement."""
    # Bet at +200 (3.00), closed at -150 (1.667) - massive move
    result = calculate_clv(bet_odds=3.00, closing_odds=1.667)

    # Bet implied ~33.3%, closing implied ~60%
    # CLV = ((0.60 - 0.333) / 0.333) * 100 = ~80%
    assert result.clv_percentage > 70
    assert result.beat_closing is True


def test_clv_percentage_math():
    """Verify CLV percentage calculation formula."""
    # Known values for precise testing
    bet_odds = 2.00  # 50% implied
    closing_odds = 1.80  # 55.56% implied

    result = calculate_clv(bet_odds, closing_odds)

    # CLV = ((0.5556 - 0.50) / 0.50) * 100 = 11.11%
    expected_clv = ((1 / 1.80 - 1 / 2.00) / (1 / 2.00)) * 100
    assert abs(result.clv_percentage - expected_clv) < 0.01


def test_tracker_multiple_games():
    """Test tracking multiple games independently."""
    tracker = CLVTracker()

    # Record bets on different games
    tracker.record_bet(game_id="game1", bet_odds=2.10, outcome_name="Celtics ML")
    tracker.record_bet(game_id="game2", bet_odds=1.90, outcome_name="Lakers ML")

    # Record closing for first game only
    tracker.record_closing(game_id="game1", outcome_name="Celtics ML", closing_odds=1.95)

    # Stats should only include games with closing odds
    stats = tracker.get_clv_stats()
    assert stats["total_bets"] == 2
    assert stats["bets_with_closing"] == 1


def test_tracker_record_closing_not_found():
    """Test error when recording closing for non-existent bet."""
    tracker = CLVTracker()

    with pytest.raises(ValueError, match="No bet found"):
        tracker.record_closing(
            game_id="nonexistent",
            outcome_name="Test",
            closing_odds=2.00,
        )


def test_bet_record_dataclass():
    """Test BetRecord dataclass initialization."""
    placed_at = datetime.now()
    bet = BetRecord(
        game_id="game1",
        placed_at=placed_at,
        bet_odds=2.10,
        outcome_name="Celtics ML",
    )

    assert bet.game_id == "game1"
    assert bet.placed_at == placed_at
    assert bet.bet_odds == 2.10
    assert bet.outcome_name == "Celtics ML"
    assert bet.closing_odds is None
    assert bet.clv is None
    assert bet.result is None


def test_tracker_auto_save_on_record(tmp_path):
    """Test that tracker auto-saves when storage_path is set."""
    storage_path = tmp_path / "auto_save.json"
    tracker = CLVTracker(storage_path=storage_path)

    # Recording should trigger save
    tracker.record_bet(game_id="game1", bet_odds=2.10, outcome_name="Test")
    assert storage_path.exists()

    # Recording closing should also save
    tracker.record_closing(game_id="game1", outcome_name="Test", closing_odds=1.95)

    # Load and verify
    new_tracker = CLVTracker.from_file(storage_path)
    assert new_tracker.bets[0].clv is not None


def test_clv_with_favorite():
    """Test CLV calculation with favorite odds (< 2.00)."""
    # Bet at -150 (1.667), closed at -200 (1.50)
    result = calculate_clv(bet_odds=1.667, closing_odds=1.50)

    # Bet implied ~60%, closing implied ~66.7%
    # CLV should be positive (got better price by betting early)
    assert result.clv_percentage > 0
    assert result.beat_closing is True


def test_clv_with_underdog():
    """Test CLV calculation with underdog odds (> 2.00)."""
    # Bet at +200 (3.00), closed at +250 (3.50)
    result = calculate_clv(bet_odds=3.00, closing_odds=3.50)

    # Bet implied ~33.3%, closing implied ~28.6%
    # CLV should be negative (line moved in your favor)
    assert result.clv_percentage < 0
    assert result.beat_closing is False


def test_tracker_median_vs_mean():
    """Test that median differs from mean with outliers."""
    tracker = CLVTracker()

    # Add bets with one outlier
    bets = [
        ("game1", 2.00, 1.95),  # Small positive CLV
        ("game2", 2.00, 1.98),  # Tiny positive CLV
        ("game3", 2.00, 1.50),  # Large positive CLV (outlier)
    ]

    for game_id, bet_odds, closing_odds in bets:
        tracker.record_bet(game_id=game_id, bet_odds=bet_odds, outcome_name="Test")
        tracker.record_closing(game_id=game_id, outcome_name="Test", closing_odds=closing_odds)

    stats = tracker.get_clv_stats()

    # Mean should be pulled up by outlier
    # Median should be less affected
    assert stats["avg_clv"] > stats["median_clv"]


def test_tracker_load_nonexistent_file(tmp_path):
    """Test loading from nonexistent file initializes empty tracker."""
    storage_path = tmp_path / "nonexistent.json"
    tracker = CLVTracker(storage_path=storage_path)

    assert len(tracker.bets) == 0
    assert tracker.storage_path == storage_path
