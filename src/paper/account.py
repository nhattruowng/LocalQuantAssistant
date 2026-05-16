"""Paper trading account models."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class PaperTrade:
    """A simulated trade that never represents a real order."""

    id: int | None
    symbol: str
    timeframe: str
    direction: str
    strategy: str
    status: str
    opened_at: datetime | str
    entry: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    position_size: float
    confidence: float
    closed_at: datetime | str | None = None
    exit_price: float | None = None
    pnl: float = 0.0
    result: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize trade into primitive values for UI tables."""
        data = asdict(self)
        if isinstance(self.opened_at, datetime):
            data["opened_at"] = self.opened_at.isoformat()
        if isinstance(self.closed_at, datetime):
            data["closed_at"] = self.closed_at.isoformat()
        return data


@dataclass(frozen=True)
class PaperAccountSnapshot:
    """Point-in-time paper account state."""

    timestamp: datetime | str
    initial_balance: float
    current_balance: float
    realized_pnl: float
    unrealized_pnl: float
    equity: float
    drawdown: float

    def to_dict(self) -> dict[str, Any]:
        """Serialize snapshot into primitive values for UI tables."""
        data = asdict(self)
        if isinstance(self.timestamp, datetime):
            data["timestamp"] = self.timestamp.isoformat()
        return data


@dataclass(frozen=True)
class PaperTradingAccount:
    """Current paper trading account state."""

    initial_balance: float
    current_balance: float
    realized_pnl: float
    unrealized_pnl: float
    equity: float
    drawdown: float
    open_positions: list[PaperTrade]
    closed_trades: list[PaperTrade]
    snapshots: list[PaperAccountSnapshot]

    def to_dict(self) -> dict[str, Any]:
        """Serialize account state for dashboard rendering."""
        return {
            "initial_balance": self.initial_balance,
            "current_balance": self.current_balance,
            "realized_pnl": self.realized_pnl,
            "unrealized_pnl": self.unrealized_pnl,
            "equity": self.equity,
            "drawdown": self.drawdown,
            "open_positions": [trade.to_dict() for trade in self.open_positions],
            "closed_trades": [trade.to_dict() for trade in self.closed_trades],
            "snapshots": [snapshot.to_dict() for snapshot in self.snapshots],
        }
