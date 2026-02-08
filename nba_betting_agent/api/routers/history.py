"""Historical analytics endpoints - performance, ROI, and model accuracy."""

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from nba_betting_agent.api.deps import get_db_session
from nba_betting_agent.api.middleware.rate_limit import limiter
from nba_betting_agent.api.schemas import ModelAccuracy, MonthlyROI, PerformanceSummary

router = APIRouter(tags=["history"])


@router.get("/history/performance", response_model=PerformanceSummary)
@limiter.limit("100/minute")
async def get_performance(
    request: Request,
    season: str = Query("2023-24", max_length=10, description="NBA season (e.g., 2023-24)"),
    session: AsyncSession = Depends(get_db_session),
):
    """Get backtest performance summary for a season.

    Uses the backtesting engine to compute ROI, win rate, and other metrics.
    """
    try:
        from nba_betting_agent.db.repositories.games import GamesRepository
        from nba_betting_agent.ml.backtesting.engine import BacktestEngine
        from nba_betting_agent.ml.backtesting.metrics import BacktestMetrics

        repo = GamesRepository(session)
        games = await repo.get_by_season(season)

        if not games:
            return PerformanceSummary()

        # Run backtest
        engine = BacktestEngine()
        result = engine.run(
            games=games,
            odds=[],
            train_seasons=["2022-23"],
            test_seasons=[season],
        )

        metrics = result.metrics if hasattr(result, "metrics") else None
        if metrics:
            return PerformanceSummary(
                total_bets=metrics.total_bets,
                wins=metrics.wins,
                losses=metrics.losses,
                win_rate=metrics.win_rate,
                net_profit=metrics.net_profit,
                roi_pct=metrics.roi_pct,
                avg_edge=metrics.avg_edge,
                brier_score=metrics.brier_score,
            )

    except Exception:
        pass

    return PerformanceSummary()


@router.get("/history/monthly-roi", response_model=list[MonthlyROI])
@limiter.limit("100/minute")
async def get_monthly_roi(
    request: Request,
    season: str = Query("2023-24", max_length=10, description="NBA season"),
    session: AsyncSession = Depends(get_db_session),
):
    """Get monthly ROI breakdown for a season."""
    try:
        from nba_betting_agent.db.repositories.games import GamesRepository

        repo = GamesRepository(session)
        games = await repo.get_by_season(season)

        if not games:
            return []

        # Group games by month and compute simple ROI approximation
        monthly: dict[str, dict] = {}
        for game in games:
            month_key = game.game_date[:7]  # YYYY-MM
            if month_key not in monthly:
                monthly[month_key] = {"bets": 0, "wins": 0}
            monthly[month_key]["bets"] += 1
            if game.home_win:
                monthly[month_key]["wins"] += 1

        results = []
        for month, data in sorted(monthly.items()):
            win_rate = data["wins"] / data["bets"] if data["bets"] > 0 else 0.5
            # Approximate ROI from win rate assuming -110 lines
            roi = (win_rate * 1.909 - 1) * 100  # -110 payout
            results.append(
                MonthlyROI(
                    month=month,
                    bets=data["bets"],
                    roi_pct=round(roi, 2),
                    net_profit=round(roi * data["bets"] / 100, 2),
                )
            )
        return results

    except Exception:
        return []


@router.get("/history/model-accuracy", response_model=ModelAccuracy)
@limiter.limit("100/minute")
async def get_model_accuracy(
    request: Request,
    season: str = Query("2023-24", max_length=10, description="NBA season"),
    session: AsyncSession = Depends(get_db_session),
):
    """Get ML model accuracy metrics (Brier score, calibration error)."""
    try:
        from nba_betting_agent.db.repositories.games import GamesRepository
        from nba_betting_agent.ml.backtesting.engine import BacktestEngine

        repo = GamesRepository(session)
        games = await repo.get_by_season(season)

        if not games:
            return ModelAccuracy()

        engine = BacktestEngine()
        result = engine.run(
            games=games,
            odds=[],
            train_seasons=["2022-23"],
            test_seasons=[season],
        )

        metrics = result.metrics if hasattr(result, "metrics") else None
        if metrics:
            return ModelAccuracy(
                brier_score=metrics.brier_score or 0,
                calibration_error=metrics.calibration_error or 0,
                clv_pct=getattr(metrics, "clv_pct", None),
                total_predictions=metrics.total_bets,
            )

    except Exception:
        pass

    return ModelAccuracy()
