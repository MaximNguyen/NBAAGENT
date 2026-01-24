"""Rich table formatters for betting opportunities display.

Formats BettingOpportunity objects into terminal tables with proper styling,
color-coded confidence levels, and detailed view panels.
"""

from typing import Optional

from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from nba_betting_agent.agents.analysis_agent.agent import BettingOpportunity


def format_american_odds(decimal_odds: float) -> str:
    """Convert decimal odds to American odds format.

    Args:
        decimal_odds: Odds in decimal format (e.g., 2.5)

    Returns:
        American odds string (e.g., "+150" or "-200")
    """
    if decimal_odds >= 2.0:
        # Underdog
        american = int((decimal_odds - 1) * 100)
        return f"+{american}"
    else:
        # Favorite
        american = int(-100 / (decimal_odds - 1))
        return f"{american}"


def format_opportunities_table(
    opportunities: list[BettingOpportunity], active_filters: dict = None
) -> Table:
    """Format betting opportunities as Rich table.

    Args:
        opportunities: List of BettingOpportunity objects
        active_filters: Dict of active filters for caption display

    Returns:
        Rich Table with sorted opportunities (by EV descending)
    """
    # Sort by EV descending (requirement OUT-01)
    sorted_opps = sorted(opportunities, key=lambda x: x.ev_pct, reverse=True)

    # Build caption with count and filters
    caption_parts = []
    if active_filters:
        filter_summary = _format_filter_summary(active_filters)
        if filter_summary:
            caption_parts.append(f"Filters: {filter_summary}")

    caption = " | ".join(caption_parts) if caption_parts else None

    # Create table
    table = Table(
        title="Betting Opportunities",
        caption=caption,
        show_header=True,
        header_style="bold cyan",
    )

    # Add columns with proper alignment
    table.add_column("Rank", justify="right", style="dim", width=4)
    table.add_column("Matchup", justify="left", style="white", no_wrap=True)
    table.add_column("Market", justify="center", style="yellow")
    table.add_column("Our Prob", justify="right", style="cyan")
    table.add_column("Market Odds", justify="right", style="magenta")
    table.add_column("EV %", justify="right", style="bold green")
    table.add_column("Kelly %", justify="right", style="green")
    table.add_column("Confidence", justify="center")

    # Handle empty list
    if not sorted_opps:
        table.add_row("", "[dim]No opportunities found[/dim]", "", "", "", "", "", "")
        return table

    # Add rows
    for idx, opp in enumerate(sorted_opps, start=1):
        # Format market column (e.g., "h2h BOS" or "spreads LAL -3.5")
        market_display = _format_market_display(opp)

        # Format probabilities
        our_prob_str = f"{opp.our_prob * 100:.1f}%"

        # Format market odds as American
        market_odds_str = format_american_odds(opp.market_odds)

        # Format EV with + sign
        ev_str = f"+{opp.ev_pct:.1f}%"

        # Format Kelly percentage
        kelly_str = f"{opp.kelly_bet_pct:.1f}%"

        # Color-code confidence
        confidence_str = _format_confidence(opp.confidence)

        table.add_row(
            str(idx),
            opp.matchup,
            market_display,
            our_prob_str,
            market_odds_str,
            ev_str,
            kelly_str,
            confidence_str,
        )

    return table


def format_opportunity_detail(
    opp: BettingOpportunity, team_stats: dict = None
) -> Panel:
    """Format detailed view of a betting opportunity.

    Args:
        opp: BettingOpportunity object
        team_stats: Optional team stats for additional context

    Returns:
        Rich Panel with detailed breakdown
    """
    lines = []

    # Matchup and market info
    lines.append(f"[bold white]{opp.matchup}[/bold white]")
    lines.append(f"Market: [yellow]{opp.market}[/yellow] - {opp.outcome}")
    lines.append(f"Bookmaker: [cyan]{opp.bookmaker}[/cyan]")
    lines.append("")

    # EV calculation breakdown
    lines.append("[bold]Expected Value Breakdown:[/bold]")
    lines.append(f"  Our Probability: [cyan]{opp.our_prob * 100:.1f}%[/cyan]")
    lines.append(f"  Market Odds: [magenta]{format_american_odds(opp.market_odds)}[/magenta] (decimal: {opp.market_odds:.2f})")
    lines.append(f"  Fair Odds: [blue]{opp.fair_odds:.2f}[/blue] (after vig removal)")
    lines.append(f"  Expected Value: [bold green]+{opp.ev_pct:.2f}%[/bold green]")
    lines.append(f"  Kelly Bet Size: [green]{opp.kelly_bet_pct:.2f}%[/green] of bankroll")
    lines.append(f"  Confidence: {_format_confidence(opp.confidence)}")
    lines.append("")

    # Sharp edge if present
    if opp.sharp_edge is not None:
        lines.append(f"[bold]Sharp Edge:[/bold] [green]+{opp.sharp_edge:.2f}%[/green]")
        lines.append("  (Edge vs sharp book reference price)")
        lines.append("")

    # RLM signal if present
    if opp.rlm_signal:
        lines.append(f"[bold]Reverse Line Movement:[/bold] [yellow]{opp.rlm_signal}[/yellow]")
        lines.append("  (Sharp money may be on this side)")
        lines.append("")

    # LLM insight if present
    if opp.llm_insight:
        lines.append("[bold]AI Analysis:[/bold]")
        lines.append(f"  {opp.llm_insight}")
        lines.append("")

    # Team stats summary if provided
    if team_stats:
        lines.append("[bold]Team Stats Summary:[/bold]")
        # Extract teams from matchup (e.g., "BOS @ LAL")
        teams = opp.matchup.replace(" @ ", " ").split()
        if len(teams) >= 2:
            for team in teams[:2]:
                team_upper = team.upper()
                if team_upper in team_stats:
                    stats = team_stats[team_upper]
                    if isinstance(stats, dict):
                        record = stats.get("record", "N/A")
                        lines.append(f"  {team}: {record}")

    content = "\n".join(lines)

    return Panel(
        content,
        title=f"[bold]{opp.outcome}[/bold]",
        border_style="green" if opp.ev_pct >= 5.0 else "yellow",
    )


def _format_market_display(opp: BettingOpportunity) -> str:
    """Format market column display.

    Args:
        opp: BettingOpportunity object

    Returns:
        Formatted market string (e.g., "h2h BOS" or "spreads LAL -3.5")
    """
    # Extract team abbreviation from outcome (usually first 3 chars for team codes)
    outcome_short = opp.outcome[:3].upper() if len(opp.outcome) >= 3 else opp.outcome

    # For h2h markets, just show market and team
    if opp.market == "h2h":
        return f"{opp.market} {outcome_short}"

    # For spreads/totals, include in outcome description
    return f"{opp.market} {outcome_short}"


def _format_confidence(confidence: str) -> str:
    """Color-code confidence level.

    Args:
        confidence: Confidence level string (high/medium/low)

    Returns:
        Rich markup string with color coding
    """
    confidence_lower = confidence.lower()

    if confidence_lower == "high":
        return "[bold green]HIGH[/bold green]"
    elif confidence_lower == "medium":
        return "[yellow]MEDIUM[/yellow]"
    else:
        return "[dim]LOW[/dim]"


def _format_filter_summary(filters: dict) -> str:
    """Format active filters for caption display.

    Args:
        filters: Dict of active filters

    Returns:
        Human-readable filter summary string
    """
    parts = []

    if filters.get("min_ev"):
        parts.append(f"min_ev={filters['min_ev']}%")

    if filters.get("max_ev"):
        parts.append(f"max_ev={filters['max_ev']}%")

    if filters.get("confidence"):
        parts.append(f"confidence={filters['confidence']}")

    if filters.get("team"):
        parts.append(f"team={filters['team']}")

    if filters.get("market"):
        parts.append(f"market={filters['market']}")

    return ", ".join(parts)
