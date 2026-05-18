"""Grouped backtest performance analysis."""

from __future__ import annotations

from collections.abc import Callable, Iterable
import math

from backtest.models import BacktestSegmentReport, Trade, TradeResult


CONFIDENCE_BUCKETS = (
    (0.50, 0.60, "0.50-0.60"),
    (0.60, 0.70, "0.60-0.70"),
    (0.70, 0.80, "0.70-0.80"),
    (0.80, 0.90, "0.80-0.90"),
    (0.90, 1.01, "0.90-1.00"),
)


class MetricsAggregator:
    """Calculates reusable metrics for any list of closed trades."""

    def aggregate(self, trades: Iterable[Trade]) -> BacktestSegmentReport:
        """Return segment metrics for the provided trades."""
        items = list(trades)
        wins = [trade for trade in items if trade.result is TradeResult.WIN]
        gross_profit = sum(trade.pnl for trade in items if trade.pnl > 0)
        gross_loss = abs(sum(trade.pnl for trade in items if trade.pnl < 0))
        net_profit = sum(trade.pnl for trade in items)
        total_trades = len(items)
        return BacktestSegmentReport(
            total_trades=total_trades,
            winrate=len(wins) / total_trades if total_trades else 0.0,
            gross_profit=gross_profit,
            gross_loss=gross_loss,
            net_profit=net_profit,
            profit_factor=_profit_factor(gross_profit, gross_loss),
            max_drawdown=calculate_max_drawdown([trade.pnl for trade in items]),
            expectancy=net_profit / total_trades if total_trades else 0.0,
            avg_holding_bars=_average([float(trade.holding_bars) for trade in items]),
            avg_confidence=_average([trade.confidence for trade in items]),
            best_trade=max((trade.pnl for trade in items), default=0.0),
            worst_trade=min((trade.pnl for trade in items), default=0.0),
        )


class GroupedBacktestAnalyzer:
    """Builds grouped backtest segment reports."""

    def __init__(self, aggregator: MetricsAggregator | None = None) -> None:
        self._aggregator = aggregator or MetricsAggregator()

    def analyze(self, trades: list[Trade]) -> dict[str, dict[str, BacktestSegmentReport]]:
        """Return reports grouped by core trading dimensions."""
        return {
            "by_market_regime": self._group_by(
                trades,
                lambda trade: trade.market_regime or "UNKNOWN",
            ),
            "by_strategy": self._group_by(trades, lambda trade: trade.strategy.value),
            "by_signal_type": self._group_by(trades, lambda trade: trade.direction.value),
            "by_confidence_bucket": self._group_by(
                trades,
                lambda trade: confidence_bucket(trade.confidence),
            ),
            "by_volatility_bucket": self._group_by(
                trades,
                lambda trade: trade.volatility_bucket or "UNKNOWN",
            ),
        }

    def _group_by(
        self,
        trades: list[Trade],
        key_fn: Callable[[Trade], str],
    ) -> dict[str, BacktestSegmentReport]:
        """Group trades and aggregate metrics for each group."""
        grouped: dict[str, list[Trade]] = {}
        for trade in trades:
            grouped.setdefault(key_fn(trade), []).append(trade)
        return {
            key: self._aggregator.aggregate(items)
            for key, items in sorted(grouped.items(), key=lambda item: item[0])
        }


def confidence_bucket(confidence: float) -> str:
    """Return the configured confidence bucket label."""
    for lower, upper, label in CONFIDENCE_BUCKETS:
        if lower <= confidence < upper:
            return label
    if confidence < 0.50:
        return "<0.50"
    return "UNKNOWN"


def volatility_bucket(
    atr_percent: float,
    low_max: float,
    normal_max: float,
    high_max: float,
) -> str:
    """Bucket ATR percent into LOW, NORMAL, HIGH, or EXTREME."""
    if not math.isfinite(atr_percent):
        return "UNKNOWN"
    if atr_percent < low_max:
        return "LOW"
    if atr_percent < normal_max:
        return "NORMAL"
    if atr_percent < high_max:
        return "HIGH"
    return "EXTREME"


def calculate_max_drawdown(pnls: list[float]) -> float:
    """Calculate absolute max drawdown from trade PnL equity curve."""
    equity = 0.0
    peak = 0.0
    max_drawdown = 0.0
    for pnl in pnls:
        equity += pnl
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, peak - equity)
    return max_drawdown


def _profit_factor(gross_profit: float, gross_loss: float) -> float:
    """Return profit factor while handling no-loss segments."""
    if gross_loss > 0:
        return gross_profit / gross_loss
    if gross_profit > 0:
        return float("inf")
    return 0.0


def _average(values: list[float]) -> float:
    """Return mean value or zero for an empty list."""
    return sum(values) / len(values) if values else 0.0
