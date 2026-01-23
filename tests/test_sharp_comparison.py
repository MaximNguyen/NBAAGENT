"""Tests for sharp vs soft book comparison module."""

from datetime import datetime, timezone

import pytest

from nba_betting_agent.agents.analysis_agent.sharp_comparison import (
    SHARP_BOOKS,
    SOFT_BOOKS,
    SharpSoftComparison,
    compare_sharp_soft,
    find_soft_book_edges,
    get_best_odds,
)
from nba_betting_agent.agents.lines_agent.models import (
    BookmakerOdds,
    GameOdds,
    Market,
    Outcome,
)


def test_compare_sharp_soft_basic():
    """Test basic sharp vs soft comparison with even odds."""
    # Sharp: -110/-110 (1.909), Soft: -110/-110 (1.909)
    sharp_odds = [1.909, 1.909]
    soft_odds = [1.909, 1.909]
    names = ["Home", "Away"]

    comparisons = compare_sharp_soft(sharp_odds, soft_odds, names)

    assert len(comparisons) == 2
    # When odds are identical, edge should be near 0
    assert abs(comparisons[0].edge_pct) < 0.01
    assert abs(comparisons[1].edge_pct) < 0.01
    assert not comparisons[0].is_value
    assert not comparisons[1].is_value


def test_compare_sharp_soft_finds_edge():
    """Test detecting value when soft book offers better odds."""
    # Sharp: -110/-110 (1.909), Soft: +105/-125 (2.05, 1.80)
    sharp_odds = [1.909, 1.909]
    soft_odds = [2.05, 1.80]  # Home better, away worse
    names = ["Home", "Away"]

    comparisons = compare_sharp_soft(sharp_odds, soft_odds, names)

    # Home should have positive edge (soft more generous)
    assert comparisons[0].outcome_name == "Home"
    assert comparisons[0].edge_pct > 0
    assert comparisons[0].is_value

    # Away should have negative edge (soft less generous)
    assert comparisons[1].outcome_name == "Away"
    assert comparisons[1].edge_pct < 0
    assert not comparisons[1].is_value


def test_compare_sharp_soft_no_edge():
    """Test when soft book offers worse odds than sharp."""
    # Sharp: +110/+110 (2.10), Soft: +100/+100 (2.00)
    sharp_odds = [2.10, 2.10]
    soft_odds = [2.00, 2.00]  # Worse odds
    names = ["Home", "Away"]

    comparisons = compare_sharp_soft(sharp_odds, soft_odds, names)

    # Both should have negative edge
    assert comparisons[0].edge_pct < 0
    assert comparisons[1].edge_pct < 0
    assert not comparisons[0].is_value
    assert not comparisons[1].is_value


def test_find_soft_book_edges_with_pinnacle():
    """Test finding edges when Pinnacle (sharp book) is available."""
    # Create mock GameOdds with Pinnacle and DraftKings
    game_odds = GameOdds(
        id="test_game_1",
        sport_key="basketball_nba",
        commence_time=datetime.now(timezone.utc),
        home_team="Boston Celtics",
        away_team="Los Angeles Lakers",
        bookmakers=[
            BookmakerOdds(
                key="pinnacle",
                title="Pinnacle",
                markets=[
                    Market(
                        key="h2h",
                        outcomes=[
                            Outcome(name="Boston Celtics", price=1.909),
                            Outcome(name="Los Angeles Lakers", price=1.909),
                        ],
                    )
                ],
                last_update=datetime.now(timezone.utc),
            ),
            BookmakerOdds(
                key="draftkings",
                title="DraftKings",
                markets=[
                    Market(
                        key="h2h",
                        outcomes=[
                            Outcome(name="Boston Celtics", price=2.05),  # Better odds
                            Outcome(name="Los Angeles Lakers", price=1.80),  # Worse odds
                        ],
                    )
                ],
                last_update=datetime.now(timezone.utc),
            ),
        ],
    )

    edges = find_soft_book_edges(game_odds, market_key="h2h", min_edge_pct=0.5)

    # Should find edge on Celtics (better odds at DraftKings)
    assert len(edges) >= 1
    celtics_edge = next((e for e in edges if e.outcome_name == "Boston Celtics"), None)
    assert celtics_edge is not None
    assert celtics_edge.edge_pct > 0
    assert celtics_edge.is_value
    assert celtics_edge.sharp_book == "pinnacle"
    assert celtics_edge.soft_book == "draftkings"


def test_find_soft_book_edges_no_sharp():
    """Test graceful handling when no sharp book available."""
    # Create GameOdds with only soft books
    game_odds = GameOdds(
        id="test_game_2",
        sport_key="basketball_nba",
        commence_time=datetime.now(timezone.utc),
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
                            Outcome(name="Boston Celtics", price=1.909),
                            Outcome(name="Los Angeles Lakers", price=1.909),
                        ],
                    )
                ],
                last_update=datetime.now(timezone.utc),
            ),
        ],
    )

    edges = find_soft_book_edges(game_odds)

    # Should return empty list (no sharp book to compare against)
    assert edges == []


def test_find_soft_book_edges_filters_by_threshold():
    """Test that only edges >= min_edge_pct are returned."""
    game_odds = GameOdds(
        id="test_game_3",
        sport_key="basketball_nba",
        commence_time=datetime.now(timezone.utc),
        home_team="Boston Celtics",
        away_team="Los Angeles Lakers",
        bookmakers=[
            BookmakerOdds(
                key="pinnacle",
                title="Pinnacle",
                markets=[
                    Market(
                        key="h2h",
                        outcomes=[
                            Outcome(name="Boston Celtics", price=1.95),
                            Outcome(name="Los Angeles Lakers", price=1.95),
                        ],
                    )
                ],
                last_update=datetime.now(timezone.utc),
            ),
            BookmakerOdds(
                key="draftkings",
                title="DraftKings",
                markets=[
                    Market(
                        key="h2h",
                        outcomes=[
                            Outcome(name="Boston Celtics", price=1.96),  # Tiny edge
                            Outcome(name="Los Angeles Lakers", price=1.94),
                        ],
                    )
                ],
                last_update=datetime.now(timezone.utc),
            ),
        ],
    )

    # With high threshold, should find nothing
    edges = find_soft_book_edges(game_odds, min_edge_pct=5.0)
    assert len(edges) == 0

    # With low threshold, should find small edges
    edges = find_soft_book_edges(game_odds, min_edge_pct=0.1)
    assert len(edges) >= 1


def test_get_best_odds_finds_highest():
    """Test that get_best_odds correctly identifies best bookmaker."""
    game_odds = GameOdds(
        id="test_game_4",
        sport_key="basketball_nba",
        commence_time=datetime.now(timezone.utc),
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
                            Outcome(name="Boston Celtics", price=1.95),
                            Outcome(name="Los Angeles Lakers", price=2.00),
                        ],
                    )
                ],
                last_update=datetime.now(timezone.utc),
            ),
            BookmakerOdds(
                key="fanduel",
                title="FanDuel",
                markets=[
                    Market(
                        key="h2h",
                        outcomes=[
                            Outcome(name="Boston Celtics", price=2.05),  # Best for Celtics
                            Outcome(name="Los Angeles Lakers", price=1.90),
                        ],
                    )
                ],
                last_update=datetime.now(timezone.utc),
            ),
        ],
    )

    book, odds = get_best_odds(game_odds, "h2h", "Boston Celtics")

    assert book == "fanduel"
    assert odds == 2.05


def test_sharp_books_constant():
    """Test that SHARP_BOOKS contains expected books."""
    assert "pinnacle" in SHARP_BOOKS
    assert "circa" in SHARP_BOOKS
    assert "bookmaker" in SHARP_BOOKS
    assert len(SHARP_BOOKS) >= 3


def test_soft_books_constant():
    """Test that SOFT_BOOKS contains expected books."""
    assert "draftkings" in SOFT_BOOKS
    assert "fanduel" in SOFT_BOOKS
    assert "betmgm" in SOFT_BOOKS
    assert len(SOFT_BOOKS) >= 3


def test_compare_with_totals_market():
    """Test comparison works with totals (over/under) market."""
    # Sharp totals odds
    sharp_odds = [1.909, 1.909]  # Over/Under at -110
    soft_odds = [1.95, 1.87]  # Over better, under worse
    names = ["Over 220.5", "Under 220.5"]

    comparisons = compare_sharp_soft(sharp_odds, soft_odds, names)

    assert len(comparisons) == 2
    assert comparisons[0].outcome_name == "Over 220.5"
    assert comparisons[1].outcome_name == "Under 220.5"
    # Over has positive edge
    assert comparisons[0].edge_pct > 0


def test_compare_with_spreads_market():
    """Test comparison works with point spreads."""
    sharp_odds = [1.909, 1.909]  # Both -110 on spread
    soft_odds = [2.00, 1.83]  # Home spread better odds
    names = ["Boston Celtics -3.5", "Los Angeles Lakers +3.5"]

    comparisons = compare_sharp_soft(sharp_odds, soft_odds, names)

    assert len(comparisons) == 2
    # Celtics spread has edge
    assert comparisons[0].edge_pct > 0
    # Lakers spread has negative edge
    assert comparisons[1].edge_pct < 0


def test_edge_calculation_accuracy():
    """Verify edge percentage calculation math."""
    # Sharp fair odds after vig removal: 2.0 each (50% each)
    # Soft offers 2.10 (47.6% implied)
    # Edge = (0.50 - 0.476) / 0.50 * 100 = 4.8%
    sharp_odds = [2.0, 2.0]  # Already fair (no vig)
    soft_odds = [2.10, 1.92]  # Better on outcome 1
    names = ["A", "B"]

    comparisons = compare_sharp_soft(sharp_odds, soft_odds, names)

    # Check edge calculation
    expected_edge = ((0.50 - (1 / 2.10)) / 0.50) * 100
    assert abs(comparisons[0].edge_pct - expected_edge) < 0.01


def test_comparison_fields():
    """Test that all SharpSoftComparison fields are populated correctly."""
    sharp_odds = [1.909, 1.909]
    soft_odds = [2.05, 1.80]
    names = ["Home", "Away"]

    comparisons = compare_sharp_soft(
        sharp_odds,
        soft_odds,
        names,
        sharp_book="pinnacle",
        soft_book="draftkings",
    )

    comp = comparisons[0]
    assert comp.sharp_book == "pinnacle"
    assert comp.soft_book == "draftkings"
    assert comp.outcome_name == "Home"
    assert comp.sharp_odds == 1.909
    assert comp.soft_odds == 2.05
    assert comp.sharp_fair_prob > 0
    assert comp.soft_implied_prob > 0
    assert isinstance(comp.edge_pct, float)
    assert isinstance(comp.is_value, bool)


def test_find_edges_sorts_by_edge_descending():
    """Test that edges are returned sorted by edge_pct descending."""
    game_odds = GameOdds(
        id="test_game_5",
        sport_key="basketball_nba",
        commence_time=datetime.now(timezone.utc),
        home_team="Boston Celtics",
        away_team="Los Angeles Lakers",
        bookmakers=[
            BookmakerOdds(
                key="pinnacle",
                title="Pinnacle",
                markets=[
                    Market(
                        key="h2h",
                        outcomes=[
                            Outcome(name="Boston Celtics", price=1.95),
                            Outcome(name="Los Angeles Lakers", price=1.95),
                        ],
                    )
                ],
                last_update=datetime.now(timezone.utc),
            ),
            BookmakerOdds(
                key="draftkings",
                title="DraftKings",
                markets=[
                    Market(
                        key="h2h",
                        outcomes=[
                            Outcome(name="Boston Celtics", price=2.10),  # Bigger edge
                            Outcome(name="Los Angeles Lakers", price=1.90),
                        ],
                    )
                ],
                last_update=datetime.now(timezone.utc),
            ),
            BookmakerOdds(
                key="fanduel",
                title="FanDuel",
                markets=[
                    Market(
                        key="h2h",
                        outcomes=[
                            Outcome(name="Boston Celtics", price=2.00),  # Smaller edge
                            Outcome(name="Los Angeles Lakers", price=1.85),
                        ],
                    )
                ],
                last_update=datetime.now(timezone.utc),
            ),
        ],
    )

    edges = find_soft_book_edges(game_odds, min_edge_pct=0.1)

    # Should be sorted by edge_pct descending
    for i in range(len(edges) - 1):
        assert edges[i].edge_pct >= edges[i + 1].edge_pct
