"""Human-readable backtest report generation.

Provides formatted output for backtest results using Rich
for terminal display.
"""

from dataclasses import dataclass, field
from datetime import datetime
from io import StringIO

from rich.console import Console
from rich.table import Table

from nba_betting_agent.ml.backtesting.metrics import BacktestMetrics


@dataclass
class BacktestReport:
    """Human-readable backtest report.

    Attributes:
        summary: Brief summary of results
        metrics: Aggregated performance metrics
        monthly_breakdown: ROI by month
        top_bets: Best performing bets
        worst_bets: Worst performing bets
        recommendations: Actionable insights
    """

    summary: str
    metrics: BacktestMetrics
    monthly_breakdown: list[dict] = field(default_factory=list)
    top_bets: list[dict] = field(default_factory=list)
    worst_bets: list[dict] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)


def generate_report(result: "BacktestResult") -> BacktestReport:  # type: ignore[name-defined]
    """Generate a human-readable report from backtest results.

    Args:
        result: BacktestResult from running a backtest

    Returns:
        BacktestReport with formatted analysis
    """
    from nba_betting_agent.ml.backtesting.engine import BacktestResult

    metrics = result.metrics

    # Generate summary
    seasons = ", ".join(result.test_seasons)
    roi_status = "PROFITABLE" if metrics.roi_pct > 0 else "UNPROFITABLE"
    brier_status = "PASS" if metrics.brier_score < 0.25 else "FAIL"

    summary = (
        f"Backtest over {seasons}: {metrics.total_bets} bets placed. "
        f"ROI: {metrics.roi_pct:+.2f}% ({roi_status}). "
        f"Brier Score: {metrics.brier_score:.3f} ({brier_status}). "
        f"Final bankroll: ${result.final_bankroll:,.2f}"
    )

    # Monthly breakdown
    monthly = _calculate_monthly_breakdown(result.bets)

    # Top and worst bets (by profit)
    sorted_bets = sorted(result.bets, key=lambda b: b.get("profit", 0), reverse=True)
    top_bets = sorted_bets[:5] if len(sorted_bets) >= 5 else sorted_bets
    worst_bets = sorted_bets[-5:][::-1] if len(sorted_bets) >= 5 else []

    # Generate recommendations
    recommendations = _generate_recommendations(metrics, monthly)

    return BacktestReport(
        summary=summary,
        metrics=metrics,
        monthly_breakdown=monthly,
        top_bets=top_bets,
        worst_bets=worst_bets,
        recommendations=recommendations,
    )


def format_report(report: BacktestReport) -> str:
    """Format a backtest report for terminal display.

    Uses Rich for table formatting and colors.

    Args:
        report: BacktestReport to format

    Returns:
        Formatted string for terminal output
    """
    # Use string buffer for capture
    buffer = StringIO()
    console = Console(file=buffer, force_terminal=True, width=100)

    # Header
    console.print("\n[bold blue]=== Backtest Report ===[/bold blue]\n")

    # Summary
    console.print(f"[white]{report.summary}[/white]\n")

    # Key Metrics Table
    metrics_table = Table(title="Key Metrics", show_header=True)
    metrics_table.add_column("Metric", style="cyan")
    metrics_table.add_column("Value", style="white", justify="right")
    metrics_table.add_column("Status", style="white", justify="center")

    m = report.metrics
    metrics_table.add_row(
        "Total Bets",
        str(m.total_bets),
        "",
    )
    metrics_table.add_row(
        "Win Rate",
        f"{m.win_rate * 100:.1f}%",
        "[green]OK[/green]" if m.win_rate > 0.5 else "[yellow]LOW[/yellow]",
    )
    metrics_table.add_row(
        "ROI",
        f"{m.roi_pct:+.2f}%",
        "[green]PROFIT[/green]" if m.roi_pct > 0 else "[red]LOSS[/red]",
    )
    metrics_table.add_row(
        "Net Profit",
        f"${m.net_profit:+,.2f}",
        "",
    )
    metrics_table.add_row(
        "Brier Score",
        f"{m.brier_score:.3f}",
        "[green]PASS[/green]" if m.brier_score < 0.25 else "[red]FAIL[/red]",
    )
    metrics_table.add_row(
        "Calibration Error",
        f"{m.calibration_error:.3f}",
        "[green]GOOD[/green]" if m.calibration_error < 0.05 else "[yellow]FAIR[/yellow]",
    )
    metrics_table.add_row(
        "Avg Edge",
        f"{m.avg_edge * 100:.2f}%",
        "",
    )

    console.print(metrics_table)

    # Monthly Breakdown
    if report.monthly_breakdown:
        console.print("\n[bold blue]=== Monthly Breakdown ===[/bold blue]\n")
        monthly_table = Table(show_header=True)
        monthly_table.add_column("Month", style="cyan")
        monthly_table.add_column("Bets", justify="right")
        monthly_table.add_column("Wins", justify="right")
        monthly_table.add_column("ROI", justify="right")
        monthly_table.add_column("Profit", justify="right")

        for month in report.monthly_breakdown:
            roi_str = f"{month['roi']:+.1f}%"
            roi_color = "[green]" if month["roi"] > 0 else "[red]"
            monthly_table.add_row(
                month["month"],
                str(month["bets"]),
                str(month["wins"]),
                f"{roi_color}{roi_str}[/]",
                f"${month['profit']:+,.2f}",
            )

        console.print(monthly_table)

    # Top Bets
    if report.top_bets:
        console.print("\n[bold blue]=== Top 5 Bets ===[/bold blue]\n")
        top_table = Table(show_header=True)
        top_table.add_column("Date", style="cyan")
        top_table.add_column("Game", style="white")
        top_table.add_column("EV", justify="right")
        top_table.add_column("Odds", justify="right")
        top_table.add_column("Profit", justify="right")

        for bet in report.top_bets:
            date_str = _format_date(bet.get("game_date"))
            game = f"{bet.get('away_team', '?')} @ {bet.get('home_team', '?')}"
            profit_str = f"${bet.get('profit', 0):+,.2f}"

            top_table.add_row(
                date_str,
                game,
                f"{bet.get('ev', 0) * 100:.1f}%",
                f"{bet.get('market_odds', 0):.2f}",
                f"[green]{profit_str}[/green]",
            )

        console.print(top_table)

    # Worst Bets
    if report.worst_bets:
        console.print("\n[bold blue]=== Worst 5 Bets ===[/bold blue]\n")
        worst_table = Table(show_header=True)
        worst_table.add_column("Date", style="cyan")
        worst_table.add_column("Game", style="white")
        worst_table.add_column("EV", justify="right")
        worst_table.add_column("Odds", justify="right")
        worst_table.add_column("Profit", justify="right")

        for bet in report.worst_bets:
            date_str = _format_date(bet.get("game_date"))
            game = f"{bet.get('away_team', '?')} @ {bet.get('home_team', '?')}"
            profit_str = f"${bet.get('profit', 0):+,.2f}"

            worst_table.add_row(
                date_str,
                game,
                f"{bet.get('ev', 0) * 100:.1f}%",
                f"{bet.get('market_odds', 0):.2f}",
                f"[red]{profit_str}[/red]",
            )

        console.print(worst_table)

    # Recommendations
    if report.recommendations:
        console.print("\n[bold blue]=== Recommendations ===[/bold blue]\n")
        for rec in report.recommendations:
            console.print(f"  [yellow]*[/yellow] {rec}")

    console.print("")

    return buffer.getvalue()


def _calculate_monthly_breakdown(bets: list[dict]) -> list[dict]:
    """Calculate ROI breakdown by month."""
    if not bets:
        return []

    # Group bets by year-month
    monthly: dict[str, list[dict]] = {}
    for bet in bets:
        game_date = bet.get("game_date")
        if game_date is None:
            continue

        if hasattr(game_date, "strftime"):
            month_key = game_date.strftime("%Y-%m")
        else:
            month_key = str(game_date)[:7]

        if month_key not in monthly:
            monthly[month_key] = []
        monthly[month_key].append(bet)

    # Calculate metrics per month
    result = []
    for month_key in sorted(monthly.keys()):
        month_bets = monthly[month_key]
        wins = sum(1 for b in month_bets if b.get("won", False))
        wagered = sum(b.get("wager", 0) for b in month_bets)
        returned = sum(b.get("returned", 0) for b in month_bets)
        profit = returned - wagered
        roi = ((returned - wagered) / wagered * 100) if wagered > 0 else 0

        result.append(
            {
                "month": month_key,
                "bets": len(month_bets),
                "wins": wins,
                "wagered": wagered,
                "returned": returned,
                "profit": profit,
                "roi": roi,
            }
        )

    return result


def _generate_recommendations(
    metrics: BacktestMetrics, monthly: list[dict]
) -> list[str]:
    """Generate actionable recommendations based on metrics."""
    recommendations = []

    # ROI-based recommendations
    if metrics.roi_pct < -5:
        recommendations.append(
            "Consider raising the EV threshold to be more selective with bets."
        )
    elif metrics.roi_pct > 10:
        recommendations.append(
            "Strong positive ROI. Consider gradually increasing bet sizes."
        )

    # Brier score recommendations
    if metrics.brier_score >= 0.25:
        recommendations.append(
            "Brier score above 0.25 suggests poor calibration. "
            "Review model training data and recalibrate."
        )
    elif metrics.brier_score < 0.20:
        recommendations.append(
            "Excellent Brier score indicates well-calibrated probabilities."
        )

    # Calibration error recommendations
    if metrics.calibration_error > 0.10:
        recommendations.append(
            "High calibration error suggests systematic over/under confidence. "
            "Consider recalibrating with more recent data."
        )

    # Win rate recommendations
    if metrics.win_rate < 0.45:
        recommendations.append(
            "Low win rate may indicate model is targeting too many longshots. "
            "Consider filtering for higher probability games."
        )

    # Sample size recommendations
    if metrics.total_bets < 50:
        recommendations.append(
            "Small sample size. Results may not be statistically significant. "
            "Run backtest over more seasons for reliability."
        )

    # Monthly variance
    if monthly:
        rois = [m["roi"] for m in monthly]
        if rois:
            import numpy as np

            roi_std = float(np.std(rois))
            if roi_std > 15:
                recommendations.append(
                    f"High monthly variance (std: {roi_std:.1f}%). "
                    "Consider more conservative bet sizing for stability."
                )

    if not recommendations:
        recommendations.append(
            "Model performance is within acceptable parameters. "
            "Continue monitoring and validate with live results."
        )

    return recommendations


def _format_date(date_val) -> str:
    """Format a date value for display."""
    if date_val is None:
        return "N/A"

    if hasattr(date_val, "strftime"):
        return date_val.strftime("%Y-%m-%d")

    return str(date_val)[:10]
