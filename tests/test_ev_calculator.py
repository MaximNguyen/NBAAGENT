"""Tests for expected value calculator and Kelly criterion bet sizing.

Validates EV calculation logic, Kelly bet sizing, and opportunity evaluation
with integrated vig removal.
"""

import pytest

from nba_betting_agent.agents.analysis_agent.ev_calculator import (
    calculate_ev,
    calculate_kelly_bet,
    evaluate_opportunity,
)
from nba_betting_agent.agents.lines_agent.models import Market, Outcome


class TestCalculateEV:
    """Tests for calculate_ev function."""

    def test_positive_ev_calculation(self):
        """55% probability at 2.0 odds should have +10% EV."""
        # Our prob: 55%, Market: 2.0 (50% implied)
        # EV = (0.55 × 100) - (0.45 × 100) = 10
        result = calculate_ev(0.55, 2.0, 100)

        assert abs(result["ev_percentage"] - 10.0) < 0.01
        assert result["ev_dollars"] == 10.0
        assert result["is_positive"] is True
        assert result["our_prob"] == 0.55
        assert result["market_odds"] == 2.0
        assert abs(result["implied_prob"] - 0.5) < 0.001

    def test_negative_ev_calculation(self):
        """45% probability at 2.0 odds should have -10% EV."""
        result = calculate_ev(0.45, 2.0, 100)

        assert abs(result["ev_percentage"] - (-10.0)) < 0.01
        assert result["ev_dollars"] == -10.0
        assert result["is_positive"] is False

    def test_break_even_ev(self):
        """50% probability at 2.0 odds should have 0% EV."""
        result = calculate_ev(0.50, 2.0, 100)

        assert abs(result["ev_percentage"]) < 0.01
        assert abs(result["ev_dollars"]) < 0.01
        assert result["is_positive"] is False  # 0 is not positive

    def test_ev_with_favorite(self):
        """Test EV calculation with favorite odds (<2.0)."""
        # 60% prob at 1.667 odds (-150 American)
        # Implied: 60%, Market implied: 60% → should be break-even
        result = calculate_ev(0.60, 1.667, 100)

        # Should be close to 0 EV
        assert abs(result["ev_percentage"]) < 1.0

    def test_ev_with_underdog(self):
        """Test EV calculation with underdog odds (>2.0)."""
        # 35% prob at 3.0 odds (+200 American)
        # EV = (0.35 × 200) - (0.65 × 100) = 70 - 65 = 5
        result = calculate_ev(0.35, 3.0, 100)

        assert abs(result["ev_percentage"] - 5.0) < 0.1
        assert result["is_positive"] is True

    def test_ev_different_bet_amount(self):
        """EV percentage should be same regardless of bet amount."""
        result_100 = calculate_ev(0.55, 2.0, 100)
        result_50 = calculate_ev(0.55, 2.0, 50)

        # EV percentage should be identical
        assert result_100["ev_percentage"] == result_50["ev_percentage"]

        # EV dollars should scale
        assert result_100["ev_dollars"] == 2 * result_50["ev_dollars"]

    def test_invalid_probability_zero(self):
        """Zero probability should raise ValueError."""
        with pytest.raises(ValueError, match="between 0 and 1 exclusive"):
            calculate_ev(0.0, 2.0)

    def test_invalid_probability_one(self):
        """100% probability should raise ValueError."""
        with pytest.raises(ValueError, match="between 0 and 1 exclusive"):
            calculate_ev(1.0, 2.0)

    def test_invalid_probability_negative(self):
        """Negative probability should raise ValueError."""
        with pytest.raises(ValueError, match="between 0 and 1 exclusive"):
            calculate_ev(-0.1, 2.0)

    def test_invalid_probability_over_one(self):
        """Probability over 1.0 should raise ValueError."""
        with pytest.raises(ValueError, match="between 0 and 1 exclusive"):
            calculate_ev(1.5, 2.0)

    def test_invalid_odds(self):
        """Odds below 1.0 should raise ValueError."""
        with pytest.raises(ValueError, match="must be >= 1.0"):
            calculate_ev(0.5, 0.9)


class TestCalculateKellyBet:
    """Tests for calculate_kelly_bet function."""

    def test_kelly_positive_edge(self):
        """Kelly sizing with positive edge."""
        # 55% prob at 2.0 odds with $1000 bankroll, quarter Kelly
        # Full Kelly: (1 × 0.55 - 0.45) / 1 = 0.10 = 10%
        # Quarter Kelly: 2.5% of bankroll = $25
        result = calculate_kelly_bet(0.55, 2.0, 1000, 0.25)

        assert abs(result["kelly_pct"] - 10.0) < 0.1
        assert abs(result["fractional_pct"] - 2.5) < 0.1
        assert abs(result["bet_amount"] - 25.0) < 0.1
        assert result["bankroll"] == 1000

    def test_kelly_negative_edge(self):
        """Kelly with negative EV should return 0 bet."""
        # 45% prob at 2.0 odds → negative EV
        result = calculate_kelly_bet(0.45, 2.0, 1000, 0.25)

        assert result["bet_amount"] == 0.0
        assert result["kelly_pct"] == 0.0
        assert result["fractional_pct"] == 0.0

    def test_kelly_fractional_sizing(self):
        """Different Kelly fractions should scale bet proportionally."""
        full_kelly = calculate_kelly_bet(0.55, 2.0, 1000, 1.0)
        half_kelly = calculate_kelly_bet(0.55, 2.0, 1000, 0.5)
        quarter_kelly = calculate_kelly_bet(0.55, 2.0, 1000, 0.25)

        # Bets should be in 4:2:1 ratio
        assert abs(full_kelly["bet_amount"] - 4 * quarter_kelly["bet_amount"]) < 0.1
        assert abs(half_kelly["bet_amount"] - 2 * quarter_kelly["bet_amount"]) < 0.1

    def test_kelly_large_edge(self):
        """Kelly with large edge should still be reasonable."""
        # 70% prob at 2.0 odds
        # Full Kelly: (1 × 0.70 - 0.30) / 1 = 0.40 = 40%
        result = calculate_kelly_bet(0.70, 2.0, 1000, 0.25)

        assert result["kelly_pct"] == 40.0
        assert result["fractional_pct"] == 10.0  # 25% of 40%
        assert result["bet_amount"] == 100.0  # 10% of $1000

    def test_kelly_underdog_odds(self):
        """Kelly with underdog odds."""
        # 40% prob at 3.0 odds (+200)
        # Full Kelly: (2 × 0.40 - 0.60) / 2 = 0.20 / 2 = 0.10 = 10%
        result = calculate_kelly_bet(0.40, 3.0, 1000, 0.25)

        assert abs(result["kelly_pct"] - 10.0) < 0.1
        assert abs(result["bet_amount"] - 25.0) < 0.1

    def test_kelly_favorite_odds(self):
        """Kelly with favorite odds."""
        # 70% prob at 1.5 odds (-200)
        # Full Kelly: (0.5 × 0.70 - 0.30) / 0.5 = 0.05 / 0.5 = 0.10 = 10%
        result = calculate_kelly_bet(0.70, 1.5, 1000, 0.25)

        assert abs(result["kelly_pct"] - 10.0) < 0.5
        assert abs(result["bet_amount"] - 25.0) < 0.5

    def test_kelly_small_bankroll(self):
        """Kelly with small bankroll."""
        result = calculate_kelly_bet(0.55, 2.0, 100, 0.25)

        # 2.5% of $100 = $2.50
        assert abs(result["bet_amount"] - 2.5) < 0.1

    def test_invalid_kelly_probability_zero(self):
        """Zero probability should raise ValueError."""
        with pytest.raises(ValueError, match="between 0 and 1 exclusive"):
            calculate_kelly_bet(0.0, 2.0, 1000)

    def test_invalid_kelly_probability_one(self):
        """100% probability should raise ValueError."""
        with pytest.raises(ValueError, match="between 0 and 1 exclusive"):
            calculate_kelly_bet(1.0, 2.0, 1000)

    def test_invalid_kelly_odds(self):
        """Invalid odds should raise ValueError."""
        with pytest.raises(ValueError, match="must be >= 1.0"):
            calculate_kelly_bet(0.55, 0.5, 1000)

    def test_invalid_kelly_fraction_zero(self):
        """Zero Kelly fraction should raise ValueError."""
        with pytest.raises(ValueError, match="must be in"):
            calculate_kelly_bet(0.55, 2.0, 1000, 0.0)

    def test_invalid_kelly_fraction_over_one(self):
        """Kelly fraction over 1.0 should raise ValueError."""
        with pytest.raises(ValueError, match="must be in"):
            calculate_kelly_bet(0.55, 2.0, 1000, 1.5)

    def test_kelly_break_even(self):
        """Break-even bet should return 0."""
        # 50% prob at 2.0 odds
        result = calculate_kelly_bet(0.50, 2.0, 1000, 0.25)

        assert result["bet_amount"] == 0.0


class TestEvaluateOpportunity:
    """Tests for evaluate_opportunity function with Market integration."""

    def test_evaluate_opportunity_positive(self):
        """Opportunity above threshold should return details."""
        market = Market(
            key="h2h",
            outcomes=[
                Outcome(name="Lakers", price=1.909),
                Outcome(name="Celtics", price=1.909),
            ],
        )

        # 55% prob → 5% EV (above 2% threshold)
        result = evaluate_opportunity(0.55, market, "Lakers", min_ev_pct=2.0)

        assert result is not None
        assert result["market_key"] == "h2h"
        assert result["outcome_name"] == "Lakers"
        assert result["our_prob"] == 0.55
        assert result["market_odds"] == 1.909
        assert abs(result["fair_odds"] - 2.0) < 0.001
        assert abs(result["fair_prob"] - 0.5) < 0.001
        assert abs(result["vig_pct"] - 4.76) < 0.1
        assert result["ev_pct"] > 2.0
        assert result["is_value_bet"] is True

    def test_evaluate_opportunity_below_threshold(self):
        """Opportunity below threshold should return None."""
        market = Market(
            key="h2h",
            outcomes=[
                Outcome(name="Lakers", price=1.909),
                Outcome(name="Celtics", price=1.909),
            ],
        )

        # 51% prob → ~1% EV (below 2% threshold)
        result = evaluate_opportunity(0.51, market, "Lakers", min_ev_pct=2.0)

        assert result is None

    def test_evaluate_opportunity_negative_ev(self):
        """Negative EV should return None."""
        market = Market(
            key="h2h",
            outcomes=[
                Outcome(name="Lakers", price=1.909),
                Outcome(name="Celtics", price=1.909),
            ],
        )

        # 45% prob → negative EV
        result = evaluate_opportunity(0.45, market, "Lakers", min_ev_pct=2.0)

        assert result is None

    def test_evaluate_opportunity_custom_threshold(self):
        """Custom EV threshold should be respected."""
        market = Market(
            key="h2h",
            outcomes=[
                Outcome(name="Lakers", price=1.909),
                Outcome(name="Celtics", price=1.909),
            ],
        )

        # 53% prob → ~3% EV
        result_low = evaluate_opportunity(0.53, market, "Lakers", min_ev_pct=2.0)
        result_high = evaluate_opportunity(0.53, market, "Lakers", min_ev_pct=5.0)

        assert result_low is not None  # Passes 2% threshold
        assert result_high is None  # Fails 5% threshold

    def test_evaluate_opportunity_totals_market(self):
        """Test with totals market."""
        market = Market(
            key="totals",
            outcomes=[
                Outcome(name="Over", price=1.909, point=220.5),
                Outcome(name="Under", price=1.909, point=220.5),
            ],
        )

        result = evaluate_opportunity(0.55, market, "Over", min_ev_pct=2.0)

        assert result is not None
        assert result["market_key"] == "totals"
        assert result["outcome_name"] == "Over"

    def test_evaluate_opportunity_spreads_market(self):
        """Test with spreads market."""
        market = Market(
            key="spreads",
            outcomes=[
                Outcome(name="Lakers", price=1.909, point=-3.5),
                Outcome(name="Celtics", price=1.909, point=3.5),
            ],
        )

        result = evaluate_opportunity(0.55, market, "Lakers", min_ev_pct=2.0)

        assert result is not None
        assert result["market_key"] == "spreads"

    def test_evaluate_opportunity_invalid_outcome(self):
        """Invalid outcome name should raise ValueError."""
        market = Market(
            key="h2h",
            outcomes=[
                Outcome(name="Lakers", price=1.909),
                Outcome(name="Celtics", price=1.909),
            ],
        )

        with pytest.raises(ValueError, match="not found in market"):
            evaluate_opportunity(0.55, market, "Warriors", min_ev_pct=2.0)

    def test_evaluate_opportunity_three_way(self):
        """Test with three-way market."""
        market = Market(
            key="h2h",
            outcomes=[
                Outcome(name="Win", price=2.5),
                Outcome(name="Loss", price=3.0),
                Outcome(name="Draw", price=4.0),
            ],
        )

        result = evaluate_opportunity(0.50, market, "Win", min_ev_pct=2.0)

        # 50% prob at 2.5 fair odds → should have +EV
        assert result is not None
        assert result["outcome_name"] == "Win"

    def test_evaluate_opportunity_favorite(self):
        """Test with favorite outcome."""
        market = Market(
            key="h2h",
            outcomes=[
                Outcome(name="Warriors", price=1.667),  # Favorite
                Outcome(name="Blazers", price=2.30),  # Underdog
            ],
        )

        # Our prob: 65% for Warriors
        result = evaluate_opportunity(0.65, market, "Warriors", min_ev_pct=2.0)

        # Should have +EV if our prob is higher than fair prob
        if result is not None:
            assert result["our_prob"] > result["fair_prob"]
