"""Signal engine data models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
import json
from typing import Mapping

from regime.market_regime import MarketRegime


class SignalType(str, Enum):
    """Final signal types produced by the system."""

    BUY = "BUY"
    SELL = "SELL"
    WAIT = "WAIT"


class StrategyType(str, Enum):
    """Supported setup strategy families."""

    TREND_FOLLOWING = "TREND_FOLLOWING"
    BREAKOUT_CONFIRMATION = "BREAKOUT_CONFIRMATION"
    MEAN_REVERSION = "MEAN_REVERSION"
    NONE = "NONE"


@dataclass(frozen=True)
class SignalContext:
    """Input context for strategy and signal decisions."""

    symbol: str
    timeframe: str
    timestamp: datetime | str
    market_regime: MarketRegime | str
    features: Mapping[str, object]
    probabilities: Mapping[str | SignalType, float]
    primary_timeframe: str | None = None
    higher_timeframes: tuple[str, ...] = field(default_factory=tuple)
    primary_features: Mapping[str, object] | None = None
    higher_timeframe_features: Mapping[str, Mapping[str, object]] = field(default_factory=dict)
    primary_regime: MarketRegime | str | None = None
    higher_timeframe_regimes: Mapping[str, MarketRegime | str] = field(default_factory=dict)
    model_prediction: Mapping[str, object] = field(default_factory=dict)
    strategy_scores: list[StrategyScore] = field(default_factory=list)
    risk_plan: RiskPlan | None = None
    explanation_context: Mapping[str, object] = field(default_factory=dict)
    regime_scores: Mapping[str, float] = field(default_factory=dict)
    regime_confidence: float = 1.0
    transition_warning: bool = False
    raw_probabilities: Mapping[str | SignalType, float] | None = None
    calibrated_probabilities: Mapping[str | SignalType, float] | None = None
    probability_source: str = "raw"

    def feature(self, key: str, default: float = 0.0) -> float:
        """Read a numeric feature value."""
        source = self.primary_features or self.features
        value = source.get(key, default)
        return float(value)

    def probability(self, signal: SignalType) -> float:
        """Read model probability for a signal."""
        return float(
            self.probabilities.get(signal, self.probabilities.get(signal.value, 0.0))
        )

    def regime_value(self) -> str:
        """Return market regime as a string value."""
        regime = self.primary_regime if self.primary_regime is not None else self.market_regime
        if isinstance(regime, MarketRegime):
            return regime.value
        return str(regime)

    def soft_regime_scores(self) -> Mapping[str, float]:
        """Return soft regime scores from context or feature payload."""
        if self.regime_scores:
            return self.regime_scores
        source = self.primary_features or self.features
        raw = source.get("regime_scores")
        if isinstance(raw, Mapping):
            return {str(key): float(value) for key, value in raw.items()}
        if isinstance(raw, str):
            try:
                decoded = json.loads(raw)
            except json.JSONDecodeError:
                return {}
            if isinstance(decoded, dict):
                return {str(key): float(value) for key, value in decoded.items()}
        return {}


@dataclass(frozen=True)
class StructuredExplanation:
    """Structured signal explanation grouped by decision layer."""

    final_decision: str
    summary: str
    regime: dict[str, object]
    strategy: dict[str, object]
    risk: dict[str, object]
    model: dict[str, object]
    multi_timeframe: dict[str, object]
    final_decision_summary: str


@dataclass(frozen=True)
class StrategyDecision:
    """Candidate decision returned by a strategy."""

    signal: SignalType
    strategy: StrategyType
    model_probability: float
    trend_score: float
    indicator_score: float
    volume_score: float
    reasons: list[str] = field(default_factory=list)
    score: float = 0.0
    confidence: float = 0.0
    failed_conditions: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class StrategyScore:
    """Scored strategy candidate used by the ensemble."""

    strategy_type: StrategyType
    signal: SignalType
    score: float
    confidence: float
    reasons: list[str] = field(default_factory=list)
    failed_conditions: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class StrategyEnsembleResult:
    """Result of evaluating several strategy candidates."""

    selected: StrategyScore | None
    candidates: list[StrategyScore]
    rejected: list[StrategyScore] = field(default_factory=list)
    conflict: bool = False
    reasons: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RiskPlan:
    """Risk plan for an actionable setup."""

    entry: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    risk_reward: float
    position_size: float
    risk_notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class TradeSetup:
    """Final setup recommendation. This object never represents an order."""

    symbol: str
    timeframe: str
    timestamp: datetime | str
    market_regime: str
    signal: SignalType
    strategy: StrategyType
    confidence: float
    entry: float | None
    stop_loss: float | None
    take_profit_1: float | None
    take_profit_2: float | None
    risk_reward: float | None
    position_size: float | None
    reasons: list[str]
    risk_notes: list[str]
    explainability: dict[str, object] | None = None
    explanation_v2: dict[str, object] | None = None
    strategy_diagnostics: dict[str, object] | None = None
    probabilities: dict[str, float] | None = None
    raw_probabilities: dict[str, float] | None = None
    calibrated_probabilities: dict[str, float] | None = None
    probability_source: str = "raw"
    model_scope_used: str | None = None
    model_version: str | None = None
    fallback_reason: str | None = None

    def to_dict(self) -> dict[str, object]:
        """Serialize setup into API-friendly primitive values."""
        data = asdict(self)
        data["signal"] = self.signal.value
        data["strategy"] = self.strategy.value
        if isinstance(self.timestamp, datetime):
            data["timestamp"] = self.timestamp.isoformat()
        return data
