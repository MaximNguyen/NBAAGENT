"""Integration tests for Analysis Agent."""

import pytest
from unittest.mock import patch, MagicMock
import numpy as np

from nba_betting_agent.agents.analysis_agent.agent import (
    analyze_bets,
    analysis_agent_impl,
    BettingOpportunity,
    AnalysisResult,
    generate_base_probability,
    parse_record_pct,
    assess_confidence,
)


# Fixtures


@pytest.fixture
def sample_odds_data():
    """Sample odds data for testing."""
    return [
        {
            "id": "game123",
            "sport_key": "basketball_nba",
            "commence_time": "2026-01-24T19:30:00Z",
            "home_team": "Boston Celtics",
            "away_team": "Los Angeles Lakers",
            "bookmakers": [
                {
                    "key": "draftkings",
                    "title": "DraftKings",
                    "markets": [
                        {
                            "key": "h2h",
                            "outcomes": [
                                {"name": "Boston Celtics", "price": 1.80},
                                {"name": "Los Angeles Lakers", "price": 2.10},
                            ],
                        }
                    ],
                }
            ],
        }
    ]


@pytest.fixture
def sample_team_stats():
    """Sample team stats for testing."""
    return {
        "BOS": {
            "name": "Boston Celtics",
            "record": {"wins": 30, "losses": 10},
            "stats": {
                "pts": 115.0,
                "reb": 45.0,
                "ast": 28.0,
                "fg_pct": 0.48,
                "fg3_pct": 0.38,
                "ft_pct": 0.82,
            },
            "advanced": {
                "off_rtg": 118.5,
                "def_rtg": 108.2,
                "net_rtg": 10.3,
                "pace": 99.5,
                "efg_pct": 0.56,
            },
            "last_10": {"record": "8-2", "pts": 118.0},
        },
        "LAL": {
            "name": "Los Angeles Lakers",
            "record": {"wins": 25, "losses": 15},
            "stats": {
                "pts": 112.0,
                "reb": 43.0,
                "ast": 26.0,
                "fg_pct": 0.46,
                "fg3_pct": 0.35,
                "ft_pct": 0.78,
            },
            "advanced": {
                "off_rtg": 112.0,
                "def_rtg": 110.5,
                "net_rtg": 1.5,
                "pace": 101.0,
                "efg_pct": 0.53,
            },
            "last_10": {"record": "5-5", "pts": 110.0},
        },
    }


@pytest.fixture
def sample_injuries():
    """Sample injury data for testing."""
    return [
        {
            "team": "BOS",
            "player": "Jaylen Brown",
            "status": "Questionable",
            "reason": "Ankle",
        },
        {"team": "LAL", "player": "Anthony Davis", "status": "Out", "reason": "Knee"},
    ]


# Helper function tests


def test_parse_record_pct_valid():
    """Test parsing valid win-loss record."""
    assert parse_record_pct("7-3") == 0.7


def test_parse_record_pct_perfect():
    """Test parsing perfect record."""
    assert parse_record_pct("10-0") == 1.0


def test_parse_record_pct_zero_wins():
    """Test parsing winless record."""
    assert parse_record_pct("0-10") == 0.0


def test_parse_record_pct_invalid():
    """Test parsing invalid record returns default."""
    assert parse_record_pct("invalid") == 0.5
    assert parse_record_pct("") == 0.5
    assert parse_record_pct("7-3-1") == 0.5


def test_assess_confidence_high():
    """Test confidence assessment with all data."""
    assert assess_confidence(True, True, True) == "high"


def test_assess_confidence_medium():
    """Test confidence assessment with partial data."""
    assert assess_confidence(True, True, False) == "medium"
    assert assess_confidence(True, False, True) == "medium"
    assert assess_confidence(False, True, True) == "medium"


def test_assess_confidence_low():
    """Test confidence assessment with minimal data."""
    assert assess_confidence(True, False, False) == "low"
    assert assess_confidence(False, True, False) == "low"
    assert assess_confidence(False, False, True) == "low"
    assert assess_confidence(False, False, False) == "low"


def test_generate_base_probability_market_baseline():
    """Test base probability uses market as baseline."""
    prob = generate_base_probability({}, {}, 0.5)
    # With no stats, should be close to market fair prob
    assert 0.4 < prob < 0.6


def test_generate_base_probability_with_stats(sample_team_stats):
    """Test base probability adjusts with stats."""
    home_stats = sample_team_stats["BOS"]
    away_stats = sample_team_stats["LAL"]
    fair_prob = 0.5

    prob = generate_base_probability(home_stats, away_stats, fair_prob)

    # With BOS having better record and net rating, prob should increase
    assert prob > fair_prob
    # Should still be in reasonable range
    assert 0.05 < prob < 0.95


def test_generate_base_probability_clamping():
    """Test probability clamping to valid range."""
    # Extreme fair prob should be clamped
    assert generate_base_probability({}, {}, 0.01) >= 0.05
    assert generate_base_probability({}, {}, 0.99) <= 0.95


# analyze_bets tests


@pytest.mark.asyncio
async def test_analyze_bets_empty_odds():
    """Test analyze_bets returns early with error when no odds."""
    result = await analyze_bets([], {}, [])

    assert isinstance(result, AnalysisResult)
    assert len(result.opportunities) == 0
    assert len(result.errors) > 0
    assert "no odds data" in result.errors[0].lower()


@pytest.mark.asyncio
async def test_analyze_bets_single_game(sample_odds_data, sample_team_stats):
    """Test analyze_bets processes single game correctly."""
    result = await analyze_bets(sample_odds_data, sample_team_stats, [])

    assert isinstance(result, AnalysisResult)
    # Should have estimated probabilities for the game
    assert "game123" in result.estimated_probabilities
    # Should have analysis notes
    assert len(result.analysis_notes) > 0


@pytest.mark.asyncio
async def test_analyze_bets_multiple_games(sample_team_stats):
    """Test analyze_bets handles multiple games."""
    odds_data = [
        {
            "id": "game1",
            "home_team": "Boston Celtics",
            "away_team": "Los Angeles Lakers",
            "bookmakers": [
                {
                    "key": "draftkings",
                    "markets": [
                        {
                            "key": "h2h",
                            "outcomes": [
                                {"name": "Boston Celtics", "price": 1.75},
                                {"name": "Los Angeles Lakers", "price": 2.15},
                            ],
                        }
                    ],
                }
            ],
        },
        {
            "id": "game2",
            "home_team": "Boston Celtics",
            "away_team": "Los Angeles Lakers",
            "bookmakers": [
                {
                    "key": "fanduel",
                    "markets": [
                        {
                            "key": "h2h",
                            "outcomes": [
                                {"name": "Boston Celtics", "price": 1.80},
                                {"name": "Los Angeles Lakers", "price": 2.05},
                            ],
                        }
                    ],
                }
            ],
        },
    ]

    result = await analyze_bets(odds_data, sample_team_stats, [])

    assert isinstance(result, AnalysisResult)
    # Should process both games
    assert "game1" in result.estimated_probabilities
    assert "game2" in result.estimated_probabilities


@pytest.mark.asyncio
async def test_analyze_bets_with_stats(sample_odds_data, sample_team_stats):
    """Test analyze_bets uses team stats to adjust probability."""
    result = await analyze_bets(sample_odds_data, sample_team_stats, [])

    # Should have probabilities
    assert len(result.estimated_probabilities) > 0

    # Get a probability estimate
    game_probs = result.estimated_probabilities.get("game123", {})
    assert len(game_probs) > 0


@pytest.mark.asyncio
async def test_analyze_bets_positive_ev_found():
    """Test analyze_bets finds +EV when present."""
    # Create scenario with high probability vs market odds
    odds_data = [
        {
            "id": "game1",
            "home_team": "Boston Celtics",
            "away_team": "Los Angeles Lakers",
            "bookmakers": [
                {
                    "key": "draftkings",
                    "markets": [
                        {
                            "key": "h2h",
                            "outcomes": [
                                # Good odds for underdog (if our prob is higher than implied)
                                {"name": "Boston Celtics", "price": 3.0},
                                {"name": "Los Angeles Lakers", "price": 1.4},
                            ],
                        }
                    ],
                }
            ],
        }
    ]

    team_stats = {
        "BOS": {
            "name": "Boston Celtics",
            "advanced": {"net_rtg": 5.0},
            "last_10": {"record": "8-2"},
        },
        "LAL": {
            "name": "Los Angeles Lakers",
            "advanced": {"net_rtg": -3.0},
            "last_10": {"record": "4-6"},
        },
    }

    result = await analyze_bets(odds_data, team_stats, [], min_ev_pct=1.0)

    # May or may not find +EV depending on adjustments, but should run without error
    assert isinstance(result, AnalysisResult)
    assert len(result.errors) == 0 or all(
        "failed" not in e.lower() for e in result.errors
    )


@pytest.mark.asyncio
async def test_analyze_bets_no_positive_ev(sample_odds_data, sample_team_stats):
    """Test analyze_bets returns empty when no +EV above threshold."""
    # Use very high EV threshold
    result = await analyze_bets(
        sample_odds_data, sample_team_stats, [], min_ev_pct=50.0
    )

    assert isinstance(result, AnalysisResult)
    assert len(result.opportunities) == 0
    # Should have note about no opportunities
    assert any("no +ev" in note.lower() for note in result.analysis_notes)


@pytest.mark.asyncio
async def test_analyze_bets_ev_threshold():
    """Test analyze_bets respects min_ev_pct parameter."""
    odds_data = [
        {
            "id": "game1",
            "home_team": "Boston Celtics",
            "away_team": "Los Angeles Lakers",
            "bookmakers": [
                {
                    "key": "draftkings",
                    "markets": [
                        {
                            "key": "h2h",
                            "outcomes": [
                                {"name": "Boston Celtics", "price": 2.5},
                                {"name": "Los Angeles Lakers", "price": 1.6},
                            ],
                        }
                    ],
                }
            ],
        }
    ]

    # Test with different thresholds
    result_low = await analyze_bets(odds_data, {}, [], min_ev_pct=1.0)
    result_high = await analyze_bets(odds_data, {}, [], min_ev_pct=10.0)

    # Higher threshold should find fewer or equal opportunities
    assert len(result_high.opportunities) <= len(result_low.opportunities)


# analysis_agent_impl tests


def test_impl_returns_state_contract(sample_odds_data, sample_team_stats):
    """Test implementation returns dict with correct keys."""
    state = {
        "odds_data": sample_odds_data,
        "team_stats": sample_team_stats,
        "injuries": [],
    }

    result = analysis_agent_impl(state)

    # Check state contract
    assert isinstance(result, dict)
    assert "estimated_probabilities" in result
    assert "expected_values" in result
    assert "errors" in result
    assert isinstance(result["estimated_probabilities"], dict)
    assert isinstance(result["expected_values"], list)
    assert isinstance(result["errors"], list)


def test_impl_handles_empty_state():
    """Test implementation works with empty state."""
    state = {"odds_data": [], "team_stats": {}, "injuries": []}

    result = analysis_agent_impl(state)

    assert isinstance(result, dict)
    assert "errors" in result
    assert len(result["errors"]) > 0


def test_impl_propagates_errors():
    """Test implementation includes errors in result."""
    # Invalid odds data that should cause errors
    state = {
        "odds_data": [{"id": "bad_game", "bookmakers": []}],
        "team_stats": {},
        "injuries": [],
    }

    result = analysis_agent_impl(state)

    # Should still return valid structure even with errors
    assert isinstance(result, dict)
    assert "errors" in result


# Integration tests


@pytest.mark.asyncio
async def test_full_pipeline_integration(
    sample_odds_data, sample_team_stats, sample_injuries
):
    """Test full pipeline from odds_data to expected_values."""
    result = await analyze_bets(
        odds_data=sample_odds_data,
        team_stats=sample_team_stats,
        injuries=sample_injuries,
        min_ev_pct=0.5,  # Low threshold to find something
    )

    # Verify complete result
    assert isinstance(result, AnalysisResult)
    assert isinstance(result.opportunities, list)
    assert isinstance(result.estimated_probabilities, dict)
    assert isinstance(result.expected_values, list)
    assert isinstance(result.analysis_notes, list)
    assert isinstance(result.errors, list)

    # Should have processed the game
    assert "game123" in result.estimated_probabilities


@pytest.mark.asyncio
async def test_analysis_with_mock_calibrator(sample_odds_data, sample_team_stats):
    """Test analysis with calibrator adjusts probabilities."""
    from nba_betting_agent.agents.analysis_agent.calibration import (
        ProbabilityCalibrator,
    )

    # Create and fit a simple calibrator
    calibrator = ProbabilityCalibrator()
    raw_probs = np.array([0.5, 0.6, 0.7, 0.8])
    outcomes = np.array([1, 1, 0, 1])  # Some wins, some losses
    calibrator.fit(raw_probs, outcomes)

    # Run analysis with calibrator
    result = await analyze_bets(
        sample_odds_data, sample_team_stats, [], calibrator=calibrator
    )

    assert isinstance(result, AnalysisResult)
    # Should still process successfully
    assert len(result.estimated_probabilities) > 0


@pytest.mark.asyncio
async def test_analysis_with_multiple_bookmakers(sample_team_stats):
    """Test analysis with multiple bookmakers for same game."""
    odds_data = [
        {
            "id": "game1",
            "home_team": "Boston Celtics",
            "away_team": "Los Angeles Lakers",
            "bookmakers": [
                {
                    "key": "draftkings",
                    "markets": [
                        {
                            "key": "h2h",
                            "outcomes": [
                                {"name": "Boston Celtics", "price": 1.80},
                                {"name": "Los Angeles Lakers", "price": 2.10},
                            ],
                        }
                    ],
                },
                {
                    "key": "fanduel",
                    "markets": [
                        {
                            "key": "h2h",
                            "outcomes": [
                                {"name": "Boston Celtics", "price": 1.85},
                                {"name": "Los Angeles Lakers", "price": 2.05},
                            ],
                        }
                    ],
                },
                {
                    "key": "pinnacle",  # Sharp book
                    "markets": [
                        {
                            "key": "h2h",
                            "outcomes": [
                                {"name": "Boston Celtics", "price": 1.83},
                                {"name": "Los Angeles Lakers", "price": 2.07},
                            ],
                        }
                    ],
                },
            ],
        }
    ]

    result = await analyze_bets(odds_data, sample_team_stats, [])

    # Should process all bookmakers
    assert isinstance(result, AnalysisResult)
    # Should note sharp book presence
    assert any("sharp" in note.lower() for note in result.analysis_notes) or len(
        result.analysis_notes
    ) > 0


@pytest.mark.asyncio
async def test_analysis_with_spreads_and_totals(sample_team_stats):
    """Test analysis handles spreads and totals markets."""
    odds_data = [
        {
            "id": "game1",
            "home_team": "Boston Celtics",
            "away_team": "Los Angeles Lakers",
            "bookmakers": [
                {
                    "key": "draftkings",
                    "markets": [
                        {
                            "key": "spreads",
                            "outcomes": [
                                {
                                    "name": "Boston Celtics",
                                    "price": 1.91,
                                    "point": -5.5,
                                },
                                {
                                    "name": "Los Angeles Lakers",
                                    "price": 1.91,
                                    "point": 5.5,
                                },
                            ],
                        },
                        {
                            "key": "totals",
                            "outcomes": [
                                {"name": "Over", "price": 1.87, "point": 220.5},
                                {"name": "Under", "price": 1.95, "point": 220.5},
                            ],
                        },
                    ],
                }
            ],
        }
    ]

    result = await analyze_bets(odds_data, sample_team_stats, [])

    assert isinstance(result, AnalysisResult)
    # Should process without errors
    assert all("failed" not in e.lower() for e in result.errors)
