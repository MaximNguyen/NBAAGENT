"""Tests for odds normalizer functions and Pydantic models.

These tests PROVE the success criteria:
1. American odds convert correctly (positive and negative)
2. Decimal odds convert to implied probability
3. Pydantic models validate odds >= 1.0
4. Invalid odds raise ValidationError
"""

from datetime import datetime

import pytest
from pydantic import ValidationError

from nba_betting_agent.agents.lines_agent.models import (
    Outcome,
    Market,
    BookmakerOdds,
    GameOdds,
)
from nba_betting_agent.agents.lines_agent.normalizer import (
    american_to_decimal,
    decimal_to_implied_probability,
    normalize_odds,
)


# =============================================================================
# Normalizer Tests
# =============================================================================


class TestAmericanToDecimal:
    """Tests for american_to_decimal conversion function."""

    def test_positive_odds_basic(self):
        """Test positive American odds convert correctly.

        +200 means win $200 on $100 bet = $300 total payout / $100 stake = 3.0
        """
        assert american_to_decimal(200) == 3.0

    def test_positive_odds_various(self):
        """Test various positive American odds."""
        # +150: win $150 on $100 = $250 total / $100 = 2.5
        assert american_to_decimal(150) == 2.5

        # +100: even money, win $100 on $100 = $200 / $100 = 2.0
        assert american_to_decimal(100) == 2.0

        # +400: longshot, win $400 on $100 = $500 / $100 = 5.0
        assert american_to_decimal(400) == 5.0

    def test_negative_odds_basic(self):
        """Test negative American odds convert correctly.

        -200 means risk $200 to win $100 = $300 total on $200 = 1.5
        """
        assert american_to_decimal(-200) == 1.5

    def test_negative_odds_standard_vig(self):
        """Test standard vig line -110 converts correctly.

        -110: risk $110 to win $100 = (100/110) + 1 = 1.909...
        """
        result = american_to_decimal(-110)
        assert abs(result - 1.909090909) < 0.001

    def test_negative_odds_various(self):
        """Test various negative American odds."""
        # -150: risk $150 to win $100 = 100/150 + 1 = 1.667
        result = american_to_decimal(-150)
        assert abs(result - 1.6667) < 0.001

        # -300: heavy favorite, risk $300 to win $100 = 100/300 + 1 = 1.333
        result = american_to_decimal(-300)
        assert abs(result - 1.3333) < 0.001


class TestDecimalToImpliedProbability:
    """Tests for decimal_to_implied_probability conversion."""

    def test_even_money(self):
        """Test 2.0 decimal odds = 50% implied probability."""
        assert decimal_to_implied_probability(2.0) == 0.5

    def test_favorite(self):
        """Test favorite odds convert correctly.

        1.5 decimal = 1/1.5 = 0.6667 (66.67% implied probability)
        """
        result = decimal_to_implied_probability(1.5)
        assert abs(result - 0.6667) < 0.001

    def test_underdog(self):
        """Test underdog odds convert correctly.

        3.0 decimal = 1/3 = 0.3333 (33.33% implied probability)
        """
        result = decimal_to_implied_probability(3.0)
        assert abs(result - 0.3333) < 0.001


class TestNormalizeOdds:
    """Tests for the normalize_odds main entry point."""

    def test_american_format(self):
        """Test American format is converted via american_to_decimal."""
        assert normalize_odds(-200, "american") == 1.5
        assert normalize_odds(200, "american") == 3.0

    def test_decimal_format_passthrough(self):
        """Test decimal format returns input as float."""
        assert normalize_odds(2.5, "decimal") == 2.5
        assert normalize_odds(1.5, "decimal") == 1.5

    def test_decimal_format_converts_int(self):
        """Test decimal format converts int to float."""
        result = normalize_odds(2, "decimal")
        assert result == 2.0
        assert isinstance(result, float)

    def test_unknown_format_raises(self):
        """Test unknown format raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            normalize_odds(100, "fractional")

        assert "Unknown odds format" in str(exc_info.value)
        assert "fractional" in str(exc_info.value)


# =============================================================================
# Model Tests
# =============================================================================


class TestOutcomeModel:
    """Tests for Outcome Pydantic model."""

    def test_valid_price_accepted(self):
        """Test that valid decimal odds (>= 1.0) are accepted."""
        outcome = Outcome(name="Los Angeles Lakers", price=2.0)
        assert outcome.name == "Los Angeles Lakers"
        assert outcome.price == 2.0

    def test_valid_price_with_point(self):
        """Test outcome with point value for spreads/totals."""
        outcome = Outcome(name="Over", price=1.91, point=220.5)
        assert outcome.point == 220.5

    def test_invalid_price_rejected(self):
        """Test that invalid decimal odds (< 1.0) raise ValidationError.

        Decimal odds represent total payout per unit, so minimum is 1.0
        (break even - you get your stake back).
        """
        with pytest.raises(ValidationError) as exc_info:
            Outcome(name="Invalid Team", price=0.5)

        # Verify error message is helpful
        error_str = str(exc_info.value)
        assert "1.0" in error_str or "Decimal odds must be >= 1.0" in error_str

    def test_edge_case_price_exactly_one(self):
        """Test that price exactly 1.0 is accepted (break even)."""
        outcome = Outcome(name="Edge Case", price=1.0)
        assert outcome.price == 1.0

    def test_high_price_warns(self):
        """Test that suspiciously high odds trigger a warning."""
        with pytest.warns(UserWarning, match="Suspiciously high"):
            Outcome(name="Longshot", price=150.0)


class TestGameOddsFullStructure:
    """Tests for complete GameOdds model with nested structures."""

    def test_full_game_odds_structure(self):
        """Test creating a complete GameOdds object with all nested models.

        This validates the entire data hierarchy works correctly.
        """
        game_odds = GameOdds(
            id="abc123",
            sport_key="basketball_nba",
            commence_time=datetime(2026, 1, 24, 19, 30),
            home_team="Los Angeles Lakers",
            away_team="Boston Celtics",
            bookmakers=[
                BookmakerOdds(
                    key="draftkings",
                    title="DraftKings",
                    last_update=datetime(2026, 1, 24, 15, 0),
                    markets=[
                        Market(
                            key="h2h",
                            outcomes=[
                                Outcome(name="Los Angeles Lakers", price=2.10),
                                Outcome(name="Boston Celtics", price=1.75),
                            ],
                        ),
                        Market(
                            key="spreads",
                            outcomes=[
                                Outcome(
                                    name="Los Angeles Lakers", price=1.91, point=3.5
                                ),
                                Outcome(
                                    name="Boston Celtics", price=1.91, point=-3.5
                                ),
                            ],
                        ),
                        Market(
                            key="totals",
                            outcomes=[
                                Outcome(name="Over", price=1.87, point=220.5),
                                Outcome(name="Under", price=1.95, point=220.5),
                            ],
                        ),
                    ],
                ),
                BookmakerOdds(
                    key="fanduel",
                    title="FanDuel",
                    last_update=datetime(2026, 1, 24, 14, 55),
                    markets=[
                        Market(
                            key="h2h",
                            outcomes=[
                                Outcome(name="Los Angeles Lakers", price=2.15),
                                Outcome(name="Boston Celtics", price=1.72),
                            ],
                        ),
                    ],
                ),
            ],
        )

        # Verify top-level fields
        assert game_odds.id == "abc123"
        assert game_odds.home_team == "Los Angeles Lakers"
        assert game_odds.away_team == "Boston Celtics"

        # Verify bookmakers
        assert len(game_odds.bookmakers) == 2
        assert game_odds.bookmakers[0].key == "draftkings"
        assert game_odds.bookmakers[1].key == "fanduel"

        # Verify markets
        dk_markets = game_odds.bookmakers[0].markets
        assert len(dk_markets) == 3
        assert dk_markets[0].key == "h2h"
        assert dk_markets[1].key == "spreads"
        assert dk_markets[2].key == "totals"

        # Verify outcomes
        h2h_outcomes = dk_markets[0].outcomes
        assert len(h2h_outcomes) == 2
        assert h2h_outcomes[0].name == "Los Angeles Lakers"
        assert h2h_outcomes[0].price == 2.10

        # Verify spread points
        spreads_outcomes = dk_markets[1].outcomes
        assert spreads_outcomes[0].point == 3.5
        assert spreads_outcomes[1].point == -3.5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
