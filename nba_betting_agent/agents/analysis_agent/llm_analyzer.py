"""LLM-powered matchup analysis using Claude.

This module provides qualitative analysis to complement statistical models,
leveraging Claude's pattern recognition for injuries, coaching, rest, motivation,
and market dynamics that pure statistics might miss.
"""

import os
from dataclasses import dataclass
from typing import Optional

import anthropic

from nba_betting_agent.agents.analysis_agent.prompts.matchup_analysis import (
    format_matchup_prompt,
    format_team_stats,
    format_injuries,
    format_odds_summary,
)


@dataclass
class MatchupAnalysis:
    """Structured LLM analysis of a matchup.

    Attributes:
        home_team: Home team name
        away_team: Away team name
        raw_analysis: Full LLM response text
        home_factors: Bullet points favoring home team
        away_factors: Bullet points favoring away team
        biggest_edge: Key mismatch or advantage the market might undervalue
        risk_factors: Sources of uncertainty or variance
        contrarian_angle: Overlooked factor contradicting public sentiment
        model_used: Claude model identifier
        tokens_used: Total tokens consumed (input + output)
    """

    home_team: str
    away_team: str
    raw_analysis: str
    home_factors: list[str]
    away_factors: list[str]
    biggest_edge: str
    risk_factors: list[str]
    contrarian_angle: str
    model_used: str
    tokens_used: int


class LLMAnalyzer:
    """Analyzer for NBA matchups using Claude LLM.

    Provides qualitative insights on injuries, rest, motivation, and matchup dynamics
    that complement statistical probability models.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-sonnet-4-20250514"
    ):
        """Initialize LLM analyzer.

        Args:
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
            model: Claude model to use

        Raises:
            ValueError: If no API key provided or found in environment
        """
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY not found in environment or parameter. "
                "Get your API key from https://console.anthropic.com/settings/keys"
            )
        self.client = anthropic.Anthropic(api_key=self.api_key)
        self.model = model

    def analyze_matchup(
        self,
        home_team: str,
        away_team: str,
        game_date: str,
        team_stats: dict,
        injuries: list,
        odds_data: list,
        max_tokens: int = 1500
    ) -> MatchupAnalysis:
        """Analyze matchup using Claude for qualitative insights.

        Args:
            home_team: Home team name
            away_team: Away team name
            game_date: Game date string (e.g., "2026-01-24")
            team_stats: Dict mapping team abbreviation to TeamStats dict/model
            injuries: List of injury dicts/models
            odds_data: List of GameOdds dicts/models
            max_tokens: Maximum tokens for LLM response

        Returns:
            MatchupAnalysis with structured insights

        Raises:
            anthropic.APIError: If API call fails
        """
        # Find team abbreviations
        home_abbr = self._find_team_abbr(home_team, team_stats)
        away_abbr = self._find_team_abbr(away_team, team_stats)

        # Format data for prompt
        home_stats_str = format_team_stats(team_stats.get(home_abbr, {}))
        away_stats_str = format_team_stats(team_stats.get(away_abbr, {}))

        # Filter injuries to relevant teams
        relevant_injuries = [
            inj for inj in injuries
            if self._get_team(inj) in [home_abbr, away_abbr]
        ]
        injuries_str = format_injuries(relevant_injuries)
        odds_str = format_odds_summary(odds_data)

        # Construct prompt
        prompt = format_matchup_prompt(
            home_team=home_team,
            away_team=away_team,
            game_date=game_date,
            home_stats=home_stats_str,
            away_stats=away_stats_str,
            injuries=injuries_str,
            odds_summary=odds_str
        )

        # Call Claude
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}]
            )

            raw_text = response.content[0].text
            tokens = response.usage.input_tokens + response.usage.output_tokens

            # Parse response into structured format
            return MatchupAnalysis(
                home_team=home_team,
                away_team=away_team,
                raw_analysis=raw_text,
                home_factors=self._extract_section(raw_text, f"Key Factors Favoring {home_team}"),
                away_factors=self._extract_section(raw_text, f"Key Factors Favoring {away_team}"),
                biggest_edge=self._extract_section_text(raw_text, "Biggest Mismatch"),
                risk_factors=self._extract_section(raw_text, "Risk Factors"),
                contrarian_angle=self._extract_section_text(raw_text, "Contrarian Angle"),
                model_used=self.model,
                tokens_used=tokens
            )

        except anthropic.APIError as e:
            # Return partial analysis with error
            return MatchupAnalysis(
                home_team=home_team,
                away_team=away_team,
                raw_analysis=f"API Error: {str(e)}",
                home_factors=[],
                away_factors=[],
                biggest_edge="Analysis failed due to API error",
                risk_factors=[],
                contrarian_angle="",
                model_used=self.model,
                tokens_used=0
            )

    def _find_team_abbr(self, team_name: str, team_stats: dict) -> str:
        """Find team abbreviation from name.

        Args:
            team_name: Team name (can be abbreviation or full name)
            team_stats: Dict of team stats

        Returns:
            Team abbreviation (uppercase)
        """
        # Check if already abbreviation
        if team_name.upper() in team_stats:
            return team_name.upper()

        # Search by name
        team_lower = team_name.lower()
        for abbr, stats in team_stats.items():
            # Handle both dict and Pydantic model
            if isinstance(stats, dict):
                name = stats.get('name', '').lower()
            else:
                name = getattr(stats, 'name', '').lower()

            if team_lower in name or name in team_lower:
                return abbr

        # Fallback to first 3 chars uppercase
        return team_name[:3].upper()

    def _get_team(self, injury) -> str:
        """Extract team from injury dict or model.

        Args:
            injury: Injury dict or Pydantic model

        Returns:
            Team abbreviation
        """
        if isinstance(injury, dict):
            return injury.get('team', '')
        return getattr(injury, 'team', '')

    def _extract_section(self, text: str, header: str) -> list[str]:
        """Extract bullet points from a section.

        Args:
            text: Full LLM response text
            header: Section header to find

        Returns:
            List of bullet point strings (without markers)
        """
        lines = text.split('\n')
        in_section = False
        bullets = []

        for line in lines:
            # Check if we found the header
            if header.lower() in line.lower():
                in_section = True
                continue

            if in_section:
                # Stop at next section header
                if line.startswith('##'):
                    break

                # Extract bullet content
                stripped = line.strip()
                if stripped.startswith('-') or stripped.startswith('*'):
                    bullet_text = stripped.lstrip('-*').strip()
                    if bullet_text:
                        bullets.append(bullet_text)

        return bullets

    def _extract_section_text(self, text: str, header: str) -> str:
        """Extract text content from a section.

        Args:
            text: Full LLM response text
            header: Section header to find

        Returns:
            Section text content (joined lines)
        """
        lines = text.split('\n')
        in_section = False
        content = []

        for line in lines:
            # Check if we found the header
            if header.lower() in line.lower():
                in_section = True
                continue

            if in_section:
                # Stop at next section header
                if line.startswith('##'):
                    break

                # Collect non-empty lines
                stripped = line.strip()
                if stripped and not stripped.startswith('#'):
                    content.append(stripped)

        return ' '.join(content)


def analyze_matchup(
    home_team: str,
    away_team: str,
    game_date: str,
    team_stats: dict,
    injuries: list,
    odds_data: list,
    api_key: Optional[str] = None
) -> MatchupAnalysis:
    """Convenience function for one-off matchup analysis.

    Args:
        home_team: Home team name
        away_team: Away team name
        game_date: Game date string
        team_stats: Dict mapping team abbreviation to TeamStats
        injuries: List of injury reports
        odds_data: List of GameOdds
        api_key: Optional API key (defaults to env var)

    Returns:
        MatchupAnalysis with LLM insights

    Raises:
        ValueError: If no API key available
        anthropic.APIError: If API call fails
    """
    analyzer = LLMAnalyzer(api_key=api_key)
    return analyzer.analyze_matchup(
        home_team, away_team, game_date, team_stats, injuries, odds_data
    )
