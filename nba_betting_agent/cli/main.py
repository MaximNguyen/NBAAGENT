"""Typer CLI entry point for NBA betting analysis.

Provides natural language interface:
- nba-ev analyze "find +ev games tonight"
- nba-ev version
"""

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from nba_betting_agent import __version__
from nba_betting_agent.cli.parser import parse_query
from nba_betting_agent.graph import app

# Create Typer app
cli = typer.Typer(
    name="nba-ev",
    help="NBA Betting Analysis - Find +EV opportunities using multi-agent analysis",
    add_completion=False,
)

# Rich console for formatted output
console = Console()


@cli.command()
def analyze(
    query: str = typer.Argument(..., help="Natural language query (e.g., 'find +ev games tonight')"),
    min_ev: float = typer.Option(0.02, "--min-ev", help="Minimum expected value threshold (default: 2%)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed analysis"),
):
    """Analyze NBA games for positive expected value betting opportunities.

    Examples:
        nba-ev analyze "find +ev games tonight"
        nba-ev analyze "best bets for celtics vs lakers" --min-ev 0.05
        nba-ev analyze "show me props for next week" --verbose
    """
    # Parse natural language query
    parsed = parse_query(query)

    # Build filter_params from parsed query and CLI options
    # CLI option min_ev takes precedence over parsed natural language
    filter_params = {}
    filter_params["min_ev"] = min_ev if min_ev > 0 else parsed.min_ev
    filter_params["confidence"] = parsed.confidence
    filter_params["limit"] = parsed.limit
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
            f"[bold cyan]Limit:[/bold cyan] {filter_params.get('limit') or 'All'}",
            title="Parsed Query",
            border_style="cyan",
        ))
        console.print()

    # Invoke LangGraph workflow
    try:
        result = app.invoke({
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
        })

        # Display results
        _display_results(result, verbose)

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}", style="red")
        raise typer.Exit(code=1)


@cli.command()
def version():
    """Show version information."""
    console.print(f"[bold cyan]NBA Betting Analysis[/bold cyan] v{__version__}")
    console.print("Multi-agent system for finding +EV NBA betting opportunities")


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
    cli()


if __name__ == "__main__":
    main()
