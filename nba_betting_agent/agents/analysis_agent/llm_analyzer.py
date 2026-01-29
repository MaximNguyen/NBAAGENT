"""LLM-powered matchup analysis using Claude or Ollama.

This module provides qualitative analysis to complement statistical models,
leveraging LLM pattern recognition for injuries, coaching, rest, motivation,
and market dynamics that pure statistics might miss.

Supports two providers:
- anthropic (default): Claude API for production quality
- ollama: Local models for free testing/development

Configure via environment variables:
- LLM_PROVIDER: "anthropic" or "ollama" (default: "anthropic")
- ANTHROPIC_API_KEY: Required for anthropic provider
- OLLAMA_MODEL: Model to use with Ollama (default: "llama3.1")
- OLLAMA_HOST: Ollama server URL (default: "http://localhost:11434")
"""

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

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
        model_used: Model identifier (e.g., "claude-sonnet-4-20250514" or "llama3.1")
        tokens_used: Total tokens consumed (input + output), 0 for Ollama
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


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def generate(self, prompt: str, max_tokens: int = 1500) -> tuple[str, int]:
        """Generate a response from the LLM.

        Args:
            prompt: The prompt to send to the LLM
            max_tokens: Maximum tokens for response

        Returns:
            Tuple of (response_text, tokens_used)
        """
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the model identifier."""
        pass


class AnthropicProvider(LLMProvider):
    """Claude API provider for production use."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-sonnet-4-20250514"
    ):
        import anthropic

        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY not found in environment or parameter. "
                "Get your API key from https://console.anthropic.com/settings/keys"
            )
        self.client = anthropic.Anthropic(api_key=self.api_key)
        self._model = model

    @property
    def model_name(self) -> str:
        return self._model

    def generate(self, prompt: str, max_tokens: int = 1500) -> tuple[str, int]:
        import anthropic

        try:
            response = self.client.messages.create(
                model=self._model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}]
            )
            text = response.content[0].text
            tokens = response.usage.input_tokens + response.usage.output_tokens
            return text, tokens
        except anthropic.APIError as e:
            raise RuntimeError(f"Anthropic API error: {e}")


class OllamaProvider(LLMProvider):
    """Ollama provider for free local testing."""

    def __init__(
        self,
        model: Optional[str] = None,
        host: Optional[str] = None
    ):
        self._model = model or os.environ.get("OLLAMA_MODEL", "llama3.1")
        self._host = host or os.environ.get("OLLAMA_HOST", "http://localhost:11434")

    @property
    def model_name(self) -> str:
        return f"ollama/{self._model}"

    def generate(self, prompt: str, max_tokens: int = 1500) -> tuple[str, int]:
        try:
            import ollama
        except ImportError:
            raise ImportError(
                "ollama package not installed. Install with: pip install ollama\n"
                "Also ensure Ollama is running: https://ollama.ai"
            )

        try:
            client = ollama.Client(host=self._host)
            response = client.generate(
                model=self._model,
                prompt=prompt,
                options={"num_predict": max_tokens}
            )
            # Ollama doesn't report token counts in the same way
            return response["response"], 0
        except Exception as e:
            raise RuntimeError(
                f"Ollama error: {e}\n"
                f"Ensure Ollama is running and model '{self._model}' is pulled:\n"
                f"  ollama pull {self._model}"
            )


def get_llm_provider(
    provider: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None
) -> LLMProvider:
    """Factory function to get the appropriate LLM provider.

    Args:
        provider: "anthropic" or "ollama" (defaults to LLM_PROVIDER env var or "anthropic")
        api_key: API key for Anthropic (optional, uses env var)
        model: Model override (optional, uses defaults)

    Returns:
        LLMProvider instance

    Raises:
        ValueError: If unknown provider specified
    """
    provider = provider or os.environ.get("LLM_PROVIDER", "anthropic")

    if provider == "anthropic":
        kwargs = {}
        if api_key:
            kwargs["api_key"] = api_key
        if model:
            kwargs["model"] = model
        return AnthropicProvider(**kwargs)

    elif provider == "ollama":
        kwargs = {}
        if model:
            kwargs["model"] = model
        return OllamaProvider(**kwargs)

    else:
        raise ValueError(
            f"Unknown LLM provider: {provider}. "
            f"Supported providers: anthropic, ollama"
        )


class LLMAnalyzer:
    """Analyzer for NBA matchups using LLM.

    Provides qualitative insights on injuries, rest, motivation, and matchup dynamics
    that complement statistical probability models.

    Supports multiple providers:
    - anthropic (default): Claude for production quality
    - ollama: Local models for free testing
    """

    def __init__(
        self,
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None
    ):
        """Initialize LLM analyzer.

        Args:
            provider: "anthropic" or "ollama" (defaults to LLM_PROVIDER env var)
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
            model: Model to use (defaults vary by provider)

        Raises:
            ValueError: If no API key for Anthropic or unknown provider
        """
        self._provider = get_llm_provider(provider, api_key, model)

    @property
    def model(self) -> str:
        """Return the model being used."""
        return self._provider.model_name

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
        """Analyze matchup using LLM for qualitative insights.

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

        # Generate response
        try:
            raw_text, tokens = self._provider.generate(prompt, max_tokens)

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
                model_used=self._provider.model_name,
                tokens_used=tokens
            )

        except RuntimeError as e:
            # Return partial analysis with error
            return MatchupAnalysis(
                home_team=home_team,
                away_team=away_team,
                raw_analysis=f"LLM Error: {str(e)}",
                home_factors=[],
                away_factors=[],
                biggest_edge="Analysis failed due to LLM error",
                risk_factors=[],
                contrarian_angle="",
                model_used=self._provider.model_name,
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
    provider: Optional[str] = None,
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
        provider: LLM provider ("anthropic" or "ollama")
        api_key: Optional API key for Anthropic

    Returns:
        MatchupAnalysis with LLM insights

    Raises:
        ValueError: If no API key available for Anthropic
        RuntimeError: If LLM call fails
    """
    analyzer = LLMAnalyzer(provider=provider, api_key=api_key)
    return analyzer.analyze_matchup(
        home_team, away_team, game_date, team_stats, injuries, odds_data
    )
