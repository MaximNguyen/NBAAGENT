"""Tests for line discrepancy detection.

Tests verify:
1. Discrepancy detection across bookmakers
2. Minimum difference threshold filtering
3. Arbitrage opportunity detection
4. Correct implied probability calculations
"""

from datetime import datetime

import pytest

from nba_betting_agent.agents.lines_agent.discrepancy import (
    LineDiscrepancy,
    find_discrepancies,
    check_arbitrage,
    find_best_odds_per_outcome,
)
from nba_betting_agent.agents.lines_agent.models import (
    GameOdds,
    BookmakerOdds,
    Market,
    Outcome,
)


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def sample_game_two_books() -> GameOdds:
    """Create game with two bookmakers having different h2h odds.

    DraftKings: Celtics 1.65 (60.6% implied), Lakers 2.30 (43.5% implied)
    FanDuel: Celtics 1.75 (57.1% implied), Lakers 2.15 (46.5% implied)

    Celtics discrepancy: 1.75 best, 1.65 worst
      - best_implied = 1/1.75 = 0.571 (57.1%)
      - worst_implied = 1/1.65 = 0.606 (60.6%)
      - diff = (0.606 - 0.571) * 100 = 3.5%

    Lakers discrepancy: 2.30 best, 2.15 worst
      - best_implied = 1/2.30 = 0.435 (43.5%)
      - worst_implied = 1/2.15 = 0.465 (46.5%)
      - diff = (0.465 - 0.435) * 100 = 3.0%
    """
    return GameOdds(
        id="game123",
        sport_key="basketball_nba",
        commence_time=datetime(2025, 1, 15, 19, 0),
        home_team="Boston Celtics",
        away_team="Los Angeles Lakers",
        bookmakers=[
            BookmakerOdds(
                key="draftkings",
                title="DraftKings",
                markets=[
                    Market(
                        key="h2h",
                        outcomes=[
                            Outcome(name="Boston Celtics", price=1.65),
                            Outcome(name="Los Angeles Lakers", price=2.30),
                        ],
                    )
                ],
                last_update=datetime(2025, 1, 15, 17, 0),
            ),
            BookmakerOdds(
                key="fanduel",
                title="FanDuel",
                markets=[
                    Market(
                        key="h2h",
                        outcomes=[
                            Outcome(name="Boston Celtics", price=1.75),
                            Outcome(name="Los Angeles Lakers", price=2.15),
                        ],
                    )
                ],
                last_update=datetime(2025, 1, 15, 17, 0),
            ),
        ],
    )


@pytest.fixture
def sample_game_with_spreads() -> GameOdds:
    """Create game with spread markets showing discrepancy.

    DraftKings: Celtics -5.5 @ 1.90, Lakers +5.5 @ 1.90
    FanDuel: Celtics -5.5 @ 2.00, Lakers +5.5 @ 1.85

    Celtics -5.5 discrepancy: 2.00 best, 1.90 worst
      - best_implied = 1/2.00 = 0.500 (50.0%)
      - worst_implied = 1/1.90 = 0.526 (52.6%)
      - diff = 2.6%
    """
    return GameOdds(
        id="game456",
        sport_key="basketball_nba",
        commence_time=datetime(2025, 1, 15, 19, 0),
        home_team="Boston Celtics",
        away_team="Los Angeles Lakers",
        bookmakers=[
            BookmakerOdds(
                key="draftkings",
                title="DraftKings",
                markets=[
                    Market(
                        key="spreads",
                        outcomes=[
                            Outcome(name="Boston Celtics", price=1.90, point=-5.5),
                            Outcome(name="Los Angeles Lakers", price=1.90, point=5.5),
                        ],
                    )
                ],
                last_update=datetime(2025, 1, 15, 17, 0),
            ),
            BookmakerOdds(
                key="fanduel",
                title="FanDuel",
                markets=[
                    Market(
                        key="spreads",
                        outcomes=[
                            Outcome(name="Boston Celtics", price=2.00, point=-5.5),
                            Outcome(name="Los Angeles Lakers", price=1.85, point=5.5),
                        ],
                    )
                ],
                last_update=datetime(2025, 1, 15, 17, 0),
            ),
        ],
    )


@pytest.fixture
def sample_game_no_discrepancy() -> GameOdds:
    """Create game where books have identical odds."""
    return GameOdds(
        id="game789",
        sport_key="basketball_nba",
        commence_time=datetime(2025, 1, 15, 19, 0),
        home_team="Boston Celtics",
        away_team="Los Angeles Lakers",
        bookmakers=[
            BookmakerOdds(
                key="draftkings",
                title="DraftKings",
                markets=[
                    Market(
                        key="h2h",
                        outcomes=[
                            Outcome(name="Boston Celtics", price=1.90),
                            Outcome(name="Los Angeles Lakers", price=1.90),
                        ],
                    )
                ],
                last_update=datetime(2025, 1, 15, 17, 0),
            ),
            BookmakerOdds(
                key="fanduel",
                title="FanDuel",
                markets=[
                    Market(
                        key="h2h",
                        outcomes=[
                            Outcome(name="Boston Celtics", price=1.90),
                            Outcome(name="Los Angeles Lakers", price=1.90),
                        ],
                    )
                ],
                last_update=datetime(2025, 1, 15, 17, 0),
            ),
        ],
    )


@pytest.fixture
def sample_game_small_discrepancy() -> GameOdds:
    """Create game with discrepancy below 2% threshold.

    DraftKings: Celtics 1.90 (52.6%)
    FanDuel: Celtics 1.92 (52.1%)
    Diff = 0.5% - below default 2% threshold
    """
    return GameOdds(
        id="game101",
        sport_key="basketball_nba",
        commence_time=datetime(2025, 1, 15, 19, 0),
        home_team="Boston Celtics",
        away_team="Los Angeles Lakers",
        bookmakers=[
            BookmakerOdds(
                key="draftkings",
                title="DraftKings",
                markets=[
                    Market(
                        key="h2h",
                        outcomes=[
                            Outcome(name="Boston Celtics", price=1.90),
                            Outcome(name="Los Angeles Lakers", price=1.90),
                        ],
                    )
                ],
                last_update=datetime(2025, 1, 15, 17, 0),
            ),
            BookmakerOdds(
                key="fanduel",
                title="FanDuel",
                markets=[
                    Market(
                        key="h2h",
                        outcomes=[
                            Outcome(name="Boston Celtics", price=1.92),
                            Outcome(name="Los Angeles Lakers", price=1.88),
                        ],
                    )
                ],
                last_update=datetime(2025, 1, 15, 17, 0),
            ),
        ],
    )


# ============================================================================
# find_discrepancies Tests
# ============================================================================


def test_find_discrepancies_basic(sample_game_two_books: GameOdds):
    """Test that discrepancies are detected between two bookmakers."""
    discrepancies = find_discrepancies(sample_game_two_books)

    # Should find discrepancies for both Celtics and Lakers
    assert len(discrepancies) == 2

    # Find Celtics discrepancy
    celtics_disc = next(d for d in discrepancies if d.outcome == "Boston Celtics")

    assert celtics_disc.game_id == "game123"
    assert celtics_disc.market == "h2h"
    assert celtics_disc.best_odds_book == "FanDuel"
    assert celtics_disc.best_odds == 1.75
    assert celtics_disc.worst_odds_book == "DraftKings"
    assert celtics_disc.worst_odds == 1.65
    # Diff should be approximately 3.5%
    assert 3.0 <= celtics_disc.implied_prob_diff <= 4.0


def test_find_discrepancies_respects_min_diff(sample_game_small_discrepancy: GameOdds):
    """Test that small discrepancies below threshold are filtered out."""
    # Default min_diff is 2%
    discrepancies = find_discrepancies(sample_game_small_discrepancy)
    assert len(discrepancies) == 0

    # With lower threshold, should find them
    discrepancies = find_discrepancies(sample_game_small_discrepancy, min_diff_pct=0.5)
    assert len(discrepancies) >= 1


def test_find_discrepancies_multiple_outcomes(sample_game_two_books: GameOdds):
    """Test that both sides of h2h market are analyzed."""
    discrepancies = find_discrepancies(sample_game_two_books)

    outcomes = {d.outcome for d in discrepancies}
    assert "Boston Celtics" in outcomes
    assert "Los Angeles Lakers" in outcomes


def test_find_discrepancies_spreads(sample_game_with_spreads: GameOdds):
    """Test that spread markets work with point values."""
    discrepancies = find_discrepancies(sample_game_with_spreads)

    # Should find at least one spread discrepancy
    assert len(discrepancies) >= 1

    # Check that spread discrepancies have point values
    celtics_disc = next(
        (d for d in discrepancies if d.outcome == "Boston Celtics"), None
    )
    if celtics_disc:
        assert celtics_disc.point == -5.5
        assert celtics_disc.market == "spreads"


def test_find_discrepancies_no_discrepancy(sample_game_no_discrepancy: GameOdds):
    """Test that identical odds return no discrepancies."""
    discrepancies = find_discrepancies(sample_game_no_discrepancy)
    assert len(discrepancies) == 0


# ============================================================================
# check_arbitrage Tests
# ============================================================================


def test_check_arbitrage_exists():
    """Test arbitrage detection when sum of implied probs < 1.0.

    Best odds: Team A @ 2.15 (46.5%), Team B @ 1.95 (51.3%)
    Total: 97.8% < 100% -> arbitrage exists with ~2.2% profit margin
    """
    outcomes = [("Team A", 2.15), ("Team B", 1.95)]
    is_arb, margin = check_arbitrage(outcomes)

    assert is_arb is True
    assert margin < 0  # Negative margin means profit
    # Should be approximately -2.2%
    assert -3.0 < margin < -1.0


def test_check_arbitrage_none():
    """Test that normal odds (with vig) return no arbitrage.

    Standard vig line: Both sides at 1.91
    Total implied: 2 * (1/1.91) = 104.7% > 100% -> no arbitrage
    """
    outcomes = [("Team A", 1.91), ("Team B", 1.91)]
    is_arb, margin = check_arbitrage(outcomes)

    assert is_arb is False
    assert margin > 0  # Positive margin means bookmaker edge


def test_check_arbitrage_empty():
    """Test handling of empty outcomes list."""
    is_arb, margin = check_arbitrage([])
    assert is_arb is False
    assert margin == 0.0


# ============================================================================
# LineDiscrepancy Tests
# ============================================================================


def test_line_discrepancy_fields():
    """Test that LineDiscrepancy dataclass has all required fields."""
    disc = LineDiscrepancy(
        game_id="game123",
        market="h2h",
        outcome="Boston Celtics",
        point=None,
        best_odds_book="FanDuel",
        best_odds=1.75,
        worst_odds_book="DraftKings",
        worst_odds=1.65,
        implied_prob_diff=3.5,
        is_arbitrage=False,
    )

    assert disc.game_id == "game123"
    assert disc.market == "h2h"
    assert disc.outcome == "Boston Celtics"
    assert disc.point is None
    assert disc.best_odds_book == "FanDuel"
    assert disc.best_odds == 1.75
    assert disc.worst_odds_book == "DraftKings"
    assert disc.worst_odds == 1.65
    assert disc.implied_prob_diff == 3.5
    assert disc.is_arbitrage is False


# ============================================================================
# find_best_odds_per_outcome Tests
# ============================================================================


def test_find_best_odds_per_outcome(sample_game_two_books: GameOdds):
    """Test finding best odds for each outcome in h2h market."""
    best_odds = find_best_odds_per_outcome(sample_game_two_books, "h2h")

    # Should have two outcomes
    assert len(best_odds) == 2

    # Celtics best is FanDuel @ 1.75
    assert "Boston Celtics" in best_odds
    celtics = best_odds["Boston Celtics"]
    assert celtics[0] == "FanDuel"  # bookmaker title
    assert celtics[1] == 1.75  # best odds

    # Lakers best is DraftKings @ 2.30
    assert "Los Angeles Lakers" in best_odds
    lakers = best_odds["Los Angeles Lakers"]
    assert lakers[0] == "DraftKings"
    assert lakers[1] == 2.30
