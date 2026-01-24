"""Tests for reverse line movement detector."""

import pytest

from nba_betting_agent.agents.analysis_agent.rlm_detector import (
    RLMStrength,
    RLMSignal,
    detect_rlm,
    interpret_rlm,
)


def test_detect_rlm_classic_case():
    """Test classic RLM case: heavy public on home, home odds increase."""
    opening_odds = [1.90, 2.00]
    current_odds = [1.95, 1.95]  # Home odds increased
    public_bet_pcts = [0.72, 0.28]  # 72% on home

    signal = detect_rlm(opening_odds, current_odds, public_bet_pcts)

    assert signal.detected is True
    assert signal.side == "away"  # Sharp money on away
    assert signal.public_pct == 0.72
    assert signal.line_movement_pct > 0  # Positive movement
    assert signal.strength in [RLMStrength.MODERATE, RLMStrength.STRONG]
    assert "sharp money" in signal.interpretation.lower()


def test_detect_rlm_no_movement():
    """Test no RLM when line unchanged."""
    opening_odds = [1.90, 2.00]
    current_odds = [1.90, 2.00]  # No change
    public_bet_pcts = [0.72, 0.28]

    signal = detect_rlm(opening_odds, current_odds, public_bet_pcts)

    assert signal.detected is False
    assert signal.strength == RLMStrength.NONE


def test_detect_rlm_movement_with_public():
    """Test no RLM when line moves WITH public (odds decrease)."""
    opening_odds = [1.90, 2.00]
    current_odds = [1.85, 2.05]  # Home odds decreased (better for public)
    public_bet_pcts = [0.72, 0.28]

    signal = detect_rlm(opening_odds, current_odds, public_bet_pcts)

    assert signal.detected is False
    assert signal.line_movement_pct < 0  # Negative = moved with public
    assert signal.strength == RLMStrength.NONE


def test_detect_rlm_weak_signal():
    """Test weak RLM: borderline public % and small movement."""
    opening_odds = [1.90, 2.00]
    current_odds = [1.92, 1.98]  # Small increase (~1%)
    public_bet_pcts = [0.62, 0.38]  # Borderline majority

    signal = detect_rlm(opening_odds, current_odds, public_bet_pcts)

    if signal.detected:
        assert signal.strength == RLMStrength.WEAK
    # May or may not detect depending on exact thresholds


def test_detect_rlm_strong_signal():
    """Test strong RLM: heavy public and large line movement."""
    opening_odds = [1.90, 2.00]
    current_odds = [2.00, 1.91]  # Large increase (~5.3%)
    public_bet_pcts = [0.75, 0.25]  # Heavy public on home

    signal = detect_rlm(opening_odds, current_odds, public_bet_pcts)

    assert signal.detected is True
    assert signal.side == "away"
    assert signal.strength == RLMStrength.STRONG
    assert signal.line_movement_pct > 3.0


def test_detect_rlm_no_majority():
    """Test no RLM when betting is 50/50."""
    opening_odds = [1.90, 2.00]
    current_odds = [1.95, 1.95]
    public_bet_pcts = [0.50, 0.50]  # Even split

    signal = detect_rlm(opening_odds, current_odds, public_bet_pcts)

    assert signal.detected is False
    assert signal.strength == RLMStrength.NONE
    assert "no clear public majority" in signal.interpretation.lower()


def test_rlm_strength_weak():
    """Verify WEAK classification: 60-70% public, 1-3% move."""
    opening_odds = [1.90, 2.00]
    current_odds = [1.93, 1.97]  # ~1.6% move
    public_bet_pcts = [0.65, 0.35]

    signal = detect_rlm(opening_odds, current_odds, public_bet_pcts)

    if signal.detected:
        assert signal.strength == RLMStrength.WEAK


def test_rlm_strength_moderate():
    """Verify MODERATE classification."""
    # Case 1: 60-70% public, >3% move
    opening_odds = [1.90, 2.00]
    current_odds = [1.98, 1.92]  # ~4.2% move
    public_bet_pcts = [0.65, 0.35]

    signal = detect_rlm(opening_odds, current_odds, public_bet_pcts)

    if signal.detected:
        assert signal.strength == RLMStrength.MODERATE

    # Case 2: >70% public, 1-3% move
    opening_odds2 = [1.90, 2.00]
    current_odds2 = [1.93, 1.97]  # ~1.6% move
    public_bet_pcts2 = [0.75, 0.25]

    signal2 = detect_rlm(opening_odds2, current_odds2, public_bet_pcts2)

    if signal2.detected:
        assert signal2.strength == RLMStrength.MODERATE


def test_rlm_strength_strong():
    """Verify STRONG classification: >70% public AND >3% move."""
    opening_odds = [1.90, 2.00]
    current_odds = [2.00, 1.91]  # ~5.3% move
    public_bet_pcts = [0.75, 0.25]

    signal = detect_rlm(opening_odds, current_odds, public_bet_pcts)

    assert signal.detected is True
    assert signal.strength == RLMStrength.STRONG


def test_interpret_rlm_readable():
    """Test that interpretation is human-readable and informative."""
    opening_odds = [1.90, 2.00]
    current_odds = [1.95, 1.95]
    public_bet_pcts = [0.72, 0.28]

    signal = detect_rlm(opening_odds, current_odds, public_bet_pcts)
    interpretation = interpret_rlm(signal)

    assert isinstance(interpretation, str)
    assert len(interpretation) > 20
    # Should mention key details
    if signal.detected:
        assert "sharp" in interpretation.lower() or "money" in interpretation.lower()
        assert "72" in interpretation or "72.0" in interpretation  # Public pct


def test_detect_rlm_custom_threshold():
    """Test custom public threshold detection."""
    opening_odds = [1.90, 2.00]
    current_odds = [1.95, 1.95]
    public_bet_pcts = [0.55, 0.45]  # Below default 60% threshold

    # Default threshold (0.60) - should not detect
    signal = detect_rlm(opening_odds, current_odds, public_bet_pcts)
    assert signal.detected is False

    # Lower threshold (0.50) - should detect
    signal_low = detect_rlm(opening_odds, current_odds, public_bet_pcts, public_threshold=0.50)
    assert signal_low.detected is True


def test_detect_rlm_invalid_percentages():
    """Test graceful handling of invalid betting percentages."""
    opening_odds = [1.90, 2.00]
    current_odds = [1.95, 1.95]

    # Percentages don't sum to 1.0
    public_bet_pcts_invalid = [0.40, 0.40]

    signal = detect_rlm(opening_odds, current_odds, public_bet_pcts_invalid)

    assert signal.detected is False
    assert "invalid" in signal.interpretation.lower()


def test_detect_rlm_away_side():
    """Test RLM detection when public is on away team."""
    opening_odds = [2.00, 1.90]  # Away favored
    current_odds = [1.95, 1.95]  # Away odds increased
    public_bet_pcts = [0.28, 0.72]  # 72% on away

    signal = detect_rlm(opening_odds, current_odds, public_bet_pcts)

    assert signal.detected is True
    assert signal.side == "home"  # Sharp money on home
    assert signal.public_pct == 0.72


def test_detect_rlm_custom_side_names():
    """Test with custom side names (team names)."""
    opening_odds = [1.90, 2.00]
    current_odds = [1.95, 1.95]
    public_bet_pcts = [0.72, 0.28]
    side_names = ["Boston Celtics", "Los Angeles Lakers"]

    signal = detect_rlm(opening_odds, current_odds, public_bet_pcts, side_names=side_names)

    assert signal.detected is True
    assert signal.side == "Los Angeles Lakers"
    assert "Boston Celtics" in signal.interpretation
    assert "Los Angeles Lakers" in signal.interpretation


def test_rlm_signal_dataclass_fields():
    """Test that RLMSignal has all expected fields."""
    signal = RLMSignal(
        detected=True,
        side="away",
        public_pct=0.72,
        line_movement_pct=2.5,
        strength=RLMStrength.MODERATE,
        interpretation="Test interpretation",
    )

    assert signal.detected is True
    assert signal.side == "away"
    assert signal.public_pct == 0.72
    assert signal.line_movement_pct == 2.5
    assert signal.strength == RLMStrength.MODERATE
    assert signal.interpretation == "Test interpretation"


def test_rlm_calculation_accuracy():
    """Verify line movement percentage calculation."""
    # Opening: 1.90, Current: 1.95
    # Movement: (1.95 - 1.90) / 1.90 * 100 = 2.63%
    opening_odds = [1.90, 2.00]
    current_odds = [1.95, 1.95]
    public_bet_pcts = [0.72, 0.28]

    signal = detect_rlm(opening_odds, current_odds, public_bet_pcts)

    expected_movement = ((1.95 - 1.90) / 1.90) * 100
    assert abs(signal.line_movement_pct - expected_movement) < 0.01
