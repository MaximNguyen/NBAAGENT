"""Ensemble methods for blending ML model probabilities with market odds.

This module implements probability blending strategies that combine the
ML model's estimated probability with market-implied probability.

The default weighting (70% model, 30% market) is based on:
- Markets are efficient but not perfect
- A well-calibrated model can identify edges
- Blending reduces variance and over-confidence

Example:
    >>> from nba_betting_agent.ml.blending import blend_probabilities, ProbabilityBlender
    >>>
    >>> # Simple blending
    >>> blended = blend_probabilities(model_prob=0.65, market_prob=0.60)
    >>> print(f"Blended: {blended:.1%}")  # 63.5%
    >>>
    >>> # Full-featured blending with confidence adjustment
    >>> blender = ProbabilityBlender(model_weight=0.7)
    >>> blended, effective_weight = blender.blend(0.65, 0.60, confidence_width=0.15)
    >>> print(blender.explain_blend(0.65, 0.60, blended))
"""

import os


def blend_probabilities(
    model_prob: float,
    market_prob: float,
    model_weight: float = 0.7,
) -> float:
    """Blend model probability with market-implied probability.

    Uses a simple weighted average to combine probabilities.
    Default weight is 70% model, 30% market.

    Args:
        model_prob: ML model's estimated probability (0-1)
        market_prob: Market-implied probability from odds (0-1)
        model_weight: Weight for model probability (0-1), market gets (1 - model_weight)

    Returns:
        Blended probability, clamped to [0.01, 0.99] range

    Example:
        >>> blend_probabilities(0.65, 0.60, 0.7)
        0.635
    """
    # Validate inputs
    model_weight = max(0.0, min(1.0, model_weight))
    model_prob = max(0.0, min(1.0, model_prob))
    market_prob = max(0.0, min(1.0, market_prob))

    # Weighted average
    blended = (model_prob * model_weight) + (market_prob * (1.0 - model_weight))

    # Clamp to valid probability range (avoid 0 and 1 for betting math)
    return max(0.01, min(0.99, blended))


class ProbabilityBlender:
    """Full-featured probability blender with confidence adjustment.

    This blender can adjust the model weight based on the model's confidence
    interval width. When the model is less confident (wider interval), it
    reduces the model weight to rely more on market prices.

    Attributes:
        model_weight: Base weight for ML model (0-1)
        min_confidence: Threshold for starting confidence penalty

    Example:
        >>> blender = ProbabilityBlender(model_weight=0.7)
        >>> blended, weight = blender.blend(0.65, 0.60, confidence_width=0.20)
        >>> print(f"Blended: {blended:.1%} (effective weight: {weight:.1%})")
        >>> print(blender.explain_blend(0.65, 0.60, blended))
    """

    def __init__(
        self,
        model_weight: float = 0.7,
        min_model_confidence: float = 0.1,
    ) -> None:
        """Initialize the probability blender.

        Args:
            model_weight: Weight for ML model probability (0-1).
                         Default 0.7 (70% model, 30% market).
            min_model_confidence: If model confidence interval width exceeds this,
                                  reduce model weight proportionally.
                                  Default 0.1 (10% interval width).
        """
        self.model_weight = max(0.0, min(1.0, model_weight))
        self.min_confidence = min_model_confidence

    def blend(
        self,
        model_prob: float,
        market_prob: float,
        confidence_width: float | None = None,
    ) -> tuple[float, float]:
        """Blend probabilities with optional confidence adjustment.

        When confidence_width is provided and exceeds min_confidence threshold,
        the model weight is reduced proportionally. This makes the blending
        more conservative when the model is uncertain.

        Args:
            model_prob: ML model's estimated probability (0-1)
            market_prob: Market-implied probability from odds (0-1)
            confidence_width: Width of model's confidence interval (optional)
                             e.g., 0.15 for interval from 0.55 to 0.70

        Returns:
            Tuple of (blended_probability, effective_model_weight)

        Example:
            >>> blender = ProbabilityBlender(model_weight=0.7)
            >>> # Without confidence adjustment
            >>> blended, weight = blender.blend(0.65, 0.60)
            >>> assert weight == 0.7
            >>>
            >>> # With wide confidence interval (uncertain model)
            >>> blended, weight = blender.blend(0.65, 0.60, confidence_width=0.25)
            >>> assert weight < 0.7  # Weight reduced due to uncertainty
        """
        effective_weight = self.model_weight

        # Apply confidence penalty if interval is wide
        if confidence_width is not None and confidence_width > self.min_confidence:
            # Calculate penalty: wider interval = larger penalty
            # Cap penalty at 50% reduction
            confidence_penalty = min(confidence_width / 0.5, 0.5)
            effective_weight = self.model_weight * (1.0 - confidence_penalty)

        blended = blend_probabilities(model_prob, market_prob, effective_weight)
        return (blended, effective_weight)

    def explain_blend(
        self,
        model_prob: float,
        market_prob: float,
        blended_prob: float,
    ) -> str:
        """Return human-readable explanation of the blend.

        Shows model vs market comparison and the blended result.

        Args:
            model_prob: ML model's estimated probability
            market_prob: Market-implied probability
            blended_prob: Result of blending

        Returns:
            Formatted string explaining the blend

        Example:
            >>> blender = ProbabilityBlender()
            >>> blender.explain_blend(0.65, 0.62, 0.641)
            'Model: 65.0% (+3.0% vs market), Market: 62.0%, Blended: 64.1%'
        """
        diff = model_prob - market_prob
        sign = "+" if diff >= 0 else ""

        return (
            f"Model: {model_prob * 100:.1f}% ({sign}{diff * 100:.1f}% vs market), "
            f"Market: {market_prob * 100:.1f}%, "
            f"Blended: {blended_prob * 100:.1f}%"
        )


def get_model_weight_from_env() -> float:
    """Get model weight from environment variable.

    Reads ML_MODEL_WEIGHT environment variable if set, otherwise
    returns the default of 0.7.

    This allows CLI/config-level override of the blending ratio
    without code changes.

    Returns:
        Model weight (0-1), defaults to 0.7

    Example:
        >>> import os
        >>> os.environ["ML_MODEL_WEIGHT"] = "0.8"
        >>> get_model_weight_from_env()
        0.8
    """
    default = 0.7

    try:
        value = os.environ.get("ML_MODEL_WEIGHT")
        if value is None:
            return default

        weight = float(value)
        # Clamp to valid range
        return max(0.0, min(1.0, weight))

    except (ValueError, TypeError):
        return default
