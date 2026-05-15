"""Signal engine data models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
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
    features: Mapping[str, float]
    probabilities: Mapping[str | SignalType, float]

    def feature(self, key: str, default: float = 0.0) -> float:
        """Read a numeric feature value."""
        value = self.features.get(key, default)
        return float(value)

    def probability(self, signal: SignalType) -> float:
        """Read model probability for a signal."""
        return float(
            self.probabilities.get(signal, self.probabilities.get(signal.value, 0.0))
        )

    def regime_value(self) -> str:
        """Return market regime as a string value."""
        if isinstance(self.market_regime, MarketRegime):
            return self.market_regime.value
        return str(self.market_regime)


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

    def to_dict(self) -> dict[str, object]:
        """Serialize setup into API-friendly primitive values."""
        data = asdict(self)
        data["signal"] = self.signal.value
        data["strategy"] = self.strategy.value
        if isinstance(self.timestamp, datetime):
            data["timestamp"] = self.timestamp.isoformat()
        return data
