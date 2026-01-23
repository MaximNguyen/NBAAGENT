"""Tests for vig removal module.

Validates margin-proportional vig removal for converting bookmaker odds
to fair probabilities. Tests standard lines, edge cases, and Market integration.
"""

import warnings

import pytest

from nba_betting_agent.agents.analysis_agent.vig_removal import (
    calculate_fair_odds,
    get_market_vig,
    remove_vig,
)
from nba_betting_agent.agents.lines_agent.models import Market, Outcome


class TestRemoveVig:
    """Tests for remove_vig function."""

    def test_standard_vig_removal_even_odds(self):
        """Standard -110/-110 line should return 50/50 fair odds."""
        # Standard juice: -110 each side = 1.909 decimal
        fair_odds, fair_probs = remove_vig([1.909, 1.909])

        # Should be very close to 2.0 (50/50)
        assert abs(fair_odds[0] - 2.0) < 0.001
        assert abs(fair_odds[1] - 2.0) < 0.001

        # Fair probs should be 0.5 each
        assert abs(fair_probs[0] - 0.5) < 0.001
        assert abs(fair_probs[1] - 0.5) < 0.001

        # Must sum to 1.0
        assert abs(sum(fair_probs) - 1.0) < 1e-10

    def test_vig_removal_favorite_underdog(self):
        """Test vig removal with favorite and underdog."""
        # Favorite -150 (1.667) vs Underdog +130 (2.30)
        fair_odds, fair_probs = remove_vig([1.667, 2.30])

        # Fair probs must sum to 1.0
        assert abs(sum(fair_probs) - 1.0) < 1e-10

        # Fair odds should be higher than market odds (vig removed)
        assert fair_odds[0] > 1.667
        assert fair_odds[1] > 2.30

        # Favorite should still have higher probability
        assert fair_probs[0] > fair_probs[1]

    def test_three_way_market(self):
        """Test vig removal for three-way market (e.g., win/loss/draw)."""
        # Three outcomes
        fair_odds, fair_probs = remove_vig([2.5, 3.0, 4.0])

        # Must sum to 1.0
        assert abs(sum(fair_probs) - 1.0) < 1e-10

        # Fair odds should be higher (vig removed)
        assert fair_odds[0] > 2.5
        assert fair_odds[1] > 3.0
        assert fair_odds[2] > 4.0

        # Probabilities should be ordered correctly
        assert fair_probs[0] > fair_probs[1] > fair_probs[2]

    def test_zero_vig_market(self):
        """Market with no vig should return unchanged odds."""
        # Perfect 50/50 line with no vig
        fair_odds, fair_probs = remove_vig([2.0, 2.0])

        # Should be exactly 2.0 and 0.5
        assert abs(fair_odds[0] - 2.0) < 1e-10
        assert abs(fair_odds[1] - 2.0) < 1e-10
        assert abs(fair_probs[0] - 0.5) < 1e-10
        assert abs(fair_probs[1] - 0.5) < 1e-10

    def test_high_vig_market(self):
        """Test with high vig percentage (8%+)."""
        # Recreational book with high margins
        # -120/-120 = 1.833 each = 109.1% total (9.1% vig)
        fair_odds, fair_probs = remove_vig([1.833, 1.833])

        # Should return 50/50 fair odds
        assert abs(fair_odds[0] - 2.0) < 0.001
        assert abs(fair_odds[1] - 2.0) < 0.001
        assert abs(fair_probs[0] - 0.5) < 0.001
        assert abs(fair_probs[1] - 0.5) < 0.001

    def test_invalid_single_outcome(self):
        """Single outcome should raise ValueError."""
        with pytest.raises(ValueError, match="at least 2 outcomes"):
            remove_vig([2.0])

    def test_invalid_zero_odds(self):
        """Zero odds should raise ValueError."""
        with pytest.raises(ValueError, match="must be positive"):
            remove_vig([0.0, 2.0])

    def test_invalid_negative_odds(self):
        """Negative odds should raise ValueError."""
        with pytest.raises(ValueError, match="must be positive"):
            remove_vig([-1.5, 2.0])

    def test_very_high_odds_warning(self):
        """Very high odds should trigger warning."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            fair_odds, fair_probs = remove_vig([2.0, 150.0])

            # Should get warning about high odds
            assert len(w) == 1
            assert "Very high decimal odds" in str(w[0].message)
            assert "150.0" in str(w[0].message)

            # But calculation should still work
            assert abs(sum(fair_probs) - 1.0) < 1e-10

    def test_empty_list(self):
        """Empty odds list should raise ValueError."""
        with pytest.raises(ValueError, match="at least 2 outcomes"):
            remove_vig([])

    def test_four_way_market(self):
        """Test with four outcomes."""
        fair_odds, fair_probs = remove_vig([3.0, 4.0, 5.0, 6.0])

        # Must sum to 1.0
        assert abs(sum(fair_probs) - 1.0) < 1e-10

        # All fair odds should be higher
        assert fair_odds[0] > 3.0
        assert fair_odds[1] > 4.0
        assert fair_odds[2] > 5.0
        assert fair_odds[3] > 6.0


class TestGetMarketVig:
    """Tests for get_market_vig function."""

    def test_standard_vig_calculation(self):
        """Standard -110/-110 should have ~4.76% vig."""
        vig = get_market_vig([1.909, 1.909])

        # Should be close to 4.76%
        assert abs(vig - 4.76) < 0.1

    def test_zero_vig(self):
        """Perfect fair odds should have 0% vig."""
        vig = get_market_vig([2.0, 2.0])
        assert abs(vig) < 1e-10

    def test_high_vig(self):
        """High margin book should show high vig."""
        # -120/-120 = ~9.1% vig
        vig = get_market_vig([1.833, 1.833])
        assert vig > 9.0
        assert vig < 10.0

    def test_three_way_vig(self):
        """Three-way market vig calculation."""
        vig = get_market_vig([2.5, 3.0, 4.0])
        # Should be positive (bookmaker always has margin)
        assert vig > 0

    def test_invalid_single_outcome_vig(self):
        """Single outcome should raise ValueError."""
        with pytest.raises(ValueError, match="at least 2 outcomes"):
            get_market_vig([2.0])

    def test_invalid_zero_odds_vig(self):
        """Zero odds should raise ValueError."""
        with pytest.raises(ValueError, match="must be positive"):
            get_market_vig([0.0, 2.0])


class TestCalculateFairOdds:
    """Tests for calculate_fair_odds function with Market integration."""

    def test_calculate_fair_odds_with_market(self):
        """Test Market model integration."""
        market = Market(
            key="h2h",
            outcomes=[
                Outcome(name="Lakers", price=1.909),
                Outcome(name="Celtics", price=1.909),
            ],
        )

        result = calculate_fair_odds(market)

        # Should have both teams
        assert "Lakers" in result
        assert "Celtics" in result

        # Check Lakers fair odds
        lakers = result["Lakers"]
        assert abs(lakers["fair_odds"] - 2.0) < 0.001
        assert abs(lakers["fair_prob"] - 0.5) < 0.001
        assert lakers["market_odds"] == 1.909
        assert abs(lakers["vig_pct"] - 4.76) < 0.1

        # Check Celtics fair odds
        celtics = result["Celtics"]
        assert abs(celtics["fair_odds"] - 2.0) < 0.001
        assert abs(celtics["fair_prob"] - 0.5) < 0.001

    def test_calculate_fair_odds_favorite_underdog(self):
        """Test with favorite and underdog."""
        market = Market(
            key="h2h",
            outcomes=[
                Outcome(name="Warriors", price=1.667),  # -150 favorite
                Outcome(name="Blazers", price=2.30),  # +130 underdog
            ],
        )

        result = calculate_fair_odds(market)

        # Favorite should have higher probability
        assert result["Warriors"]["fair_prob"] > result["Blazers"]["fair_prob"]

        # Both should have same vig percentage
        assert result["Warriors"]["vig_pct"] == result["Blazers"]["vig_pct"]

        # Fair odds should be better than market odds
        assert result["Warriors"]["fair_odds"] > result["Warriors"]["market_odds"]
        assert result["Blazers"]["fair_odds"] > result["Blazers"]["market_odds"]

    def test_calculate_fair_odds_totals_market(self):
        """Test with totals (over/under) market."""
        market = Market(
            key="totals",
            outcomes=[
                Outcome(name="Over", price=1.909, point=220.5),
                Outcome(name="Under", price=1.909, point=220.5),
            ],
        )

        result = calculate_fair_odds(market)

        # Should have Over and Under
        assert "Over" in result
        assert "Under" in result

        # Should be 50/50
        assert abs(result["Over"]["fair_prob"] - 0.5) < 0.001
        assert abs(result["Under"]["fair_prob"] - 0.5) < 0.001

    def test_calculate_fair_odds_three_outcomes(self):
        """Test with three-outcome market."""
        market = Market(
            key="h2h",
            outcomes=[
                Outcome(name="Win", price=2.5),
                Outcome(name="Loss", price=3.0),
                Outcome(name="Draw", price=4.0),
            ],
        )

        result = calculate_fair_odds(market)

        # All three outcomes present
        assert len(result) == 3
        assert "Win" in result
        assert "Loss" in result
        assert "Draw" in result

        # Probabilities should sum to 1.0
        total_prob = sum(outcome["fair_prob"] for outcome in result.values())
        assert abs(total_prob - 1.0) < 1e-10

        # All should have same vig percentage
        vigs = [outcome["vig_pct"] for outcome in result.values()]
        assert all(abs(v - vigs[0]) < 1e-10 for v in vigs)
