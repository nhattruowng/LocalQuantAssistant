"""Backtest domain models."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from signal.models import SignalType, StrategyType


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

    def to_summary_dict(self) -> dict[str, Any]:
        """Serialize report summary without full trade payload."""
        data = asdict(self)
        data.pop("trades")
        return data
