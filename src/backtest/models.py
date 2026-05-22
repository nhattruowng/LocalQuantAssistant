"""Backtest domain models."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from signals.models import SignalType, StrategyType


class TradeResult(str, Enum):
    """Closed trade outcomes."""

    WIN = "WIN"
    LOSS = "LOSS"
    BREAKEVEN = "BREAKEVEN"
    TIMEOUT = "TIMEOUT"


@dataclass(frozen=True)
class Trade:
    """Simulated trade produced by a backtest."""

    symbol: str
    timeframe: str
    direction: SignalType
    strategy: StrategyType
    opened_at: datetime | str
    closed_at: datetime | str
    entry: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    exit_price: float
    position_size: float
    gross_pnl: float
    fees: float
    slippage: float
    pnl: float
    risk_reward: float
    result: TradeResult
    confidence: float
    reasons: list[str]
    market_regime: str = "UNKNOWN"
    confidence_bucket: str = "UNKNOWN"
    volatility_bucket: str = "UNKNOWN"
    atr_percent: float = 0.0
    holding_bars: int = 0
    setup_type: str = "UNKNOWN"
    setup_grade: str = "UNKNOWN"
    wait_reason: str = "NONE"
    safety_filter: str = "NONE"
    model_scope: str = "UNKNOWN"
    probability_source: str = "raw"
    conflict_level: str = "NONE"
    confluence_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Serialize trade into primitive values."""
        data = asdict(self)
        data["direction"] = self.direction.value
        data["strategy"] = self.strategy.value
        data["result"] = self.result.value
        if isinstance(self.opened_at, datetime):
            data["opened_at"] = self.opened_at.isoformat()
        if isinstance(self.closed_at, datetime):
            data["closed_at"] = self.closed_at.isoformat()
        return data


@dataclass(frozen=True)
class BacktestSegmentReport:
    """Metrics for one filtered group of backtest trades."""

    total_trades: int
    winrate: float
    gross_profit: float
    gross_loss: float
    net_profit: float
    profit_factor: float
    max_drawdown: float
    expectancy: float
    avg_holding_bars: float
    avg_confidence: float
    best_trade: float
    worst_trade: float

    def to_dict(self) -> dict[str, Any]:
        """Serialize segment metrics into primitive values."""
        return asdict(self)


@dataclass(frozen=True)
class BacktestReport:
    """Summary report for a completed backtest."""

    symbol: str
    timeframe: str
    mode: str
    total_trades: int
    winrate: float
    gross_profit: float
    gross_loss: float
    net_profit: float
    profit_factor: float
    max_drawdown: float
    average_win: float
    average_loss: float
    expectancy: float
    average_risk_reward: float
    longest_win_streak: int
    longest_loss_streak: int
    trades: list[Trade]
    grouped: dict[str, dict[str, BacktestSegmentReport]]

    def to_summary_dict(self) -> dict[str, Any]:
        """Serialize report summary without full trade payload."""
        data = asdict(self)
        data.pop("trades")
        return data
