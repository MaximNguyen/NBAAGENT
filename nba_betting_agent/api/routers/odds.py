"""Odds comparison endpoints."""

from fastapi import APIRouter, HTTPException, Path

from nba_betting_agent.api.schemas import OddsComparisonResponse, OddsOutcome
from nba_betting_agent.api.state import analysis_store

router = APIRouter(tags=["odds"])


@router.get("/odds/{game_id}/comparison", response_model=OddsComparisonResponse)
async def get_odds_comparison(game_id: str = Path(..., max_length=100)):
    """Get cross-book odds comparison matrix for a game.

    Rows = outcomes, columns = sportsbooks, best odds highlighted.
    """
    latest = analysis_store.get_latest()
    if not latest or not latest.result:
        raise HTTPException(status_code=404, detail="No analysis data available. Run an analysis first.")

    odds_data = latest.result.get("odds_data", [])

    # Find the game in odds_data
    game_odds = None
    for game in odds_data:
        if game.get("id") == game_id:
            game_odds = game
            break

    if not game_odds:
        raise HTTPException(status_code=404, detail=f"Game {game_id} not found in latest analysis.")

    matchup = f"{game_odds.get('home_team', '?')} vs {game_odds.get('away_team', '?')}"

    # Build outcomes list from all bookmakers
    outcomes: list[OddsOutcome] = []
    best_odds: dict[str, OddsOutcome] = {}

    for bookmaker in game_odds.get("bookmakers", []):
        book_name = bookmaker.get("key", bookmaker.get("title", "unknown"))
        for market in bookmaker.get("markets", []):
            market_key = market.get("key", "h2h")
            for outcome in market.get("outcomes", []):
                odds_outcome = OddsOutcome(
                    outcome=outcome.get("name", ""),
                    bookmaker=book_name,
                    price=outcome.get("price", 0),
                    point=outcome.get("point"),
                )
                outcomes.append(odds_outcome)

                # Track best odds per outcome
                outcome_key = f"{market_key}:{outcome.get('name', '')}"
                if outcome_key not in best_odds or odds_outcome.price > best_odds[outcome_key].price:
                    best_odds[outcome_key] = odds_outcome

    return OddsComparisonResponse(
        game_id=game_id,
        matchup=matchup,
        market="h2h",
        outcomes=outcomes,
        best_odds=best_odds,
    )
