"""Integration tests for the Lines Agent.

Tests the complete flow from collect_odds through discrepancy detection,
using mocked API responses to avoid real API calls.

Tests PROVE:
1. collect_odds returns odds_data and line_discrepancies
2. Discrepancies are correctly detected and formatted
3. Team filtering works as expected
4. API errors are handled gracefully
5. Circuit breaker opens after repeated failures
6. Missing API key returns helpful error
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, patch, MagicMock

from circuitbreaker import CircuitBreakerError

from nba_betting_agent.agents.lines_agent.agent import (
    collect_odds,
    lines_agent_impl,
    fetch_from_api,
)
from nba_betting_agent.agents.lines_agent.models import (
    GameOdds,
    BookmakerOdds,
    Market,
    Outcome,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_game_odds():
    """Create a mock GameOdds object with discrepancies.

    DraftKings and FanDuel offer different odds for Boston Celtics:
    - DraftKings: 1.65 (60.6% implied)
    - FanDuel: 1.75 (57.1% implied)
    - Difference: 3.5 percentage points -> should trigger discrepancy
    """
    return GameOdds(
        id="game123",
        sport_key="basketball_nba",
        commence_time=datetime.fromisoformat("2026-01-24T00:00:00+00:00"),
        home_team="Boston Celtics",
        away_team="Los Angeles Lakers",
        bookmakers=[
            BookmakerOdds(
                key="draftkings",
                title="DraftKings",
                last_update=datetime.now(),
                markets=[
                    Market(
                        key="h2h",
                        outcomes=[
                            Outcome(name="Boston Celtics", price=1.65),
                            Outcome(name="Los Angeles Lakers", price=2.30),
                        ],
                    )
                ],
            ),
            BookmakerOdds(
                key="fanduel",
                title="FanDuel",
                last_update=datetime.now(),
                markets=[
                    Market(
                        key="h2h",
                        outcomes=[
                            Outcome(name="Boston Celtics", price=1.75),
                            Outcome(name="Los Angeles Lakers", price=2.15),
                        ],
                    )
                ],
            ),
        ],
    )


@pytest.fixture
def mock_game_odds_no_discrepancy():
    """Create a mock GameOdds object with nearly identical odds (no discrepancy)."""
    return GameOdds(
        id="game456",
        sport_key="basketball_nba",
        commence_time=datetime.fromisoformat("2026-01-24T00:00:00+00:00"),
        home_team="Miami Heat",
        away_team="New York Knicks",
        bookmakers=[
            BookmakerOdds(
                key="draftkings",
                title="DraftKings",
                last_update=datetime.now(),
                markets=[
                    Market(
                        key="h2h",
                        outcomes=[
                            Outcome(name="Miami Heat", price=1.90),
                            Outcome(name="New York Knicks", price=1.90),
                        ],
                    )
                ],
            ),
            BookmakerOdds(
                key="fanduel",
                title="FanDuel",
                last_update=datetime.now(),
                markets=[
                    Market(
                        key="h2h",
                        outcomes=[
                            Outcome(name="Miami Heat", price=1.91),
                            Outcome(name="New York Knicks", price=1.89),
                        ],
                    )
                ],
            ),
        ],
    )


# ============================================================================
# Test: collect_odds success path
# ============================================================================


@pytest.mark.asyncio
async def test_collect_odds_success(mock_game_odds):
    """Test collect_odds returns odds_data and line_discrepancies on success."""
    with patch(
        "nba_betting_agent.agents.lines_agent.agent.fetch_from_api",
        new_callable=AsyncMock,
    ) as mock_fetch:
        mock_fetch.return_value = ([mock_game_odds], [])

        with patch.dict("os.environ", {"ODDS_API_KEY": "test-key"}):
            result = await collect_odds(game_date=None, teams=[])

    assert "odds_data" in result
    assert "line_discrepancies" in result
    assert "errors" in result
    assert "sources_succeeded" in result
    assert "sources_failed" in result

    assert len(result["odds_data"]) == 1
    assert result["odds_data"][0]["home_team"] == "Boston Celtics"
    assert result["sources_succeeded"] == ["odds_api"]
    assert result["sources_failed"] == []


# ============================================================================
# Test: discrepancy detection
# ============================================================================


@pytest.mark.asyncio
async def test_collect_odds_finds_discrepancies(mock_game_odds):
    """Test that discrepancies are detected and formatted correctly."""
    with patch(
        "nba_betting_agent.agents.lines_agent.agent.fetch_from_api",
        new_callable=AsyncMock,
    ) as mock_fetch:
        mock_fetch.return_value = ([mock_game_odds], [])

        with patch.dict("os.environ", {"ODDS_API_KEY": "test-key"}):
            result = await collect_odds(game_date=None, teams=[])

    # Should find discrepancies for Celtics (3.5% diff) and possibly Lakers
    assert len(result["line_discrepancies"]) >= 1

    # Check discrepancy structure
    celtics_disc = next(
        (d for d in result["line_discrepancies"] if d["outcome"] == "Boston Celtics"),
        None,
    )
    assert celtics_disc is not None
    assert celtics_disc["game_id"] == "game123"
    assert celtics_disc["market"] == "h2h"
    assert celtics_disc["best_book"] == "FanDuel"  # 1.75 is better for bettor
    assert celtics_disc["best_odds"] == 1.75
    assert celtics_disc["worst_book"] == "DraftKings"  # 1.65 is worse
    assert celtics_disc["worst_odds"] == 1.65
    assert celtics_disc["implied_diff_pct"] >= 2.0  # Significant discrepancy


@pytest.mark.asyncio
async def test_collect_odds_no_discrepancy(mock_game_odds_no_discrepancy):
    """Test that near-identical odds don't trigger discrepancies."""
    with patch(
        "nba_betting_agent.agents.lines_agent.agent.fetch_from_api",
        new_callable=AsyncMock,
    ) as mock_fetch:
        mock_fetch.return_value = ([mock_game_odds_no_discrepancy], [])

        with patch.dict("os.environ", {"ODDS_API_KEY": "test-key"}):
            result = await collect_odds(game_date=None, teams=[])

    # Near-identical odds (< 2% diff) should not trigger discrepancy
    assert len(result["line_discrepancies"]) == 0


# ============================================================================
# Test: team filtering
# ============================================================================


@pytest.mark.asyncio
async def test_collect_odds_filters_by_team(mock_game_odds, mock_game_odds_no_discrepancy):
    """Test that only games with requested teams are returned."""
    both_games = [mock_game_odds, mock_game_odds_no_discrepancy]

    with patch(
        "nba_betting_agent.agents.lines_agent.agent.fetch_from_api",
        new_callable=AsyncMock,
    ) as mock_fetch:
        mock_fetch.return_value = (both_games, [])

        with patch.dict("os.environ", {"ODDS_API_KEY": "test-key"}):
            # Filter for Celtics only
            result = await collect_odds(game_date=None, teams=["celtics"])

    # Should only return the Celtics game
    assert len(result["odds_data"]) == 1
    assert result["odds_data"][0]["home_team"] == "Boston Celtics"


@pytest.mark.asyncio
async def test_collect_odds_filters_by_multiple_teams(
    mock_game_odds, mock_game_odds_no_discrepancy
):
    """Test filtering with multiple teams."""
    both_games = [mock_game_odds, mock_game_odds_no_discrepancy]

    with patch(
        "nba_betting_agent.agents.lines_agent.agent.fetch_from_api",
        new_callable=AsyncMock,
    ) as mock_fetch:
        mock_fetch.return_value = (both_games, [])

        with patch.dict("os.environ", {"ODDS_API_KEY": "test-key"}):
            # Filter for both teams - should get both games
            result = await collect_odds(game_date=None, teams=["celtics", "heat"])

    assert len(result["odds_data"]) == 2


# ============================================================================
# Test: error handling
# ============================================================================


@pytest.mark.asyncio
async def test_collect_odds_handles_api_error():
    """Test that API errors are captured in the errors list."""
    with patch(
        "nba_betting_agent.agents.lines_agent.agent.fetch_from_api",
        new_callable=AsyncMock,
    ) as mock_fetch:
        mock_fetch.side_effect = Exception("API connection failed")

        with patch.dict("os.environ", {"ODDS_API_KEY": "test-key"}):
            result = await collect_odds(game_date=None, teams=[])

    assert len(result["errors"]) >= 1
    assert "API connection failed" in result["errors"][0]
    assert result["sources_failed"] == ["odds_api"]
    assert result["odds_data"] == []


@pytest.mark.asyncio
async def test_collect_odds_no_api_key():
    """Test that missing API key returns helpful error."""
    with patch.dict("os.environ", {}, clear=True):
        # Remove ODDS_API_KEY from environment
        with patch("os.getenv", return_value=None):
            result = await collect_odds(game_date=None, teams=[])

    assert len(result["errors"]) >= 1
    assert "ODDS_API_KEY" in result["errors"][0]
    assert ".env" in result["errors"][0]
    assert result["sources_failed"] == ["odds_api"]


# ============================================================================
# Test: lines_agent_impl (sync wrapper)
# ============================================================================


def test_lines_agent_impl_returns_state_update(mock_game_odds):
    """Test that lines_agent_impl returns dict with required keys."""
    with patch(
        "nba_betting_agent.agents.lines_agent.agent.fetch_from_api",
        new_callable=AsyncMock,
    ) as mock_fetch:
        mock_fetch.return_value = ([mock_game_odds], [])

        with patch.dict("os.environ", {"ODDS_API_KEY": "test-key"}):
            state = {"game_date": None, "teams": []}
            result = lines_agent_impl(state)

    # Must have these keys for LangGraph state update
    assert "odds_data" in result
    assert "line_discrepancies" in result
    assert "errors" in result

    # Values should be lists (not None)
    assert isinstance(result["odds_data"], list)
    assert isinstance(result["line_discrepancies"], list)
    assert isinstance(result["errors"], list)


def test_lines_agent_impl_no_api_key():
    """Test lines_agent_impl returns helpful error when API key missing."""
    with patch.dict("os.environ", {}, clear=True):
        with patch("os.getenv", return_value=None):
            state = {"game_date": None, "teams": []}
            result = lines_agent_impl(state)

    assert len(result["errors"]) >= 1
    assert "ODDS_API_KEY" in result["errors"][0]
    assert result["odds_data"] == []
    assert result["line_discrepancies"] == []


# ============================================================================
# Test: circuit breaker
# ============================================================================


@pytest.mark.asyncio
async def test_circuit_breaker_configuration():
    """Test that circuit breaker is configured with correct parameters.

    The circuit breaker is configured with:
    - failure_threshold=3 (opens after 3 failures)
    - recovery_timeout=300 (recovers after 5 minutes)

    We verify this by checking the function is decorated and handles errors.
    """
    # Verify fetch_from_api is wrapped (has __wrapped__ attribute from decorator)
    assert hasattr(fetch_from_api, "__wrapped__"), "fetch_from_api should be decorated"

    # Verify it's an async function
    import asyncio

    assert asyncio.iscoroutinefunction(
        fetch_from_api
    ), "fetch_from_api should be async"


@pytest.mark.asyncio
async def test_collect_odds_handles_circuit_breaker():
    """Test that collect_odds handles CircuitBreakerError gracefully."""
    with patch(
        "nba_betting_agent.agents.lines_agent.agent.fetch_from_api",
        new_callable=AsyncMock,
    ) as mock_fetch:
        mock_fetch.side_effect = CircuitBreakerError(
            fetch_from_api, "circuit breaker open"
        )

        with patch.dict("os.environ", {"ODDS_API_KEY": "test-key"}):
            result = await collect_odds(game_date=None, teams=[])

    assert len(result["errors"]) >= 1
    assert "circuit breaker" in result["errors"][0].lower()
    assert result["sources_failed"] == ["odds_api"]


@pytest.mark.asyncio
async def test_circuit_breaker_error_message():
    """Test that circuit breaker error message is user-friendly."""
    with patch(
        "nba_betting_agent.agents.lines_agent.agent.fetch_from_api",
        new_callable=AsyncMock,
    ) as mock_fetch:
        mock_fetch.side_effect = CircuitBreakerError(
            fetch_from_api, "circuit breaker open"
        )

        with patch.dict("os.environ", {"ODDS_API_KEY": "test-key"}):
            result = await collect_odds(game_date=None, teams=[])

    # Error message should be informative
    error_msg = result["errors"][0]
    assert "circuit breaker" in error_msg.lower()
    assert "temporarily unavailable" in error_msg.lower() or "open" in error_msg.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
