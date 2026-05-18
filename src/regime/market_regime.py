"""Market regime enum used by strategy and signal filters."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class MarketRegime(str, Enum):
    """Supported market regimes for filtering model signals."""

    UPTREND = "UPTREND"
    DOWNTREND = "DOWNTREND"
    SIDEWAY = "SIDEWAY"
    BREAKOUT_UP = "BREAKOUT_UP"
    BREAKOUT_DOWN = "BREAKOUT_DOWN"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    LOW_VOLATILITY = "LOW_VOLATILITY"
    UNKNOWN = "UNKNOWN"


class VolatilityLevel(str, Enum):
    """Normalized volatility levels used by market context."""

    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    EXTREME = "EXTREME"


@dataclass(frozen=True)
class RegimeScore:
    """Soft score for one market regime."""

    regime: MarketRegime
    score: float
    reasons: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class MarketTransitionWarning:
    """Warning that the current regime may be transitioning."""

    warning_type: str
    message: str
    severity: float = 0.0


@dataclass(frozen=True)
class RegimeContext:
    """Soft regime state for one feature row."""

    primary_regime: MarketRegime
    regime_scores: dict[str, float]
    confidence: float
    uncertainty_score: float
    transition_warning: bool
    volatility_level: VolatilityLevel
    reasons: list[str] = field(default_factory=list)
    warnings: list[MarketTransitionWarning] = field(default_factory=list)


@dataclass(frozen=True)
class MarketContext:
    """Complete soft market context produced by the context engine."""

    regime: RegimeContext
    transition_warnings: list[MarketTransitionWarning] = field(default_factory=list)
    features_used: list[str] = field(default_factory=list)

    @property
    def primary_regime(self) -> MarketRegime:
        """Return the highest-confidence regime."""
        return self.regime.primary_regime

    @property
    def regime_scores(self) -> dict[str, float]:
        """Return soft regime scores."""
        return self.regime.regime_scores

    @property
    def confidence(self) -> float:
        """Return confidence of the primary regime."""
        return self.regime.confidence

    @property
    def uncertainty_score(self) -> float:
        """Return uncertainty as 1 - confidence."""
        return self.regime.uncertainty_score


RegimeDetectionResult = RegimeContext
