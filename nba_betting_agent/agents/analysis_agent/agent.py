"""Analysis Agent for calculating probabilities and expected values.

Integrates:
- Vig removal for fair odds calculation
- Probability calibration (Platt scaling)
- EV calculation for betting opportunities
- Sharp/soft book comparison
- Reverse line movement detection
- LLM matchup analysis (optional)
- ML-based probability estimation (Phase 7)
"""

import asyncio
import os
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Optional

from nba_betting_agent.agents.analysis_agent.vig_removal import (
    remove_vig,
    calculate_fair_odds,
)
from nba_betting_agent.agents.analysis_agent.ev_calculator import (
    calculate_ev,
    calculate_kelly_bet,
)
from nba_betting_agent.agents.analysis_agent.calibration import (
    ProbabilityCalibrator,
    calibrate_probability,
)
from nba_betting_agent.agents.analysis_agent.sharp_comparison import (
    find_soft_book_edges,
    SHARP_BOOKS,
)
from nba_betting_agent.agents.analysis_agent.rlm_detector import detect_rlm
from nba_betting_agent.agents.analysis_agent.clv_tracker import CLVTracker
from nba_betting_agent.agents.lines_agent.models import Market, Outcome
from nba_betting_agent.monitoring import get_logger

log = get_logger()

# ML Model Integration
_ml_estimator = None
_ml_historical_games = None
_ml_enabled = os.getenv("ML_ENABLED", "true").lower() in ("true", "1", "yes")
_ml_model_path = os.getenv("ML_MODEL_PATH", ".models/moneyline")


def _get_ml_estimator():
    """Lazily load the ML probability estimator."""
    global _ml_estimator, _ml_historical_games

    if not _ml_enabled:
        return None

    if _ml_estimator is not None:
        return _ml_estimator

    try:
        from nba_betting_agent.agents.analysis_agent.ml_probability import MLProbabilityEstimator
        from nba_betting_agent.ml.data.historical import load_historical_games

        model_path = Path(_ml_model_path)

        # Check if model exists
        if not (model_path.parent / f"{model_path.name}.lgb").exists():
            log.info("ml_model_not_found_training", path=str(model_path))
            # Train a new model
            _train_ml_model(model_path)

        # Load historical games for feature computation
        if _ml_historical_games is None:
            log.info("ml_loading_historical_games")
            _ml_historical_games = load_historical_games(["2023-24", "2022-23"])
            log.info("ml_historical_games_loaded", count=len(_ml_historical_games))

        # Load the estimator
        _ml_estimator = MLProbabilityEstimator(model_path=str(model_path))
        log.info("ml_estimator_loaded", model_path=str(model_path))

        return _ml_estimator

    except Exception as e:
        log.warning("ml_estimator_load_failed", error=str(e))
        return None


def _train_ml_model(model_path: Path):
    """Train and save a new ML model."""
    from nba_betting_agent.ml.data.historical import load_historical_games
    from nba_betting_agent.ml.training.trainer import ModelTrainer

    log.info("ml_model_training_started")

    # Load historical games
    games = load_historical_games(["2023-24", "2022-23"])
    log.info("ml_training_games_loaded", count=len(games))

    # Train model
    trainer = ModelTrainer(model_dir=str(model_path.parent))
    model = trainer.train_from_games(games)

    # Save model
    trainer.save_model(model, model_path.name)
    log.info("ml_model_trained_and_saved", path=str(model_path))


@dataclass
class BettingOpportunity:
    """Structured betting opportunity with EV analysis.

    Attributes:
        game_id: Unique game identifier
        matchup: Game matchup string (e.g., "BOS vs LAL")
        market: Market type (h2h, spreads, totals)
        outcome: Outcome name (team name or over/under)
        bookmaker: Sportsbook offering this line
        our_prob: Our estimated probability (calibrated if available)
        market_odds: Market odds in decimal format
        fair_odds: Fair odds after vig removal
        ev_pct: Expected value percentage
        kelly_bet_pct: Kelly criterion bet percentage
        confidence: Confidence level (low/medium/high)
        sharp_edge: Edge vs sharp book if available
        rlm_signal: Reverse line movement if detected
        llm_insight: Key insight from LLM if run
        ml_prob: ML model probability (if ML enabled)
        ml_explanation: ML model explanation (key factors)
    """

    game_id: str
    matchup: str
    market: str
    outcome: str
    bookmaker: str
    our_prob: float
    market_odds: float
    fair_odds: float
    ev_pct: float
    kelly_bet_pct: float
    confidence: str
    sharp_edge: Optional[float] = None
    rlm_signal: Optional[str] = None
    llm_insight: Optional[str] = None
    ml_prob: Optional[float] = None
    ml_explanation: Optional[str] = None


@dataclass
class AnalysisResult:
    """Complete analysis result for state contract.

    Attributes:
        opportunities: List of +EV betting opportunities
        estimated_probabilities: Dict for state (game_id -> outcome -> probability)
        expected_values: List of EV dicts for state
        analysis_notes: Human-readable analysis notes
        errors: Any errors encountered
    """

    opportunities: list[BettingOpportunity]
    estimated_probabilities: dict
    expected_values: list[dict]
    analysis_notes: list[str]
    errors: list[str]


def parse_record_pct(record: str) -> float:
    """Parse '7-3' format to win percentage.

    Args:
        record: Record string like "7-3"

    Returns:
        Win percentage (0.0 to 1.0), or 0.5 if parse fails
    """
    try:
        w, l = record.split("-")
        total = int(w) + int(l)
        return int(w) / total if total > 0 else 0.5
    except Exception:
        return 0.5


def assess_confidence(has_stats: bool, has_injuries: bool, has_sharp: bool) -> str:
    """Assess confidence level based on data completeness.

    Args:
        has_stats: Whether we have team stats
        has_injuries: Whether we have injury data
        has_sharp: Whether we have sharp book odds

    Returns:
        Confidence level: "high", "medium", or "low"
    """
    score = sum([has_stats, has_injuries, has_sharp])
    if score >= 3:
        return "high"
    elif score >= 2:
        return "medium"
    return "low"


def generate_base_probability(
    home_stats: dict, away_stats: dict, fair_prob: float
) -> float:
    """Generate probability estimate from stats + market (fallback when ML unavailable).

    For MVP: Start with market fair odds as baseline (markets are efficient).
    Adjust slightly based on recent form and home court advantage.

    Args:
        home_stats: Home team stats dict
        away_stats: Away team stats dict
        fair_prob: Fair probability from market odds

    Returns:
        Adjusted probability (0.05 to 0.95)
    """
    prob = fair_prob  # Market baseline

    # Small adjustments based on available data
    if home_stats and away_stats:
        # Home court advantage adjustment (+2-3%)
        prob += 0.025

        # Recent form adjustment (last 10 games)
        home_l10 = home_stats.get("last_10", {})
        away_l10 = away_stats.get("last_10", {})
        if home_l10 and away_l10:
            # Parse records like "7-3" -> 0.7
            home_pct = parse_record_pct(home_l10.get("record", "5-5"))
            away_pct = parse_record_pct(away_l10.get("record", "5-5"))
            form_diff = (home_pct - away_pct) * 0.05  # Small form adjustment
            prob += form_diff

        # Net rating difference adjustment
        home_advanced = home_stats.get("advanced", {})
        away_advanced = away_stats.get("advanced", {})
        home_net = home_advanced.get("net_rtg", 0)
        away_net = away_advanced.get("net_rtg", 0)
        if home_net and away_net:
            net_diff = (home_net - away_net) / 100  # Scale down
            prob += net_diff * 0.02

    # Clamp to valid probability range
    return max(0.05, min(0.95, prob))


def generate_ml_probability(
    home_team: str,
    away_team: str,
    fair_prob: float,
) -> tuple[float, Optional[str]]:
    """Generate probability estimate using ML model.

    Uses trained LightGBM model with 22 features (team stats, situational).
    Falls back to market-based estimate if ML unavailable.

    Args:
        home_team: Home team abbreviation
        away_team: Away team abbreviation
        fair_prob: Fair probability from market odds (for blending)

    Returns:
        Tuple of (probability, explanation or None)
    """
    global _ml_historical_games

    estimator = _get_ml_estimator()

    if estimator is None or _ml_historical_games is None:
        # ML not available, return fair prob with no explanation
        return fair_prob, None

    try:
        # Use today's date for prediction
        game_date = date.today()

        # Map team names to abbreviations if needed
        home_abbr = _normalize_team_abbr(home_team)
        away_abbr = _normalize_team_abbr(away_team)

        # Get ML prediction
        result = estimator.estimate_probability(
            home_team=home_abbr,
            away_team=away_abbr,
            game_date=game_date,
            historical_games=_ml_historical_games,
            market_prob=fair_prob,
        )

        # Return blended probability and explanation
        return result["blended_prob"], result["explanation"]

    except Exception as e:
        log.warning("ml_probability_failed", error=str(e), home=home_team, away=away_team)
        return fair_prob, None


def _normalize_team_abbr(team_name: str) -> str:
    """Normalize team name to 3-letter abbreviation."""
    # Common mappings
    TEAM_MAP = {
        "boston celtics": "BOS", "celtics": "BOS",
        "miami heat": "MIA", "heat": "MIA",
        "new york knicks": "NYK", "knicks": "NYK",
        "philadelphia 76ers": "PHI", "76ers": "PHI",
        "brooklyn nets": "BKN", "nets": "BKN",
        "milwaukee bucks": "MIL", "bucks": "MIL",
        "cleveland cavaliers": "CLE", "cavaliers": "CLE", "cavs": "CLE",
        "chicago bulls": "CHI", "bulls": "CHI",
        "indiana pacers": "IND", "pacers": "IND",
        "detroit pistons": "DET", "pistons": "DET",
        "atlanta hawks": "ATL", "hawks": "ATL",
        "orlando magic": "ORL", "magic": "ORL",
        "washington wizards": "WAS", "wizards": "WAS",
        "charlotte hornets": "CHA", "hornets": "CHA",
        "toronto raptors": "TOR", "raptors": "TOR",
        "denver nuggets": "DEN", "nuggets": "DEN",
        "minnesota timberwolves": "MIN", "timberwolves": "MIN", "wolves": "MIN",
        "oklahoma city thunder": "OKC", "thunder": "OKC",
        "portland trail blazers": "POR", "trail blazers": "POR", "blazers": "POR",
        "utah jazz": "UTA", "jazz": "UTA",
        "los angeles lakers": "LAL", "lakers": "LAL",
        "los angeles clippers": "LAC", "clippers": "LAC",
        "phoenix suns": "PHX", "suns": "PHX",
        "sacramento kings": "SAC", "kings": "SAC",
        "golden state warriors": "GSW", "warriors": "GSW",
        "memphis grizzlies": "MEM", "grizzlies": "MEM",
        "new orleans pelicans": "NOP", "pelicans": "NOP",
        "dallas mavericks": "DAL", "mavericks": "DAL", "mavs": "DAL",
        "houston rockets": "HOU", "rockets": "HOU",
        "san antonio spurs": "SAS", "spurs": "SAS",
    }

    name_lower = team_name.lower().strip()

    # Direct lookup
    if name_lower in TEAM_MAP:
        return TEAM_MAP[name_lower]

    # Already an abbreviation?
    if len(team_name) <= 3 and team_name.upper() in [v for v in TEAM_MAP.values()]:
        return team_name.upper()

    # Partial match
    for key, abbr in TEAM_MAP.items():
        if key in name_lower or name_lower in key:
            return abbr

    # Fallback: first 3 chars
    return team_name[:3].upper()


async def analyze_bets(
    odds_data: list,
    team_stats: dict,
    injuries: list,
    calibrator: Optional[ProbabilityCalibrator] = None,
    min_ev_pct: float = 2.0,
    use_llm: bool = False,
) -> AnalysisResult:
    """Main analysis function integrating all Phase 4 modules.

    Args:
        odds_data: List of game odds from Lines Agent
        team_stats: Dict of team stats from Stats Agent
        injuries: List of injury reports from Stats Agent
        calibrator: Optional probability calibrator
        min_ev_pct: Minimum EV percentage to qualify (default 2.0%)
        use_llm: Whether to use LLM analysis (default False)

    Returns:
        AnalysisResult with opportunities and state-compatible outputs
    """
    start_time = time.perf_counter()

    opportunities: list[BettingOpportunity] = []
    estimated_probabilities: dict = {}
    expected_values: list[dict] = []
    analysis_notes: list[str] = []
    errors: list[str] = []

    # Validate inputs
    if not odds_data:
        errors.append("Analysis Agent: no odds data provided")
        log.warning("analysis_agent_no_odds_data")
        return AnalysisResult(
            opportunities=[],
            estimated_probabilities={},
            expected_values=[],
            analysis_notes=[],
            errors=errors,
        )

    log.info(
        "analysis_agent_started",
        game_count=len(odds_data),
        has_team_stats=bool(team_stats),
        has_injuries=bool(injuries),
        min_ev_pct=min_ev_pct,
    )

    # Process each game
    for game in odds_data:
        try:
            game_id = game.get("id", "unknown")
            home_team = game.get("home_team", "")
            away_team = game.get("away_team", "")
            matchup = f"{away_team} @ {home_team}"

            # Initialize game probabilities dict
            if game_id not in estimated_probabilities:
                estimated_probabilities[game_id] = {}

            # Get team stats for this game
            home_abbr = _find_team_abbr(home_team, team_stats)
            away_abbr = _find_team_abbr(away_team, team_stats)
            home_stats = team_stats.get(home_abbr, {})
            away_stats = team_stats.get(away_abbr, {})

            # Check data availability
            has_stats = bool(home_stats and away_stats)
            has_injuries = bool(injuries)
            has_sharp = False

            # Process each bookmaker
            bookmakers = game.get("bookmakers", [])
            for bookmaker in bookmakers:
                bookmaker_key = bookmaker.get("key", "")

                # Check if this is a sharp book
                if bookmaker_key in SHARP_BOOKS:
                    has_sharp = True

                # Process each market
                markets = bookmaker.get("markets", [])
                for market_data in markets:
                    market_key = market_data.get("key", "")
                    outcomes = market_data.get("outcomes", [])

                    if len(outcomes) < 2:
                        continue

                    # Create Market object for analysis
                    market = Market(
                        key=market_key,
                        outcomes=[
                            Outcome(
                                name=o.get("name", ""),
                                price=o.get("price", 1.0),
                                point=o.get("point"),
                            )
                            for o in outcomes
                        ],
                    )

                    # Calculate fair odds for this market
                    try:
                        fair_odds_analysis = calculate_fair_odds(market)
                    except Exception as e:
                        errors.append(
                            f"Fair odds calculation failed for {game_id} {market_key}: {e}"
                        )
                        continue

                    # Analyze each outcome
                    for outcome_name, outcome_analysis in fair_odds_analysis.items():
                        # Generate base probability
                        fair_prob = outcome_analysis["fair_prob"]
                        ml_explanation = None
                        ml_prob = None

                        # For h2h markets, use ML model if available
                        if market_key == "h2h":
                            # Determine if this is home or away team
                            is_home = outcome_name == home_team

                            if is_home:
                                # Try ML probability first
                                ml_prob, ml_explanation = generate_ml_probability(
                                    home_team, away_team, fair_prob
                                )
                                our_prob = ml_prob if ml_prob else generate_base_probability(
                                    home_stats, away_stats, fair_prob
                                )
                            else:
                                # Away team - flip the logic
                                away_fair_prob = fair_prob
                                home_prob, ml_explanation = generate_ml_probability(
                                    home_team, away_team, 1.0 - away_fair_prob
                                )
                                our_prob = 1.0 - home_prob if home_prob else 1.0 - generate_base_probability(
                                    home_stats, away_stats, 1.0 - away_fair_prob
                                )
                                ml_prob = 1.0 - home_prob if home_prob else None
                        else:
                            # For spreads/totals, use fair prob as baseline
                            our_prob = fair_prob

                        # Apply calibration if available (skip if ML already calibrated)
                        if ml_prob is None:
                            our_prob = calibrate_probability(our_prob, calibrator)

                        # Store probability estimate
                        if outcome_name not in estimated_probabilities[game_id]:
                            estimated_probabilities[game_id][outcome_name] = our_prob

                        # Calculate EV
                        ev_result = calculate_ev(
                            our_prob, outcome_analysis["market_odds"]
                        )

                        # Check if meets minimum EV threshold
                        if ev_result["ev_percentage"] >= min_ev_pct:
                            # Calculate Kelly bet sizing
                            kelly_result = calculate_kelly_bet(
                                our_prob,
                                outcome_analysis["market_odds"],
                                bankroll=1000.0,  # Placeholder
                                kelly_fraction=0.25,
                            )

                            # Assess confidence (higher if ML model used)
                            has_ml = ml_prob is not None
                            confidence = assess_confidence(
                                has_stats or has_ml, has_injuries, has_sharp or has_ml
                            )

                            # Create opportunity
                            opportunity = BettingOpportunity(
                                game_id=game_id,
                                matchup=matchup,
                                market=market_key,
                                outcome=outcome_name,
                                bookmaker=bookmaker_key,
                                our_prob=our_prob,
                                market_odds=outcome_analysis["market_odds"],
                                fair_odds=outcome_analysis["fair_odds"],
                                ev_pct=ev_result["ev_percentage"],
                                kelly_bet_pct=kelly_result["fractional_pct"],
                                confidence=confidence,
                                ml_prob=ml_prob,
                                ml_explanation=ml_explanation,
                            )

                            opportunities.append(opportunity)

                            # Add to expected_values for state
                            expected_values.append(
                                {
                                    "game_id": game_id,
                                    "matchup": matchup,
                                    "market": market_key,
                                    "outcome": outcome_name,
                                    "bookmaker": bookmaker_key,
                                    "our_prob": round(our_prob, 3),
                                    "market_odds": outcome_analysis["market_odds"],
                                    "ev_pct": round(ev_result["ev_percentage"], 2),
                                    "confidence": confidence,
                                    "ml_prob": round(ml_prob, 3) if ml_prob else None,
                                    "ml_explanation": ml_explanation,
                                }
                            )

            # Check for sharp book edges (if sharp book available)
            if has_sharp:
                try:
                    # Convert to GameOdds format for sharp comparison
                    from nba_betting_agent.agents.lines_agent.models import (
                        GameOdds,
                        BookmakerOdds,
                    )
                    from datetime import datetime

                    game_odds = GameOdds(
                        id=game_id,
                        sport_key=game.get("sport_key", "basketball_nba"),
                        commence_time=datetime.fromisoformat(
                            game.get("commence_time", "2026-01-01T00:00:00Z")
                        ),
                        home_team=home_team,
                        away_team=away_team,
                        bookmakers=[
                            BookmakerOdds(
                                key=bm.get("key", ""),
                                title=bm.get("title", ""),
                                markets=[
                                    Market(
                                        key=m.get("key", ""),
                                        outcomes=[
                                            Outcome(
                                                name=o.get("name", ""),
                                                price=o.get("price", 1.0),
                                                point=o.get("point"),
                                            )
                                            for o in m.get("outcomes", [])
                                        ],
                                    )
                                    for m in bm.get("markets", [])
                                ],
                                last_update=datetime.now(),
                            )
                            for bm in bookmakers
                        ],
                    )

                    edges = find_soft_book_edges(game_odds, market_key="h2h")
                    if edges:
                        analysis_notes.append(
                            f"Found {len(edges)} sharp/soft edges for {matchup}"
                        )
                        # Add edge info to matching opportunities
                        for edge in edges:
                            for opp in opportunities:
                                if (
                                    opp.game_id == game_id
                                    and opp.outcome == edge.outcome_name
                                    and opp.bookmaker == edge.soft_book
                                ):
                                    opp.sharp_edge = edge.edge_pct

                except Exception as e:
                    errors.append(f"Sharp comparison failed for {game_id}: {e}")

        except Exception as e:
            errors.append(f"Game analysis failed for {game.get('id', 'unknown')}: {e}")
            continue

    # Sort opportunities by EV descending
    opportunities.sort(key=lambda x: x.ev_pct, reverse=True)

    # Check if ML was used
    ml_used = any(opp.ml_prob is not None for opp in opportunities)

    # Add summary notes
    if opportunities:
        analysis_notes.insert(
            0, f"Found {len(opportunities)} +EV opportunities (min EV: {min_ev_pct}%)"
        )
        if ml_used:
            ml_count = sum(1 for opp in opportunities if opp.ml_prob is not None)
            analysis_notes.insert(1, f"ML model used for {ml_count} predictions (22 features, LightGBM)")
    else:
        analysis_notes.append(
            f"No +EV opportunities found (min EV threshold: {min_ev_pct}%)"
        )

    duration_ms = int((time.perf_counter() - start_time) * 1000)
    log.info(
        "analysis_agent_completed",
        opportunities_found=len(opportunities),
        games_analyzed=len(odds_data),
        duration_ms=duration_ms,
    )

    return AnalysisResult(
        opportunities=opportunities,
        estimated_probabilities=estimated_probabilities,
        expected_values=expected_values,
        analysis_notes=analysis_notes,
        errors=errors,
    )


def _find_team_abbr(team_name: str, team_stats: dict) -> str:
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
            name = stats.get("name", "").lower()
        else:
            name = getattr(stats, "name", "").lower()

        if team_lower in name or name in team_lower:
            return abbr

    # Fallback to first 3 chars uppercase
    return team_name[:3].upper()


def analysis_agent_impl(state: dict) -> dict:
    """Sync wrapper for Analysis Agent - called by LangGraph node.

    Args:
        state: BettingAnalysisState dict with odds_data, team_stats, injuries

    Returns:
        Partial state update with estimated_probabilities and expected_values
    """
    odds_data = state.get("odds_data", [])
    team_stats = state.get("team_stats", {})
    injuries = state.get("injuries", [])

    # Get min_ev from filter_params (set by CLI --min-ev flag)
    # Default to -100 to show ALL opportunities - let communication_agent filter
    filter_params = state.get("filter_params", {})
    min_ev_pct = filter_params.get("min_ev", -100) * 100 if filter_params.get("min_ev") is not None else -100

    # Run async analysis in thread pool (same pattern as Lines/Stats agents)
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(
            asyncio.run, analyze_bets(odds_data, team_stats, injuries, min_ev_pct=min_ev_pct)
        )
        result = future.result(timeout=60)

    return {
        "estimated_probabilities": result.estimated_probabilities,
        "expected_values": result.expected_values,
        "opportunities": result.opportunities,  # NEW: typed objects for formatters
        "errors": result.errors,
    }
