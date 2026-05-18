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


@dataclass(frozen=True)
class RegimeScore:
    """Soft score for one market regime."""

    regime: MarketRegime
    score: float
    reasons: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RegimeDetectionResult:
    """Soft market regime detection result for one feature row."""

    primary_regime: MarketRegime
    regime_scores: dict[str, float]
    confidence: float
    transition_warning: bool
    reasons: list[str] = field(default_factory=list)
