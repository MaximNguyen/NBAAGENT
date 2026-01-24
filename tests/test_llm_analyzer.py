"""Tests for LLM-powered matchup analysis."""

import os
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from nba_betting_agent.agents.analysis_agent.llm_analyzer import (
    LLMAnalyzer,
    MatchupAnalysis,
    analyze_matchup,
)
from nba_betting_agent.agents.analysis_agent.prompts.matchup_analysis import (
    format_injuries,
    format_matchup_prompt,
    format_odds_summary,
    format_team_stats,
)


# --- Helper Formatting Tests ---


def test_format_team_stats_dict():
    """Test formatting team stats from dict."""
    stats = {
        'name': 'Boston Celtics',
        'record': {'wins': 30, 'losses': 10},
        'stats': {
            'pts': 118.5,
            'reb': 45.2,
            'ast': 26.3,
            'fg_pct': 0.482,
            'fg3_pct': 0.385,
        },
        'advanced': {
            'off_rtg': 121.5,
            'def_rtg': 110.2,
            'net_rtg': 11.3,
            'pace': 99.8,
        },
        'last_10': {
            'record': '8-2',
            'pts': 120.1,
        }
    }

    result = format_team_stats(stats)

    assert 'Record: 30-10' in result
    assert 'PPG: 118.5' in result
    assert 'FG%: 48.2%' in result
    assert '3P%: 38.5%' in result
    assert 'ORtg: 121.5' in result
    assert 'Last 10: 8-2' in result


def test_format_team_stats_empty():
    """Test formatting empty stats."""
    result = format_team_stats({})
    assert result == "No stats available"


def test_format_team_stats_partial():
    """Test formatting partial stats (only record and basic)."""
    stats = {
        'record': {'wins': 25, 'losses': 15},
        'stats': {
            'pts': 112.0,
            'reb': 43.0,
            'ast': 24.0,
            'fg_pct': 0.460,
            'fg3_pct': 0.360,
        }
    }

    result = format_team_stats(stats)

    assert 'Record: 25-15' in result
    assert 'PPG: 112.0' in result
    assert 'ORtg' not in result  # No advanced stats
    assert 'Last 10' not in result


def test_format_injuries_list():
    """Test formatting injury list."""
    injuries = [
        {
            'player': 'Jayson Tatum',
            'team': 'BOS',
            'status': 'Questionable',
            'injury': 'Ankle'
        },
        {
            'player': 'LeBron James',
            'team': 'LAL',
            'status': 'Out',
            'injury': 'Knee'
        }
    ]

    result = format_injuries(injuries)

    assert 'Jayson Tatum (BOS): Questionable - Ankle' in result
    assert 'LeBron James (LAL): Out - Knee' in result


def test_format_injuries_empty():
    """Test formatting empty injury list."""
    result = format_injuries([])
    assert result == "No injuries reported"


def test_format_odds_summary():
    """Test formatting odds summary."""
    odds_data = [
        {
            'bookmakers': [
                {
                    'title': 'DraftKings',
                    'key': 'draftkings',
                    'markets': [
                        {
                            'key': 'h2h',
                            'outcomes': [
                                {'name': 'Boston Celtics', 'price': 1.85},
                                {'name': 'Los Angeles Lakers', 'price': 2.05}
                            ]
                        }
                    ]
                },
                {
                    'title': 'FanDuel',
                    'key': 'fanduel',
                    'markets': [
                        {
                            'key': 'h2h',
                            'outcomes': [
                                {'name': 'Boston Celtics', 'price': 1.87},
                                {'name': 'Los Angeles Lakers', 'price': 2.00}
                            ]
                        }
                    ]
                }
            ]
        }
    ]

    result = format_odds_summary(odds_data)

    assert 'DraftKings:' in result
    assert 'Boston Celtics 1.85' in result
    assert 'Los Angeles Lakers 2.05' in result
    assert 'FanDuel:' in result


def test_format_odds_summary_empty():
    """Test formatting empty odds."""
    result = format_odds_summary([])
    assert result == "No odds available"


def test_format_matchup_prompt():
    """Test complete prompt formatting."""
    prompt = format_matchup_prompt(
        home_team="Boston Celtics",
        away_team="Los Angeles Lakers",
        game_date="2026-01-24",
        home_stats="Record: 30-10\nPPG: 118.5",
        away_stats="Record: 25-15\nPPG: 112.0",
        injuries="- Jayson Tatum (BOS): Questionable - Ankle",
        odds_summary="DraftKings: Celtics 1.85, Lakers 2.05"
    )

    assert "Boston Celtics" in prompt
    assert "Los Angeles Lakers" in prompt
    assert "2026-01-24" in prompt
    assert "Record: 30-10" in prompt
    assert "Jayson Tatum" in prompt
    assert "DraftKings" in prompt
    assert "Injury Impact" in prompt  # Part of template
    assert "Risk Factors" in prompt  # Part of template


# --- LLMAnalyzer Tests ---


def test_llm_analyzer_init_with_key():
    """Test initialization with explicit API key."""
    analyzer = LLMAnalyzer(api_key="test-key-123")
    assert analyzer.api_key == "test-key-123"
    assert analyzer.model == "claude-sonnet-4-20250514"


def test_llm_analyzer_init_from_env():
    """Test initialization from environment variable."""
    with patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'env-key-456'}):
        analyzer = LLMAnalyzer()
        assert analyzer.api_key == "env-key-456"


def test_llm_analyzer_init_no_key_raises():
    """Test initialization without API key raises ValueError."""
    with patch.dict(os.environ, {}, clear=True):
        # Clear ANTHROPIC_API_KEY if it exists
        os.environ.pop('ANTHROPIC_API_KEY', None)

        with pytest.raises(ValueError) as exc:
            LLMAnalyzer()

        assert "ANTHROPIC_API_KEY not found" in str(exc.value)
        assert "console.anthropic.com" in str(exc.value)


def test_llm_analyzer_custom_model():
    """Test initialization with custom model."""
    analyzer = LLMAnalyzer(api_key="test-key", model="claude-opus-4-20250514")
    assert analyzer.model == "claude-opus-4-20250514"


# --- MatchupAnalysis Dataclass Tests ---


def test_matchup_analysis_dataclass():
    """Test MatchupAnalysis dataclass creation."""
    analysis = MatchupAnalysis(
        home_team="Celtics",
        away_team="Lakers",
        raw_analysis="Full text...",
        home_factors=["Home court", "Better defense"],
        away_factors=["Star power", "Rest advantage"],
        biggest_edge="Lakers undervalued on road",
        risk_factors=["Injury uncertainty", "B2B fatigue"],
        contrarian_angle="Public overvalues home court",
        model_used="claude-sonnet-4-20250514",
        tokens_used=850
    )

    assert analysis.home_team == "Celtics"
    assert len(analysis.home_factors) == 2
    assert analysis.tokens_used == 850
    assert "Better defense" in analysis.home_factors


# --- Mocked API Call Tests ---


@patch('nba_betting_agent.agents.analysis_agent.llm_analyzer.anthropic.Anthropic')
def test_analyze_matchup_mock_success(mock_anthropic_class):
    """Test analyze_matchup with mocked successful API call."""
    # Setup mock
    mock_client = MagicMock()
    mock_anthropic_class.return_value = mock_client

    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="""
## Key Factors Favoring Boston Celtics
- Home court advantage
- Superior defensive rating
- Healthy roster

## Key Factors Favoring Los Angeles Lakers
- Star power with LeBron
- Better recent form

## Biggest Mismatch or Advantage
Celtics' elite defense vs Lakers' struggles on the road creates value.

## Risk Factors
- Injury to key rotation player could shift dynamics
- B2B fatigue factor

## Contrarian Angle
Public overreacting to Lakers' recent win streak.
""")]
    mock_response.usage.input_tokens = 500
    mock_response.usage.output_tokens = 350
    mock_client.messages.create.return_value = mock_response

    # Test
    analyzer = LLMAnalyzer(api_key="test-key")
    result = analyzer.analyze_matchup(
        home_team="Boston Celtics",
        away_team="Los Angeles Lakers",
        game_date="2026-01-24",
        team_stats={
            'BOS': {'name': 'Boston Celtics'},
            'LAL': {'name': 'Los Angeles Lakers'}
        },
        injuries=[],
        odds_data=[]
    )

    # Verify API was called
    mock_client.messages.create.assert_called_once()
    call_args = mock_client.messages.create.call_args

    assert call_args.kwargs['model'] == "claude-sonnet-4-20250514"
    assert call_args.kwargs['max_tokens'] == 1500
    assert len(call_args.kwargs['messages']) == 1
    assert call_args.kwargs['messages'][0]['role'] == 'user'

    # Verify parsed result
    assert result.home_team == "Boston Celtics"
    assert result.away_team == "Los Angeles Lakers"
    assert result.tokens_used == 850  # 500 + 350
    assert len(result.home_factors) == 3
    assert "Home court advantage" in result.home_factors
    assert len(result.away_factors) == 2
    assert "Star power" in result.away_factors[0]
    assert "Celtics' elite defense" in result.biggest_edge
    assert len(result.risk_factors) == 2
    assert "overreacting" in result.contrarian_angle.lower()


@patch('nba_betting_agent.agents.analysis_agent.llm_analyzer.anthropic.Anthropic')
def test_analyze_matchup_api_error(mock_anthropic_class):
    """Test analyze_matchup handles API errors gracefully."""
    # Setup mock to raise API error
    mock_client = MagicMock()
    mock_anthropic_class.return_value = mock_client
    mock_client.messages.create.side_effect = Exception("API rate limit exceeded")

    # Test
    analyzer = LLMAnalyzer(api_key="test-key")
    result = analyzer.analyze_matchup(
        home_team="Celtics",
        away_team="Lakers",
        game_date="2026-01-24",
        team_stats={'BOS': {}, 'LAL': {}},
        injuries=[],
        odds_data=[]
    )

    # Verify error handling
    assert "API Error" in result.raw_analysis
    assert result.tokens_used == 0
    assert result.home_factors == []
    assert result.away_factors == []
    assert "failed" in result.biggest_edge.lower()


def test_find_team_abbr_exact_match():
    """Test _find_team_abbr with exact abbreviation match."""
    analyzer = LLMAnalyzer(api_key="test-key")
    team_stats = {
        'BOS': {'name': 'Boston Celtics'},
        'LAL': {'name': 'Los Angeles Lakers'}
    }

    assert analyzer._find_team_abbr('BOS', team_stats) == 'BOS'
    assert analyzer._find_team_abbr('bos', team_stats) == 'BOS'


def test_find_team_abbr_name_search():
    """Test _find_team_abbr with team name search."""
    analyzer = LLMAnalyzer(api_key="test-key")
    team_stats = {
        'BOS': {'name': 'Boston Celtics'},
        'LAL': {'name': 'Los Angeles Lakers'}
    }

    assert analyzer._find_team_abbr('Boston Celtics', team_stats) == 'BOS'
    assert analyzer._find_team_abbr('Lakers', team_stats) == 'LAL'
    assert analyzer._find_team_abbr('celtics', team_stats) == 'BOS'


def test_find_team_abbr_fallback():
    """Test _find_team_abbr fallback to first 3 chars."""
    analyzer = LLMAnalyzer(api_key="test-key")
    team_stats = {}

    assert analyzer._find_team_abbr('Warriors', team_stats) == 'WAR'
    assert analyzer._find_team_abbr('NY', team_stats) == 'NY'


def test_extract_section_bullets():
    """Test _extract_section extracts bullet points correctly."""
    analyzer = LLMAnalyzer(api_key="test-key")
    text = """
## Key Factors Favoring Team A
- First factor
- Second factor
* Third factor

## Key Factors Favoring Team B
- Different section
"""

    result = analyzer._extract_section(text, "Key Factors Favoring Team A")

    assert len(result) == 3
    assert "First factor" in result
    assert "Second factor" in result
    assert "Third factor" in result
    assert "Different section" not in result


def test_extract_section_text():
    """Test _extract_section_text extracts paragraph content."""
    analyzer = LLMAnalyzer(api_key="test-key")
    text = """
## Biggest Mismatch or Advantage
The home team's elite defense against the away team's weak offense
creates a significant edge that the market undervalues.

## Risk Factors
Different section
"""

    result = analyzer._extract_section_text(text, "Biggest Mismatch")

    assert "elite defense" in result
    assert "undervalues" in result
    assert "Risk Factors" not in result
    assert "Different section" not in result


def test_standalone_analyze_matchup_function():
    """Test standalone analyze_matchup function."""
    with patch('nba_betting_agent.agents.analysis_agent.llm_analyzer.anthropic.Anthropic'):
        with patch('nba_betting_agent.agents.analysis_agent.llm_analyzer.LLMAnalyzer.analyze_matchup') as mock_analyze:
            mock_analyze.return_value = MatchupAnalysis(
                home_team="Celtics",
                away_team="Lakers",
                raw_analysis="test",
                home_factors=[],
                away_factors=[],
                biggest_edge="test",
                risk_factors=[],
                contrarian_angle="test",
                model_used="test",
                tokens_used=100
            )

            result = analyze_matchup(
                home_team="Celtics",
                away_team="Lakers",
                game_date="2026-01-24",
                team_stats={},
                injuries=[],
                odds_data=[],
                api_key="test-key"
            )

            assert result.home_team == "Celtics"
            assert result.tokens_used == 100


def test_extract_section_empty():
    """Test _extract_section with missing section returns empty list."""
    analyzer = LLMAnalyzer(api_key="test-key")
    text = "## Some Other Section\n- Point"

    result = analyzer._extract_section(text, "Non-existent Section")

    assert result == []


def test_extract_section_text_empty():
    """Test _extract_section_text with missing section returns empty string."""
    analyzer = LLMAnalyzer(api_key="test-key")
    text = "## Some Other Section\nContent"

    result = analyzer._extract_section_text(text, "Non-existent Section")

    assert result == ""
