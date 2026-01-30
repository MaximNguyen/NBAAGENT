"""Typer CLI entry point for NBA betting analysis.

Provides natural language interface:
- nba-ev analyze "find +ev games tonight"
- nba-ev version
"""

import os

from dotenv import load_dotenv

# Load .env file before anything else
load_dotenv()

import typer
from rich.console import Console

# Force colors on Windows if terminal supports it
if os.name == 'nt':
    os.system('')  # Enable ANSI escape codes on Windows
from rich.panel import Panel
from rich.table import Table

from nba_betting_agent import __version__
from nba_betting_agent.cli.parser import parse_query
from nba_betting_agent.graph.graph import invoke_with_tracing
from nba_betting_agent.monitoring import configure_logging

# Create Typer app
cli = typer.Typer(
    name="nba-ev",
    help="""NBA Betting Analysis - Find +EV opportunities using multi-agent analysis.

WHAT IT DOES:
  Analyzes NBA betting lines across multiple sportsbooks to find positive
  expected value (+EV) opportunities. Uses real-time odds data, team stats,
  and injury reports to calculate fair probabilities.

QUICK START:
  nba-ev analyze "find best bets tonight"
  nba-ev analyze "celtics vs lakers" --min-ev 0.05
  nba-ev analyze "all games" --min-ev -1 --limit 10

DATA SOURCES:
  • Odds: The Odds API (DraftKings, FanDuel, BetMGM, etc.)
  • Stats: NBA API (team records, advanced metrics)
  • Injuries: ESPN injury reports
""",
    add_completion=False,
)

# Rich console for formatted output
# Disable colors if NO_COLOR env var is set (standard convention)
console = Console(force_terminal=True, no_color=os.getenv("NO_COLOR") is not None)


def _get_default_min_ev() -> float:
    """Get default min_ev from environment or use 0.02."""
    env_val = os.getenv("DEFAULT_MIN_EV")
    if env_val is not None:
        try:
            return float(env_val)
        except ValueError:
            pass
    return 0.02


@cli.command()
def analyze(
    query: str = typer.Argument(..., help="Natural language query (e.g., 'best bets tonight', 'celtics vs lakers')"),
    min_ev: float = typer.Option(None, "--min-ev", "-e", help="Min EV threshold (0.02 = 2%). Use -1 to see all bets. Default from DEFAULT_MIN_EV env var"),
    limit: int = typer.Option(5, "--limit", "-n", help="Show top N bets (default: 5, use 0 for all)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed stats and processing info"),
):
    """Analyze NBA games for betting opportunities.

    Shows the top bets sorted by expected value (EV). Positive EV means
    the bet has an edge over the sportsbook.

    \b
    EXAMPLES:
      nba-ev analyze "best bets tonight"          # Top 5 +EV bets for today
      nba-ev analyze "celtics vs lakers"          # Specific matchup analysis
      nba-ev analyze "all games" --min-ev -1      # All bets including -EV
      nba-ev analyze "tonight" -n 10 -e 0.01      # Top 10 with 1% min EV

    \b
    UNDERSTANDING EV:
      +2.5% EV = For every $100 bet, expect $2.50 profit long-term
      -3.0% EV = House edge of 3% (typical sportsbook vig)
    """
    # Parse natural language query
    parsed = parse_query(query)

    # Build filter_params from parsed query and CLI options
    # Priority: CLI flag > parsed query > env var > default (0.02)
    filter_params = {}
    if min_ev is not None:
        # CLI flag provided
        filter_params["min_ev"] = min_ev
    elif parsed.min_ev is not None:
        # Parsed from natural language query
        filter_params["min_ev"] = parsed.min_ev
    else:
        # Use environment variable or default
        filter_params["min_ev"] = _get_default_min_ev()
    filter_params["confidence"] = parsed.confidence
    # CLI --limit takes precedence; 0 means show all (no limit)
    filter_params["limit"] = limit if limit != 5 else (parsed.limit if parsed.limit is not None else limit)
    if filter_params["limit"] == 0:
        filter_params["limit"] = None  # No limit
    # Note: team filter already applied via state.teams, market not yet supported

    if verbose:
        # Display parsed query details
        console.print(Panel.fit(
            f"[bold cyan]Query:[/bold cyan] {parsed.original}\n"
            f"[bold cyan]Date:[/bold cyan] {parsed.game_date or 'Any'}\n"
            f"[bold cyan]Teams:[/bold cyan] {', '.join(parsed.teams) if parsed.teams else 'All'}\n"
            f"[bold cyan]Bet Type:[/bold cyan] {parsed.bet_type or 'All'}\n"
            f"[bold cyan]Min EV:[/bold cyan] {filter_params.get('min_ev', 0) * 100:.1f}%\n"
            f"[bold cyan]Confidence:[/bold cyan] {filter_params.get('confidence') or 'Any'}\n"
            f"[bold cyan]Limit:[/bold cyan] {filter_params.get('limit') or 'All (use --limit 0 for all)'}",
            title="Parsed Query",
            border_style="cyan",
        ))
        console.print()

    # Invoke LangGraph workflow with tracing metadata
    try:
        # Build trace tags and metadata for LangSmith filtering
        tags = ["cli", "production"]
        if parsed.teams:
            tags.append("team-specific")
        if filter_params.get("confidence"):
            tags.append(f"confidence-{filter_params['confidence']}")

        metadata = {
            "query_type": "game_analysis",
            "min_ev_threshold": filter_params.get("min_ev", 0),
            "has_team_filter": bool(parsed.teams),
            "has_confidence_filter": bool(filter_params.get("confidence")),
            "limit": filter_params.get("limit"),
        }

        result = invoke_with_tracing(
            state={
                "query": query,
                "game_date": parsed.game_date,
                "teams": parsed.teams or [],
                "filter_params": filter_params,
                "errors": [],
                "messages": [],
                "odds_data": [],
                "line_discrepancies": [],
                "team_stats": {},
                "player_stats": {},
                "injuries": [],
                "estimated_probabilities": {},
                "expected_values": [],
                "opportunities": [],
                "recommendation": "",
            },
            tags=tags,
            metadata=metadata,
        )

        # Display results
        _display_results(result, verbose)

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}", style="red")
        raise typer.Exit(code=1)


@cli.command()
def version():
    """Show version and configuration info."""
    console.print(f"[bold cyan]NBA Betting Analysis[/bold cyan] v{__version__}")
    console.print()
    console.print("[bold]Configuration:[/bold]")
    console.print(f"  Odds API: {'✓ configured' if os.getenv('ODDS_API_KEY') else '✗ missing ODDS_API_KEY'}")
    console.print(f"  LLM: {os.getenv('LLM_PROVIDER', 'anthropic')} ({os.getenv('OLLAMA_MODEL', 'claude') if os.getenv('LLM_PROVIDER') == 'ollama' else 'claude-sonnet-4'})")
    console.print(f"  Default Min EV: {_get_default_min_ev()} ({_get_default_min_ev() * 100:.0f}%)")
    console.print(f"  Tracing: {'enabled' if os.getenv('LANGSMITH_TRACING') == 'true' else 'disabled'}")


def _display_results(result: dict, verbose: bool):
    """Display analysis results with Rich formatting.

    Args:
        result: StateGraph invocation result
        verbose: Whether to show detailed information
    """
    recommendation = result.get("recommendation", "No recommendation available")

    # recommendation is now Rich-formatted from communication_agent
    # Print directly without wrapping in Panel
    console.print(recommendation)

    # Verbose details
    if verbose:
        console.print()

        # Errors table
        errors = result.get("errors", [])
        if errors:
            error_table = Table(title="Processing Details", show_header=False)
            error_table.add_column("Agent", style="cyan")
            error_table.add_column("Status", style="dim")

            for error in errors:
                # Parse agent name from error message
                if ":" in error:
                    agent, status = error.split(":", 1)
                    error_table.add_row(agent.strip(), status.strip())
                else:
                    error_table.add_row("System", error)

            console.print(error_table)
            console.print()

        # Data summary
        odds_count = len(result.get("odds_data", []))
        ev_count = len(result.get("expected_values", []))
        opps_count = len(result.get("opportunities", []))

        summary = Table(title="Data Summary", show_header=False)
        summary.add_column("Metric", style="bold")
        summary.add_column("Value")

        summary.add_row("Odds Sources", str(odds_count))
        summary.add_row("Opportunities Found", str(opps_count))
        summary.add_row("Expected Values", str(ev_count))
        summary.add_row("Line Discrepancies", str(len(result.get("line_discrepancies", []))))

        console.print(summary)


def main():
    """Entry point for CLI."""
    # Configure structured logging
    # Use production mode if LOG_MODE=production, otherwise development
    log_mode = os.getenv("LOG_MODE", "development")
    configure_logging(log_mode)

    cli()


if __name__ == "__main__":
    main()
