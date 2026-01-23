"""Expected value calculation and Kelly criterion bet sizing.

Provides the core mathematical tools for identifying and sizing +EV betting opportunities:
1. EV calculation comparing our probability vs market odds
2. Kelly criterion with fractional sizing for conservative position sizing
3. Opportunity evaluation integrating vig removal for complete analysis

Formula Reference:
    EV = (prob_win × amount_won) - (prob_lose × amount_lost)
    Kelly = (b×p - q) / b where b=odds-1, p=probability, q=1-p
"""

from typing import Any

from nba_betting_agent.agents.analysis_agent.vig_removal import (
    calculate_fair_odds,
)
from nba_betting_agent.agents.lines_agent.models import Market


def calculate_ev(
    our_prob: float, market_decimal_odds: float, bet_amount: float = 100.0
) -> dict[str, Any]:
    """Calculate expected value for a betting opportunity.

    Compares our probability estimate against market odds to determine
    expected profit or loss per bet.

    Args:
        our_prob: Our estimated probability of winning (0.0 to 1.0)
        market_decimal_odds: Market odds in decimal format (e.g., 2.0 for even money)
        bet_amount: Amount to bet in dollars (default 100)

    Returns:
        Dictionary with:
            - ev_dollars: Expected value in dollars
            - ev_percentage: EV as percentage of bet amount
            - is_positive: Whether this is a +EV opportunity
            - our_prob: Echo of input probability
            - market_odds: Echo of input odds
            - implied_prob: Market's implied probability

    Raises:
        ValueError: If our_prob is not in (0, 1) exclusive
        ValueError: If market_decimal_odds < 1.0

    Example:
        >>> # We think team has 55% chance, market offers 2.0 odds (50% implied)
        >>> result = calculate_ev(0.55, 2.0, 100)
        >>> result['ev_percentage']
        10.0  # 10% expected value
        >>> result['is_positive']
        True
    """
    # Validate probability
    if our_prob <= 0.0 or our_prob >= 1.0:
        raise ValueError(
            f"Probability must be between 0 and 1 exclusive. Got {our_prob}."
        )

    # Validate odds
    if market_decimal_odds < 1.0:
        raise ValueError(
            f"Decimal odds must be >= 1.0. Got {market_decimal_odds}. "
            "Odds represent total payout including stake."
        )

    # Calculate win and loss amounts
    # Win amount: profit on winning bet (odds - 1) × stake
    amount_won = (market_decimal_odds - 1.0) * bet_amount
    # Loss amount: entire stake
    amount_lost = bet_amount

    # Calculate EV
    prob_win = our_prob
    prob_lose = 1.0 - our_prob

    ev_dollars = (prob_win * amount_won) - (prob_lose * amount_lost)
    ev_percentage = (ev_dollars / bet_amount) * 100.0

    # Calculate market's implied probability
    implied_prob = 1.0 / market_decimal_odds

    return {
        "ev_dollars": ev_dollars,
        "ev_percentage": ev_percentage,
        "is_positive": ev_dollars > 0,
        "our_prob": our_prob,
        "market_odds": market_decimal_odds,
        "implied_prob": implied_prob,
    }


def calculate_kelly_bet(
    prob: float, odds: float, bankroll: float, kelly_fraction: float = 0.25
) -> dict[str, Any]:
    """Calculate optimal bet size using Kelly Criterion with fractional sizing.

    Kelly Criterion maximizes long-term growth but is aggressive. Fractional Kelly
    (default 25%) provides more conservative sizing to account for probability
    estimation errors.

    Args:
        prob: Our estimated probability of winning (0.0 to 1.0)
        odds: Market odds in decimal format
        bankroll: Current bankroll in dollars
        kelly_fraction: Fraction of full Kelly to bet (default 0.25 = 25%)
            - 1.0 = full Kelly (aggressive)
            - 0.5 = half Kelly (moderate)
            - 0.25 = quarter Kelly (conservative, recommended)

    Returns:
        Dictionary with:
            - bet_amount: Recommended bet size in dollars
            - kelly_pct: Full Kelly percentage of bankroll
            - fractional_pct: Actual percentage used (kelly_pct × kelly_fraction)
            - bankroll: Echo of input bankroll

    Raises:
        ValueError: If prob not in (0, 1) exclusive
        ValueError: If odds < 1.0
        ValueError: If kelly_fraction not in (0, 1]

    Example:
        >>> # 55% prob at 2.0 odds with $1000 bankroll, quarter Kelly
        >>> result = calculate_kelly_bet(0.55, 2.0, 1000, 0.25)
        >>> result['bet_amount']
        25.0  # Bet $25 (2.5% of bankroll)
    """
    # Validate probability
    if prob <= 0.0 or prob >= 1.0:
        raise ValueError(
            f"Probability must be between 0 and 1 exclusive. Got {prob}."
        )

    # Validate odds
    if odds < 1.0:
        raise ValueError(f"Decimal odds must be >= 1.0. Got {odds}.")

    # Validate Kelly fraction
    if kelly_fraction <= 0.0 or kelly_fraction > 1.0:
        raise ValueError(
            f"Kelly fraction must be in (0, 1]. Got {kelly_fraction}. "
            "Use 0.25 for conservative, 0.5 for moderate, 1.0 for full Kelly."
        )

    # Kelly formula: f = (b×p - q) / b
    # where b = decimal_odds - 1, p = probability, q = 1 - p
    b = odds - 1.0
    p = prob
    q = 1.0 - p

    kelly_pct = (b * p - q) / b

    # Never bet on negative EV (Kelly would be negative)
    kelly_pct = max(0.0, kelly_pct)

    # Apply fractional Kelly
    fractional_kelly_pct = kelly_pct * kelly_fraction

    # Calculate bet amount
    bet_amount = bankroll * fractional_kelly_pct

    return {
        "bet_amount": bet_amount,
        "kelly_pct": kelly_pct * 100.0,  # Convert to percentage
        "fractional_pct": fractional_kelly_pct * 100.0,
        "bankroll": bankroll,
    }


def evaluate_opportunity(
    our_prob: float,
    market: Market,
    outcome_name: str,
    min_ev_pct: float = 2.0,
) -> dict[str, Any] | None:
    """Evaluate a betting opportunity with vig removal and EV calculation.

    Integrates fair odds calculation (vig removal) with EV analysis to provide
    a complete assessment of whether a betting opportunity meets threshold.

    Args:
        our_prob: Our estimated probability for the outcome
        market: Market model with all outcomes and odds
        outcome_name: Specific outcome to evaluate (e.g., "Lakers", "Over")
        min_ev_pct: Minimum EV percentage to qualify (default 2.0%)

    Returns:
        Dictionary with opportunity details if EV >= min_ev_pct, else None:
            - market_key: Market type (h2h, spreads, totals)
            - outcome_name: Outcome being evaluated
            - our_prob: Our probability estimate
            - market_odds: Raw market odds
            - fair_odds: Vig-removed fair odds
            - fair_prob: Fair probability from market
            - vig_pct: Market vig percentage
            - ev_pct: Expected value percentage
            - is_value_bet: True if EV meets threshold

    Raises:
        ValueError: If outcome_name not found in market
        ValueError: If our_prob invalid

    Example:
        >>> market = Market(
        ...     key="h2h",
        ...     outcomes=[
        ...         Outcome(name="Lakers", price=1.909),
        ...         Outcome(name="Celtics", price=1.909)
        ...     ]
        ... )
        >>> opp = evaluate_opportunity(0.55, market, "Lakers", min_ev_pct=2.0)
        >>> opp['ev_pct']
        5.0  # 5% expected value (above 2% threshold)
    """
    # Calculate fair odds for all outcomes
    fair_odds_analysis = calculate_fair_odds(market)

    # Find the specific outcome
    if outcome_name not in fair_odds_analysis:
        available = list(fair_odds_analysis.keys())
        raise ValueError(
            f"Outcome '{outcome_name}' not found in market. "
            f"Available outcomes: {available}"
        )

    outcome_data = fair_odds_analysis[outcome_name]

    # Calculate EV using market odds
    ev_result = calculate_ev(our_prob, outcome_data["market_odds"])

    # Check if meets minimum EV threshold
    if ev_result["ev_percentage"] < min_ev_pct:
        return None

    # Build opportunity dictionary
    return {
        "market_key": market.key,
        "outcome_name": outcome_name,
        "our_prob": our_prob,
        "market_odds": outcome_data["market_odds"],
        "fair_odds": outcome_data["fair_odds"],
        "fair_prob": outcome_data["fair_prob"],
        "vig_pct": outcome_data["vig_pct"],
        "ev_pct": ev_result["ev_percentage"],
        "is_value_bet": True,
    }
