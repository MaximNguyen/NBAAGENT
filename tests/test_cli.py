"""Tests for CLI and natural language query parsing.

These tests verify:
1. Query parser extracts date, teams, and bet types correctly
2. CLI commands execute successfully
3. Historical games are filtered out
4. Verbose mode displays additional information
"""

from datetime import datetime, timedelta

import pytest
from typer.testing import CliRunner

from nba_betting_agent.cli.main import cli
from nba_betting_agent.cli.parser import parse_query
from nba_betting_agent.graph import app

runner = CliRunner()


class TestQueryParser:
    """Test natural language query parsing."""

    def test_parse_tonight(self):
        """Test that 'tonight' is parsed to today's date."""
        query = "find +ev games tonight"
        parsed = parse_query(query)

        expected_date = datetime.now().date().isoformat()
        assert parsed.game_date == expected_date
        assert parsed.original == query

    def test_parse_tomorrow(self):
        """Test that 'tomorrow' is parsed to tomorrow's date."""
        query = "show me games tomorrow"
        parsed = parse_query(query)

        expected_date = (datetime.now().date() + timedelta(days=1)).isoformat()
        assert parsed.game_date == expected_date

    def test_parse_teams(self):
        """Test that team names are extracted and converted to abbreviations."""
        # Test single team
        query1 = "find best bets for celtics"
        parsed1 = parse_query(query1)
        assert parsed1.teams is not None
        assert "BOS" in parsed1.teams

        # Test multiple teams
        query2 = "celtics vs lakers"
        parsed2 = parse_query(query2)
        assert parsed2.teams is not None
        assert "BOS" in parsed2.teams
        assert "LAL" in parsed2.teams

        # Test team aliases
        query3 = "sixers warriors game"
        parsed3 = parse_query(query3)
        assert parsed3.teams is not None
        assert "PHI" in parsed3.teams
        assert "GSW" in parsed3.teams

    def test_parse_bet_type(self):
        """Test that bet types are extracted correctly."""
        # Moneyline
        query1 = "find moneyline bets"
        parsed1 = parse_query(query1)
        assert parsed1.bet_type == "moneyline"

        # ML abbreviation
        query2 = "show me ml for tonight"
        parsed2 = parse_query(query2)
        assert parsed2.bet_type == "moneyline"

        # Spread
        query3 = "what's the spread"
        parsed3 = parse_query(query3)
        assert parsed3.bet_type == "spread"

        # Props
        query4 = "player props for celtics"
        parsed4 = parse_query(query4)
        assert parsed4.bet_type == "props"

    def test_parse_this_week(self):
        """Test that 'this week' returns today's date for filtering."""
        query = "find games this week"
        parsed = parse_query(query)

        expected_date = datetime.now().date().isoformat()
        assert parsed.game_date == expected_date

    def test_parse_iso_date(self):
        """Test that ISO date format is parsed correctly."""
        query = "find games on 2026-02-15"
        parsed = parse_query(query)

        assert parsed.game_date == "2026-02-15"

    def test_parse_no_date(self):
        """Test that queries without dates return None."""
        query = "find best bets"
        parsed = parse_query(query)

        assert parsed.game_date is None


class TestCLI:
    """Test CLI commands and integration."""

    def test_version_command(self):
        """Test that version command runs successfully."""
        result = runner.invoke(cli, ["version"])

        assert result.exit_code == 0
        assert "NBA Betting Analysis" in result.stdout
        assert "0.1.0" in result.stdout

    def test_analyze_command_runs(self):
        """Test that analyze command executes without errors."""
        result = runner.invoke(cli, ["analyze", "find +ev games tonight"])

        # Should complete successfully (stub implementation)
        assert result.exit_code == 0
        assert "Analysis Result" in result.stdout or "recommendation" in result.stdout.lower()

    def test_analyze_with_verbose(self):
        """Test that verbose flag displays additional information."""
        result = runner.invoke(cli, ["analyze", "find games tonight", "--verbose"])

        assert result.exit_code == 0
        # Verbose mode should show parsed query
        assert "Parsed Query" in result.stdout or "Query:" in result.stdout

    def test_analyze_with_min_ev(self):
        """Test that min-ev option is accepted."""
        result = runner.invoke(cli, ["analyze", "find +ev games", "--min-ev", "0.05"])

        assert result.exit_code == 0
        # Command should complete successfully with custom threshold

    def test_historical_game_filtered(self):
        """Test that historical games are filtered out by the graph."""
        # Invoke graph directly with yesterday's date
        yesterday = (datetime.now().date() - timedelta(days=1)).isoformat()

        result = app.invoke({
            "query": "test historical filtering",
            "game_date": yesterday,
            "teams": [],
            "errors": [],
            "messages": [],
            "odds_data": [],
            "line_discrepancies": [],
            "team_stats": {},
            "player_stats": {},
            "injuries": [],
            "estimated_probabilities": {},
            "expected_values": [],
            "recommendation": "",
        })

        # Historical game should have no odds data
        assert len(result["odds_data"]) == 0

        # Should have filtering error message
        errors = result.get("errors", [])
        filtered_errors = [e for e in errors if "filtered" in e.lower()]
        assert len(filtered_errors) > 0

        # Recommendation should explain filtering
        recommendation = result.get("recommendation", "")
        assert "historical" in recommendation.lower() or "no games" in recommendation.lower()

    def test_upcoming_game_processed(self):
        """Test that upcoming games are processed (not filtered)."""
        # Invoke graph with today's date
        today = datetime.now().date().isoformat()

        result = app.invoke({
            "query": "test upcoming game",
            "game_date": today,
            "teams": [],
            "errors": [],
            "messages": [],
            "odds_data": [],
            "line_discrepancies": [],
            "team_stats": {},
            "player_stats": {},
            "injuries": [],
            "estimated_probabilities": {},
            "expected_values": [],
            "recommendation": "",
        })

        # Today's game should have odds data (stub implementation)
        assert len(result["odds_data"]) > 0

        # Should NOT have filtering errors
        errors = result.get("errors", [])
        filtered_errors = [e for e in errors if "filtered" in e.lower()]
        assert len(filtered_errors) == 0

    def test_far_future_game_filtered(self):
        """Test that games too far in the future are filtered."""
        # 10 days from now (beyond 7-day window)
        far_future = (datetime.now().date() + timedelta(days=10)).isoformat()

        result = app.invoke({
            "query": "test far future filtering",
            "game_date": far_future,
            "teams": [],
            "errors": [],
            "messages": [],
            "odds_data": [],
            "line_discrepancies": [],
            "team_stats": {},
            "player_stats": {},
            "injuries": [],
            "estimated_probabilities": {},
            "expected_values": [],
            "recommendation": "",
        })

        # Far future game should be filtered
        assert len(result["odds_data"]) == 0

        # Should have filtering errors
        errors = result.get("errors", [])
        filtered_errors = [e for e in errors if "filtered" in e.lower()]
        assert len(filtered_errors) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
