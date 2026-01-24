"""Reverse line movement (RLM) detection for identifying sharp money.

Reverse line movement occurs when betting lines move in the opposite direction
of public betting percentages. This indicates "sharp money" (professional bettors)
taking the other side, forcing bookmakers to adjust despite the public trend.

Example:
    72% of bets on the home team, but home odds INCREASE (get worse for bettors).
    This suggests sharps are betting the away team, and the book is protecting itself.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class RLMStrength(Enum):
    """Strength classification for RLM signals."""

    NONE = "none"
    WEAK = "weak"  # Small line movement against borderline public majority
    MODERATE = "moderate"  # Clear movement against majority OR heavy majority with small move
    STRONG = "strong"  # Significant movement against heavy public betting


@dataclass
class RLMSignal:
    """Reverse line movement signal with strength classification.

    Attributes:
        detected: True if RLM detected
        side: Which side has sharp money ("home", "away", or None)
        public_pct: Percentage of bets on the popular side
        line_movement_pct: How much the line moved against public (positive = moved against)
        strength: Classification of signal strength
        interpretation: Human-readable explanation
    """

    detected: bool
    side: Optional[str]
    public_pct: float
    line_movement_pct: float
    strength: RLMStrength
    interpretation: str


def detect_rlm(
    opening_odds: list[float],
    current_odds: list[float],
    public_bet_pcts: list[float],
    side_names: list[str] = None,
    public_threshold: float = 0.60,
) -> RLMSignal:
    """Detect reverse line movement in betting lines.

    Args:
        opening_odds: Opening decimal odds [home, away]
        current_odds: Current decimal odds [home, away]
        public_bet_pcts: Percentage of bets [home_pct, away_pct] (should sum to ~1.0)
        side_names: Names for sides (default ["home", "away"])
        public_threshold: Minimum percentage to consider "public side" (default 0.60)

    Returns:
        RLMSignal with detection results and interpretation

    Example:
        >>> signal = detect_rlm(
        ...     opening_odds=[1.90, 2.00],
        ...     current_odds=[1.95, 1.95],  # Home odds increased
        ...     public_bet_pcts=[0.72, 0.28]  # 72% on home
        ... )
        >>> signal.detected  # True - line moved against public
        True
        >>> signal.side  # Sharp money on away
        'away'
    """
    if side_names is None:
        side_names = ["home", "away"]

    # Validate inputs
    if len(opening_odds) != 2 or len(current_odds) != 2 or len(public_bet_pcts) != 2:
        return RLMSignal(
            detected=False,
            side=None,
            public_pct=0.0,
            line_movement_pct=0.0,
            strength=RLMStrength.NONE,
            interpretation="Invalid input: Need exactly 2 sides for RLM detection",
        )

    # Check if betting percentages are valid
    if sum(public_bet_pcts) < 0.95 or sum(public_bet_pcts) > 1.05:
        return RLMSignal(
            detected=False,
            side=None,
            public_pct=0.0,
            line_movement_pct=0.0,
            strength=RLMStrength.NONE,
            interpretation="Invalid betting percentages: Must sum to ~1.0",
        )

    # Find which side has public majority
    public_side_idx = 0 if public_bet_pcts[0] > public_bet_pcts[1] else 1
    public_side_pct = public_bet_pcts[public_side_idx]

    # Check if there's a clear public majority
    if public_side_pct < public_threshold:
        return RLMSignal(
            detected=False,
            side=None,
            public_pct=max(public_bet_pcts),
            line_movement_pct=0.0,
            strength=RLMStrength.NONE,
            interpretation=f"No clear public majority (max {max(public_bet_pcts)*100:.1f}%, need {public_threshold*100:.0f}%)",
        )

    # Calculate line movement for public side
    opening_public = opening_odds[public_side_idx]
    current_public = current_odds[public_side_idx]
    line_movement_pct = ((current_public - opening_public) / opening_public) * 100

    # RLM detected if public side odds INCREASED (worse for bettors)
    # Higher odds = worse value = book moving against public
    if line_movement_pct <= 0:
        # Line moved with public or didn't move
        return RLMSignal(
            detected=False,
            side=None,
            public_pct=public_side_pct,
            line_movement_pct=line_movement_pct,
            strength=RLMStrength.NONE,
            interpretation=f"No RLM: Line moved WITH public or unchanged (public {public_side_pct*100:.1f}%, line {line_movement_pct:+.2f}%)",
        )

    # RLM detected! Determine strength
    strength = _classify_rlm_strength(public_side_pct, abs(line_movement_pct))

    # Sharp side is opposite of public side
    sharp_side_idx = 1 - public_side_idx
    sharp_side_name = side_names[sharp_side_idx]
    public_side_name = side_names[public_side_idx]

    interpretation = (
        f"Sharp money detected on {sharp_side_name}. "
        f"{public_side_pct*100:.1f}% of bets on {public_side_name}, "
        f"but {public_side_name} odds increased {line_movement_pct:.2f}% "
        f"(from {opening_public:.3f} to {current_public:.3f}). "
        f"Strength: {strength.value.upper()}"
    )

    return RLMSignal(
        detected=True,
        side=sharp_side_name,
        public_pct=public_side_pct,
        line_movement_pct=line_movement_pct,
        strength=strength,
        interpretation=interpretation,
    )


def _classify_rlm_strength(public_pct: float, line_move_pct: float) -> RLMStrength:
    """Classify RLM signal strength based on public % and line movement.

    Args:
        public_pct: Percentage of bets on public side (0.60 - 1.0)
        line_move_pct: Absolute percentage line moved

    Returns:
        RLMStrength classification

    Classification logic:
        - WEAK: public 60-70% AND line moved 1-3%
        - MODERATE: (public 60-70% AND line moved >3%) OR (public >70% AND line moved 1-3%)
        - STRONG: public >70% AND line moved >3%
    """
    heavy_public = public_pct > 0.70
    significant_move = line_move_pct > 3.0

    if heavy_public and significant_move:
        return RLMStrength.STRONG
    elif heavy_public or significant_move:
        return RLMStrength.MODERATE
    else:
        return RLMStrength.WEAK


def interpret_rlm(signal: RLMSignal) -> str:
    """Generate human-readable interpretation of RLM signal.

    Args:
        signal: RLMSignal to interpret

    Returns:
        Human-readable description

    Example:
        >>> signal = detect_rlm([1.90, 2.00], [1.95, 1.95], [0.72, 0.28])
        >>> interpret_rlm(signal)
        'Sharp money detected on away. 72.0% of bets on home, but home odds increased 2.63%...'
    """
    return signal.interpretation
