"""Shared context passed through the trading agent pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field

from domain.entities import OHLCVBar, RiskPlan, TradeSetup
from domain.enums import MarketRegime, StrategyType, TradingAction


@dataclass
class AgentContext:
    """Mutable pipeline state shared by deterministic agents."""

    symbol: str
    ohlcv: list[OHLCVBar] = field(default_factory=list)
    features: dict[str, float] = field(default_factory=dict)
    indicators: dict[str, float] = field(default_factory=dict)
    regime: MarketRegime | None = None
    probabilities: dict[TradingAction, float] = field(default_factory=dict)
    strategy: StrategyType | None = None
    risk_plan: RiskPlan | None = None
    action: TradingAction = TradingAction.WAIT
    confidence: float = 0.0
    reasons: list[str] = field(default_factory=list)
    explanation: str = ""
    trade_setup: TradeSetup | None = None
    backtest_report: dict[str, float] = field(default_factory=dict)

    def add_reason(self, reason: str) -> None:
        """Append a human-readable pipeline reason."""
        self.reasons.append(reason)
