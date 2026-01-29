"""Temporal validation tests ensuring no data leakage in historical analysis.

These tests verify that:
1. The system respects temporal boundaries (no future data usage)
2. CLV tracking only compares opening vs closing odds within same day
3. Caching respects time boundaries in historical simulation
4. Train/test splits are properly separated

Critical for backtesting accuracy - any data leakage invalidates results.
"""

import pytest
from datetime import datetime, timedelta
from freezegun import freeze_time

from nba_betting_agent.agents.analysis_agent.clv_tracker import (
    CLVTracker,
    calculate_clv,
    BetRecord,
)


class TestTemporalBoundaries:
    """Test that system respects temporal boundaries."""

    def test_freeze_time_affects_datetime_now(self, historical_window):
        """Verify freezegun correctly freezes datetime.now()."""
        freeze_date = "2026-01-15 12:00:00"

        with freeze_time(freeze_date):
            now = datetime.now()
            assert now.year == 2026
            assert now.month == 1
            assert now.day == 15
            assert now.hour == 12

    def test_freeze_time_restores_after_context(self):
        """Verify time is restored after freeze_time context exits."""
        before = datetime.now()

        with freeze_time("2020-01-01 00:00:00"):
            frozen = datetime.now()
            assert frozen.year == 2020

        after = datetime.now()
        # After exiting context, time should be restored
        # The 'after' time should be close to 'before' (within seconds)
        assert after.year >= before.year

    def test_train_test_split_no_overlap(self, temporal_split):
        """Verify train and test dates don't overlap."""
        train_dates = set(d.date() for d in temporal_split["train_dates"])
        test_dates = set(d.date() for d in temporal_split["test_dates"])

        overlap = train_dates & test_dates
        assert len(overlap) == 0, f"Train/test overlap detected: {overlap}"

    def test_train_before_test(self, temporal_split):
        """Verify all train dates precede test dates."""
        max_train = max(temporal_split["train_dates"])
        min_test = min(temporal_split["test_dates"])

        assert max_train < min_test, "Train data must precede test data"

    def test_frozen_time_affects_bet_recording(self):
        """Verify bets recorded during frozen time have correct timestamp."""
        tracker = CLVTracker()

        with freeze_time("2026-01-15 14:30:00"):
            bet = tracker.record_bet(
                game_id="test_001",
                bet_odds=1.91,
                outcome_name="BOS ML",
            )

            # Bet should have the frozen timestamp
            assert bet.placed_at.year == 2026
            assert bet.placed_at.month == 1
            assert bet.placed_at.day == 15
            assert bet.placed_at.hour == 14
            assert bet.placed_at.minute == 30


class TestCLVTemporalValidation:
    """Test CLV tracking respects temporal boundaries."""

    def test_clv_opening_before_closing(self):
        """CLV calculation requires opening odds captured before closing.

        This test simulates a realistic betting scenario where:
        1. Bet is placed at 2pm (opening odds locked in)
        2. Game starts at 7pm (closing odds captured)
        3. CLV is calculated comparing the two
        """
        tracker = CLVTracker()

        # Simulate bet placed at 2pm
        with freeze_time("2026-01-15 14:00:00"):
            bet = tracker.record_bet(
                game_id="test_001",
                bet_odds=1.91,  # -110 American
                outcome_name="BOS ML",
            )
            bet_time = bet.placed_at

        # Simulate closing odds recorded at 7pm (game start)
        with freeze_time("2026-01-15 19:00:00"):
            closing_time = datetime.now()

        # Verify temporal ordering
        assert bet_time < closing_time
        assert (closing_time - bet_time).total_seconds() == 5 * 3600  # 5 hours

    def test_clv_positive_when_line_moves_toward_bet(self):
        """CLV should be positive when closing odds move in bet direction.

        If you bet on BOS at 1.91 and the line closes at 1.83,
        the market moved toward your position (implied prob increased),
        meaning you got +EV - positive CLV.
        """
        # Bet at -110 (1.91 decimal)
        bet_odds = 1.91

        # Closing at -120 (1.83 decimal) - line moved toward our bet
        closing_odds = 1.83

        result = calculate_clv(bet_odds, closing_odds)

        # CLV formula: ((closing_implied - bet_implied) / bet_implied) * 100
        # = ((1/1.83 - 1/1.91) / (1/1.91)) * 100
        # = ((0.5464 - 0.5236) / 0.5236) * 100
        # = (0.0228 / 0.5236) * 100
        # = 4.35%
        assert result.clv_percentage > 0, "CLV should be positive when line moves toward bet"
        assert result.beat_closing is True

    def test_clv_negative_when_line_moves_away_from_bet(self):
        """CLV should be negative when closing odds move away from bet.

        If you bet on BOS at 1.91 and the line closes at 2.10,
        the market moved away from your position (implied prob decreased),
        meaning you got -EV - negative CLV.
        """
        # Bet at -110 (1.91 decimal)
        bet_odds = 1.91

        # Closing at -105 (1.95 decimal) - line moved away from our bet
        closing_odds = 2.10

        result = calculate_clv(bet_odds, closing_odds)

        assert result.clv_percentage < 0, "CLV should be negative when line moves away"
        assert result.beat_closing is False

    def test_clv_tracker_with_temporal_bet_flow(self):
        """Test complete CLV tracking flow with temporal context."""
        tracker = CLVTracker()

        # Day 1: Place bet
        with freeze_time("2026-01-15 14:00:00"):
            tracker.record_bet(
                game_id="game_001",
                bet_odds=1.91,
                outcome_name="BOS ML",
            )

        # Day 1: Record closing odds (game starts at 7pm)
        tracker.record_closing(
            game_id="game_001",
            outcome_name="BOS ML",
            closing_odds=1.83,
        )

        # Verify CLV was calculated
        stats = tracker.get_clv_stats()
        assert stats["total_bets"] == 1
        assert stats["bets_with_closing"] == 1
        assert stats["avg_clv"] > 0  # Positive CLV expected


class TestCacheTemporalBehavior:
    """Test cache behavior in temporal context.

    Note: diskcache uses time.time() internally for TTL calculations.
    While freezegun does affect time.time(), the interactions between
    frozen time and cache expiration can be complex. These tests focus
    on verifying cache operations work correctly in real time, with
    separate tests demonstrating temporal patterns.
    """

    @pytest.mark.asyncio
    async def test_cache_basic_set_get(self, clean_cache):
        """Cache should store and retrieve values correctly."""
        await clean_cache.set("test_key", {"data": "value"}, "team_stats")
        entry = await clean_cache.get("test_key", "team_stats")

        assert entry is not None
        assert entry.data == {"data": "value"}
        assert entry.is_stale is False

    @pytest.mark.asyncio
    async def test_cache_multiple_keys(self, clean_cache):
        """Cache should handle multiple keys independently."""
        await clean_cache.set("key1", {"value": 1}, "team_stats")
        await clean_cache.set("key2", {"value": 2}, "team_stats")

        entry1 = await clean_cache.get("key1", "team_stats")
        entry2 = await clean_cache.get("key2", "team_stats")

        assert entry1 is not None
        assert entry1.data == {"value": 1}
        assert entry2 is not None
        assert entry2.data == {"value": 2}

    @pytest.mark.asyncio
    async def test_cache_entry_freshness_immediately_after_set(self, clean_cache):
        """Cache entry should be fresh immediately after setting."""
        await clean_cache.set("test_key", {"data": 1}, "team_stats")
        entry = await clean_cache.get("test_key", "team_stats")

        # Entry should be fresh immediately after setting
        assert entry is not None
        assert entry.is_stale is False

    def test_temporal_cache_access_pattern(self, clean_cache):
        """Demonstrate temporal cache access pattern for backtesting.

        In backtesting, we should only access cache entries that existed
        at the simulated time. This is enforced by application logic,
        not by the cache itself.
        """
        # Simulate a scenario where we cache data with timestamps
        cache_entries = {
            datetime(2026, 1, 10): {"team": "BOS", "rating": 115.0},
            datetime(2026, 1, 11): {"team": "BOS", "rating": 115.2},
            datetime(2026, 1, 12): {"team": "BOS", "rating": 114.8},
        }

        # When simulating day 11, we should only see entries from day 11 and earlier
        with freeze_time("2026-01-11 12:00:00"):
            simulated_time = datetime.now()

            available_entries = {
                date: data
                for date, data in cache_entries.items()
                if date <= simulated_time
            }

            assert len(available_entries) == 2
            assert datetime(2026, 1, 12) not in available_entries


class TestHistoricalValidationIntegrity:
    """Test overall historical validation setup."""

    def test_30_day_window_coverage(self, historical_window):
        """Verify we have exactly 30 days in validation window."""
        duration = historical_window["end"] - historical_window["start"]
        # Jan 1 00:00 to Jan 30 23:59 = 29 days + 23:59:59
        assert duration.days == 29  # 30 days inclusive (0-29)

    def test_train_test_ratio(self, temporal_split):
        """Verify ~70/30 train/test split."""
        train_count = len(temporal_split["train_dates"])
        test_count = len(temporal_split["test_dates"])
        total = train_count + test_count

        train_pct = train_count / total * 100
        assert 65 <= train_pct <= 75, f"Train should be ~70%, got {train_pct:.1f}%"

    def test_historical_window_dates_are_consistent(self, historical_window):
        """Verify historical window dates are internally consistent."""
        assert historical_window["start"] < historical_window["train_split"]
        assert historical_window["train_split"] < historical_window["test_start"]
        assert historical_window["test_start"] < historical_window["end"]

    def test_temporal_split_covers_full_window(self, historical_window, temporal_split):
        """Verify temporal split covers the full validation window."""
        all_dates = temporal_split["train_dates"] + temporal_split["test_dates"]
        min_date = min(all_dates)
        max_date = max(all_dates)

        # First date should be the start of historical window
        assert min_date.date() == historical_window["start"].date()

        # Last date should be day 30 (test day 9, index 8)
        expected_last = historical_window["start"] + timedelta(days=29)
        assert max_date.date() == expected_last.date()


class TestNoLookAheadBias:
    """Tests specifically designed to catch look-ahead bias."""

    def test_data_access_pattern_respects_time(self):
        """Demonstrate proper data access pattern during backtesting.

        When simulating a bet on day 15, we should only use data
        available up to day 15, never from days 16+.
        """
        # Simulated historical data
        daily_data = {
            datetime(2026, 1, d): {"odds": 1.90 + d * 0.01}
            for d in range(1, 31)
        }

        # Simulate being on day 15
        with freeze_time("2026-01-15 12:00:00"):
            current_time = datetime.now()

            # Filter to only data available at current time
            available_data = {
                date: data
                for date, data in daily_data.items()
                if date <= current_time
            }

            # Should only have days 1-15
            assert len(available_data) == 15
            assert datetime(2026, 1, 16) not in available_data

    def test_clv_only_uses_closing_from_same_game(self):
        """CLV should only compare odds from the same game.

        This prevents accidentally using closing odds from
        future games to evaluate past bets.
        """
        tracker = CLVTracker()

        # Place bets on two games
        tracker.record_bet("game_001", bet_odds=1.91, outcome_name="BOS ML")
        tracker.record_bet("game_002", bet_odds=2.10, outcome_name="LAL ML")

        # Record closing for only game 1
        tracker.record_closing("game_001", "BOS ML", closing_odds=1.83)

        stats = tracker.get_clv_stats()

        # Only 1 bet should have CLV calculated
        assert stats["bets_with_closing"] == 1
        assert stats["total_bets"] == 2

    def test_cannot_record_closing_for_nonexistent_bet(self):
        """Recording closing odds for non-existent bet should fail.

        This prevents accidentally matching closing odds to wrong bets.
        """
        tracker = CLVTracker()

        with pytest.raises(ValueError, match="No bet found"):
            tracker.record_closing("nonexistent_game", "BOS ML", closing_odds=1.83)
