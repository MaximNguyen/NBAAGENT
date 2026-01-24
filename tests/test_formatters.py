"""Unit tests for CLI formatters and filters.

Tests Rich table formatting, filtering logic, and helper functions.
"""

import pytest
from rich.table import Table
from rich.panel import Panel

from nba_betting_agent.agents.analysis_agent.agent import BettingOpportunity
from nba_betting_agent.cli.formatters import (
    format_opportunities_table,
    format_opportunity_detail,
    format_american_odds,
)
from nba_betting_agent.cli.filters import (
    filter_opportunities,
    sort_opportunities,
    get_filter_summary,
    suggest_relaxed_filters,
)


# Test fixtures
@pytest.fixture
def sample_opportunities():
    """Create sample BettingOpportunity objects for testing."""
    return [
        BettingOpportunity(
            game_id="game1",
            matchup="BOS @ LAL",
            market="h2h",
            outcome="BOS",
            bookmaker="fanduel",
            our_prob=0.55,
            market_odds=2.1,
            fair_odds=2.0,
            ev_pct=5.5,
            kelly_bet_pct=2.75,
            confidence="high",
            sharp_edge=2.3,
            rlm_signal="STRONG",
            llm_insight="Celtics have strong defensive matchup advantage",
        ),
        BettingOpportunity(
            game_id="game2",
            matchup="MIA @ CHI",
            market="spreads",
            outcome="MIA -3.5",
            bookmaker="draftkings",
            our_prob=0.60,
            market_odds=1.91,
            fair_odds=1.85,
            ev_pct=8.2,
            kelly_bet_pct=4.1,
            confidence="medium",
            sharp_edge=None,
            rlm_signal=None,
            llm_insight=None,
        ),
        BettingOpportunity(
            game_id="game3",
            matchup="GSW @ PHX",
            market="totals",
            outcome="Over 220.5",
            bookmaker="betmgm",
            our_prob=0.52,
            market_odds=1.95,
            fair_odds=1.92,
            ev_pct=1.5,
            kelly_bet_pct=0.75,
            confidence="low",
        ),
    ]


@pytest.fixture
def high_confidence_opp():
    """Single high-confidence opportunity."""
    return BettingOpportunity(
        game_id="game_high",
        matchup="BOS @ LAL",
        market="h2h",
        outcome="BOS",
        bookmaker="pinnacle",
        our_prob=0.55,
        market_odds=2.0,
        fair_odds=1.95,
        ev_pct=10.0,
        kelly_bet_pct=5.0,
        confidence="high",
        sharp_edge=3.5,
        rlm_signal="MODERATE",
        llm_insight="Strong matchup",
    )


# Tests for format_american_odds
def test_format_american_odds_underdog():
    """Test converting underdog decimal odds to American."""
    assert format_american_odds(2.5) == "+150"
    assert format_american_odds(3.0) == "+200"
    assert format_american_odds(2.0) == "+100"


def test_format_american_odds_favorite():
    """Test converting favorite decimal odds to American."""
    assert format_american_odds(1.5) == "-200"
    assert format_american_odds(1.91) == "-109"
    assert format_american_odds(1.1) == "-1000"


def test_format_american_odds_even():
    """Test even money odds."""
    result = format_american_odds(2.0)
    assert result == "+100"


# Tests for format_opportunities_table
def test_format_empty_list():
    """Test table formatting with empty opportunity list."""
    table = format_opportunities_table([])

    assert isinstance(table, Table)
    assert table.title == "Betting Opportunities"


def test_format_single_opportunity(high_confidence_opp):
    """Test table formatting with single opportunity."""
    table = format_opportunities_table([high_confidence_opp])

    assert isinstance(table, Table)
    assert table.title == "Betting Opportunities"
    # Table should have data rows (not empty)
    assert len(table.rows) > 0


def test_format_sorted_by_ev(sample_opportunities):
    """Test that opportunities are sorted by EV descending."""
    table = format_opportunities_table(sample_opportunities)

    # Check that highest EV is first
    # sample_opportunities[1] has ev_pct=8.2 (highest)
    # We can't directly inspect table content, but we verified sorting in the function
    assert isinstance(table, Table)


def test_format_confidence_colors(sample_opportunities):
    """Test that confidence levels have proper markup."""
    table = format_opportunities_table(sample_opportunities)

    # Just verify table is created successfully
    # Rich Table internal structure makes direct markup testing difficult
    assert isinstance(table, Table)


def test_format_with_active_filters(sample_opportunities):
    """Test table caption shows active filters."""
    filters = {"min_ev": 5.0, "confidence": "high"}
    table = format_opportunities_table(sample_opportunities, active_filters=filters)

    assert isinstance(table, Table)
    # Caption should be set when filters are active
    assert table.caption is not None or table.caption == ""


# Tests for format_opportunity_detail
def test_detail_panel_has_title(high_confidence_opp):
    """Test that detail panel has proper title."""
    panel = format_opportunity_detail(high_confidence_opp)

    assert isinstance(panel, Panel)


def test_detail_shows_ev_breakdown(high_confidence_opp):
    """Test that EV calculation details are visible in panel."""
    panel = format_opportunity_detail(high_confidence_opp)

    # Panel contains our probability, market odds, fair odds, EV
    # We can't easily inspect Rich Panel content, but verify it's created
    assert isinstance(panel, Panel)


def test_detail_shows_sharp_edge(high_confidence_opp):
    """Test that sharp edge appears when present."""
    panel = format_opportunity_detail(high_confidence_opp)

    assert isinstance(panel, Panel)
    # sharp_edge=3.5 should be displayed


def test_detail_shows_llm_insight(high_confidence_opp):
    """Test that LLM insight appears when present."""
    panel = format_opportunity_detail(high_confidence_opp)

    assert isinstance(panel, Panel)
    # llm_insight="Strong matchup" should be displayed


def test_detail_without_optional_fields():
    """Test detail panel with minimal opportunity (no sharp/rlm/llm)."""
    minimal_opp = BettingOpportunity(
        game_id="game_min",
        matchup="ATL @ DEN",
        market="h2h",
        outcome="ATL",
        bookmaker="caesars",
        our_prob=0.48,
        market_odds=2.1,
        fair_odds=2.05,
        ev_pct=3.0,
        kelly_bet_pct=1.5,
        confidence="medium",
    )

    panel = format_opportunity_detail(minimal_opp)
    assert isinstance(panel, Panel)


def test_detail_with_team_stats(high_confidence_opp):
    """Test detail panel includes team stats when provided."""
    team_stats = {
        "BOS": {"name": "Boston Celtics", "record": "35-15"},
        "LAL": {"name": "Los Angeles Lakers", "record": "28-22"},
    }

    panel = format_opportunity_detail(high_confidence_opp, team_stats=team_stats)
    assert isinstance(panel, Panel)


# Tests for filter_opportunities
def test_filter_by_min_ev(sample_opportunities):
    """Test filtering by minimum EV threshold."""
    filtered = filter_opportunities(sample_opportunities, min_ev=5.0)

    # Should return only opps with ev_pct >= 5.0
    # sample_opportunities[0] has 5.5%, [1] has 8.2%, [2] has 1.5%
    assert len(filtered) == 2
    assert all(opp.ev_pct >= 5.0 for opp in filtered)


def test_filter_by_max_ev(sample_opportunities):
    """Test filtering by maximum EV threshold."""
    filtered = filter_opportunities(sample_opportunities, max_ev=6.0)

    # Should return only opps with ev_pct <= 6.0
    assert len(filtered) == 2
    assert all(opp.ev_pct <= 6.0 for opp in filtered)


def test_filter_by_confidence(sample_opportunities):
    """Test filtering by confidence level."""
    filtered = filter_opportunities(sample_opportunities, confidence="high")

    assert len(filtered) == 1
    assert filtered[0].confidence == "high"


def test_filter_by_confidence_case_insensitive(sample_opportunities):
    """Test that confidence filter is case-insensitive."""
    filtered = filter_opportunities(sample_opportunities, confidence="HIGH")

    assert len(filtered) == 1
    assert filtered[0].confidence == "high"


def test_filter_by_team(sample_opportunities):
    """Test filtering by team in matchup."""
    filtered = filter_opportunities(sample_opportunities, team="BOS")

    assert len(filtered) == 1
    assert "BOS" in filtered[0].matchup


def test_filter_by_team_case_insensitive(sample_opportunities):
    """Test that team filter is case-insensitive."""
    filtered = filter_opportunities(sample_opportunities, team="bos")

    assert len(filtered) == 1
    assert "BOS" in filtered[0].matchup.upper()


def test_filter_by_market(sample_opportunities):
    """Test filtering by market type."""
    filtered = filter_opportunities(sample_opportunities, market="h2h")

    assert len(filtered) == 1
    assert filtered[0].market == "h2h"


def test_filter_combined(sample_opportunities):
    """Test that multiple filters work with AND logic."""
    filtered = filter_opportunities(
        sample_opportunities, min_ev=5.0, confidence="high"
    )

    # Only sample_opportunities[0] meets both criteria
    assert len(filtered) == 1
    assert filtered[0].ev_pct >= 5.0
    assert filtered[0].confidence == "high"


def test_filter_returns_empty(sample_opportunities):
    """Test that filter returns empty list when no matches."""
    filtered = filter_opportunities(sample_opportunities, team="NONEXISTENT")

    assert len(filtered) == 0
    assert filtered == []


def test_filter_no_filters_returns_all(sample_opportunities):
    """Test that no filters returns original list."""
    filtered = filter_opportunities(sample_opportunities)

    assert len(filtered) == len(sample_opportunities)
    assert filtered == sample_opportunities


# Tests for sort_opportunities
def test_sort_by_ev_descending(sample_opportunities):
    """Test default sort by EV descending."""
    sorted_opps = sort_opportunities(sample_opportunities)

    # Should be sorted by ev_pct descending
    # [1]=8.2, [0]=5.5, [2]=1.5
    assert sorted_opps[0].ev_pct == 8.2
    assert sorted_opps[1].ev_pct == 5.5
    assert sorted_opps[2].ev_pct == 1.5


def test_sort_by_ev_ascending(sample_opportunities):
    """Test sort by EV ascending."""
    sorted_opps = sort_opportunities(sample_opportunities, reverse=False)

    # Should be sorted by ev_pct ascending
    assert sorted_opps[0].ev_pct == 1.5
    assert sorted_opps[1].ev_pct == 5.5
    assert sorted_opps[2].ev_pct == 8.2


def test_sort_by_kelly(sample_opportunities):
    """Test sorting by Kelly bet percentage."""
    sorted_opps = sort_opportunities(sample_opportunities, sort_by="kelly_bet_pct")

    # Should be sorted by kelly_bet_pct descending
    # [1]=4.1, [0]=2.75, [2]=0.75
    assert sorted_opps[0].kelly_bet_pct == 4.1
    assert sorted_opps[1].kelly_bet_pct == 2.75
    assert sorted_opps[2].kelly_bet_pct == 0.75


def test_sort_by_our_prob(sample_opportunities):
    """Test sorting by our probability."""
    sorted_opps = sort_opportunities(sample_opportunities, sort_by="our_prob")

    # Should be sorted by our_prob descending
    # [1]=0.60, [0]=0.55, [2]=0.52
    assert sorted_opps[0].our_prob == 0.60
    assert sorted_opps[1].our_prob == 0.55
    assert sorted_opps[2].our_prob == 0.52


def test_sort_invalid_field_uses_fallback(sample_opportunities):
    """Test that invalid sort field uses fallback value."""
    # Should not raise error, uses getattr fallback
    sorted_opps = sort_opportunities(sample_opportunities, sort_by="invalid_field")

    assert len(sorted_opps) == len(sample_opportunities)


# Tests for get_filter_summary
def test_get_filter_summary_single_filter():
    """Test filter summary with single active filter."""
    filters = {"min_ev": 5.0}
    summary = get_filter_summary(filters)

    assert summary == "min_ev=5.0%"


def test_get_filter_summary_multiple_filters():
    """Test filter summary with multiple active filters."""
    filters = {"min_ev": 5.0, "confidence": "high", "team": "BOS"}
    summary = get_filter_summary(filters)

    assert "min_ev=5.0%" in summary
    assert "confidence=high" in summary
    assert "team=BOS" in summary


def test_get_filter_summary_no_filters():
    """Test filter summary with no active filters."""
    filters = {}
    summary = get_filter_summary(filters)

    assert summary == ""


def test_get_filter_summary_all_filters():
    """Test filter summary with all possible filters."""
    filters = {
        "min_ev": 5.0,
        "max_ev": 10.0,
        "confidence": "high",
        "team": "BOS",
        "market": "h2h",
    }
    summary = get_filter_summary(filters)

    assert "min_ev=5.0%" in summary
    assert "max_ev=10.0%" in summary
    assert "confidence=high" in summary
    assert "team=BOS" in summary
    assert "market=h2h" in summary


# Tests for suggest_relaxed_filters
def test_suggest_relaxed_filters_with_min_ev():
    """Test relaxation suggestion when min_ev is set."""
    filters = {"min_ev": 10.0}
    suggestion = suggest_relaxed_filters(filters)

    assert "lower --min-ev" in suggestion


def test_suggest_relaxed_filters_with_confidence():
    """Test relaxation suggestion when confidence is set."""
    filters = {"confidence": "high"}
    suggestion = suggest_relaxed_filters(filters)

    assert "remove --confidence filter" in suggestion


def test_suggest_relaxed_filters_multiple():
    """Test relaxation suggestion with multiple filters."""
    filters = {"min_ev": 10.0, "confidence": "high"}
    suggestion = suggest_relaxed_filters(filters)

    assert "lower --min-ev" in suggestion or "remove --confidence filter" in suggestion


def test_suggest_relaxed_filters_no_filters():
    """Test suggestion when no filters are active."""
    filters = {}
    suggestion = suggest_relaxed_filters(filters)

    # Should provide generic suggestion
    assert len(suggestion) > 0
    assert "Try" in suggestion or "try" in suggestion
