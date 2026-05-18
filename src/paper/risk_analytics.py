"""Paper trading risk analytics."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime

from paper.account import PaperTradingAccount, PaperTrade


@dataclass(frozen=True)
class PaperRiskAnalytics:
    """Serializable paper trading risk analytics."""

    equity_curve: list[dict[str, object]]
    drawdown_curve: list[dict[str, object]]
    realized_pnl_by_regime: dict[str, float]
    realized_pnl_by_strategy: dict[str, float]
    consecutive_wins: int
    consecutive_losses: int
    daily_trade_count: dict[str, int]
    max_adverse_excursion: float | None
    confidence_vs_result: list[dict[str, object]]

    def to_dict(self) -> dict[str, object]:
        """Return JSON-safe analytics."""
        return {
            "equity_curve": self.equity_curve,
            "drawdown_curve": self.drawdown_curve,
            "realized_pnl_by_regime": self.realized_pnl_by_regime,
            "realized_pnl_by_strategy": self.realized_pnl_by_strategy,
            "consecutive_wins": self.consecutive_wins,
            "consecutive_losses": self.consecutive_losses,
            "daily_trade_count": self.daily_trade_count,
            "max_adverse_excursion": self.max_adverse_excursion,
            "confidence_vs_result": self.confidence_vs_result,
        }


class PaperRiskAnalyticsBuilder:
    """Builds risk analytics from paper account state."""

    def build(self, account: PaperTradingAccount) -> PaperRiskAnalytics:
        """Return aggregate paper-trading risk analytics."""
        closed = sorted(account.closed_trades, key=lambda trade: _dt_key(trade.closed_at or trade.opened_at))
        pnl_by_regime: dict[str, float] = defaultdict(float)
        pnl_by_strategy: dict[str, float] = defaultdict(float)
        daily_count: dict[str, int] = defaultdict(int)
        confidence_vs_result: list[dict[str, object]] = []
        for trade in closed:
            regime = str(getattr(trade, "market_regime", "UNKNOWN") or "UNKNOWN")
            pnl_by_regime[regime] += trade.pnl
            pnl_by_strategy[str(trade.strategy)] += trade.pnl
            daily_count[_date_key(trade.opened_at)] += 1
            confidence_vs_result.append(
                {
                    "confidence": trade.confidence,
                    "result": trade.result,
                    "pnl": trade.pnl,
                    "strategy": trade.strategy,
                    "regime": regime,
                }
            )
        return PaperRiskAnalytics(
            equity_curve=[
                {"timestamp": snapshot.to_dict()["timestamp"], "equity": snapshot.equity}
                for snapshot in account.snapshots
            ],
            drawdown_curve=[
                {"timestamp": snapshot.to_dict()["timestamp"], "drawdown": snapshot.drawdown}
                for snapshot in account.snapshots
            ],
            realized_pnl_by_regime=dict(pnl_by_regime),
            realized_pnl_by_strategy=dict(pnl_by_strategy),
            consecutive_wins=_streak(closed, "WIN"),
            consecutive_losses=_streak(closed, "LOSS"),
            daily_trade_count=dict(daily_count),
            max_adverse_excursion=None,
            confidence_vs_result=confidence_vs_result,
        )


def _streak(trades: list[PaperTrade], result: str) -> int:
    """Return trailing streak count for a result."""
    count = 0
    for trade in reversed(trades):
        if str(trade.result).upper() == result:
            count += 1
            continue
        break
    return count


def _date_key(value: datetime | str) -> str:
    """Return YYYY-MM-DD key."""
    return value.date().isoformat() if isinstance(value, datetime) else str(value)[:10]


def _dt_key(value: datetime | str) -> str:
    """Return sortable datetime key."""
    return value.isoformat() if isinstance(value, datetime) else str(value)
