"""Multi-dimensional backtest analytics for edge attribution."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
import json
import math
from typing import Any

from backtest.models import Trade, TradeResult


CONFLUENCE_BUCKETS = (
    (0.00, 0.40, "0.00-0.40"),
    (0.40, 0.55, "0.40-0.55"),
    (0.55, 0.68, "0.55-0.68"),
    (0.68, 0.80, "0.68-0.80"),
    (0.80, 1.01, "0.80-1.00"),
)


@dataclass(frozen=True)
class AnalyzerMetrics:
    """Metrics for one segment."""

    total_trades: int
    winrate: float
    net_profit: float
    gross_profit: float
    gross_loss: float
    profit_factor: float
    expectancy: float
    max_drawdown: float
    avg_r_multiple: float
    avg_holding_bars: float
    best_trade: float
    worst_trade: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_trades": self.total_trades,
            "winrate": self.winrate,
            "net_profit": self.net_profit,
            "gross_profit": self.gross_profit,
            "gross_loss": self.gross_loss,
            "profit_factor": self.profit_factor,
            "expectancy": self.expectancy,
            "max_drawdown": self.max_drawdown,
            "avg_r_multiple": self.avg_r_multiple,
            "avg_holding_bars": self.avg_holding_bars,
            "best_trade": self.best_trade,
            "worst_trade": self.worst_trade,
        }


@dataclass(frozen=True)
class BacktestAnalysisReport:
    """Full multi-dimensional analytics output."""

    overall: AnalyzerMetrics
    grouped: dict[str, dict[str, AnalyzerMetrics]]
    wait_reason_distribution: dict[str, int]
    generated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "overall": self.overall.to_dict(),
            "grouped": {
                dimension: {
                    key: metrics.to_dict()
                    for key, metrics in segments.items()
                }
                for dimension, segments in self.grouped.items()
            },
            "wait_reason_distribution": dict(self.wait_reason_distribution),
        }

    def to_json(self) -> str:
        return json.dumps(_json_ready(self.to_dict()), indent=2, sort_keys=True)


class BacktestAnalyzer:
    """Analyze trades by regime/strategy/setup and reasoning dimensions."""

    def analyze(self, trades: list[Trade]) -> BacktestAnalysisReport:
        grouped: dict[str, dict[str, AnalyzerMetrics]] = {
            "regime": self._group_and_metric(trades, lambda trade: trade.market_regime or "UNKNOWN"),
            "strategy": self._group_and_metric(trades, lambda trade: trade.strategy.value),
            "setup_type": self._group_and_metric(trades, lambda trade: trade.setup_type or "UNKNOWN"),
            "setup_grade": self._group_and_metric(trades, lambda trade: trade.setup_grade or "UNKNOWN"),
            "signal": self._group_and_metric(trades, lambda trade: trade.direction.value),
            "wait_reason": self._group_and_metric(trades, lambda trade: trade.wait_reason or "NONE"),
            "safety_filter": self._group_and_metric(trades, lambda trade: trade.safety_filter or "NONE"),
            "model_scope": self._group_and_metric(trades, lambda trade: trade.model_scope or "UNKNOWN"),
            "probability_source": self._group_and_metric(trades, lambda trade: trade.probability_source or "UNKNOWN"),
            "conflict_level": self._group_and_metric(trades, lambda trade: trade.conflict_level or "NONE"),
            "confluence_bucket": self._group_and_metric(
                trades,
                lambda trade: confluence_bucket(float(trade.confluence_score)),
            ),
        }
        wait_distribution = self._wait_reason_distribution(trades)
        return BacktestAnalysisReport(
            overall=self._metrics(trades),
            grouped=grouped,
            wait_reason_distribution=wait_distribution,
        )

    def _group_and_metric(
        self,
        trades: list[Trade],
        key_fn,
    ) -> dict[str, AnalyzerMetrics]:
        grouped: dict[str, list[Trade]] = {}
        for trade in trades:
            key = str(key_fn(trade))
            grouped.setdefault(key, []).append(trade)
        return {
            key: self._metrics(items)
            for key, items in sorted(grouped.items(), key=lambda item: item[0])
        }

    def _wait_reason_distribution(self, trades: list[Trade]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for trade in trades:
            reason = str(trade.wait_reason or "NONE")
            counts[reason] = counts.get(reason, 0) + 1
        return dict(sorted(counts.items(), key=lambda item: item[0]))

    def _metrics(self, trades: list[Trade]) -> AnalyzerMetrics:
        total = len(trades)
        wins = sum(1 for trade in trades if trade.result is TradeResult.WIN)
        net_profit = sum(float(trade.pnl) for trade in trades)
        gross_profit = sum(float(trade.pnl) for trade in trades if trade.pnl > 0)
        gross_loss = abs(sum(float(trade.pnl) for trade in trades if trade.pnl < 0))
        holding = [float(trade.holding_bars) for trade in trades]
        r_multiples = [_r_multiple(trade) for trade in trades]
        return AnalyzerMetrics(
            total_trades=total,
            winrate=wins / total if total else 0.0,
            net_profit=net_profit,
            gross_profit=gross_profit,
            gross_loss=gross_loss,
            profit_factor=_profit_factor(gross_profit, gross_loss),
            expectancy=net_profit / total if total else 0.0,
            max_drawdown=_max_drawdown([float(trade.pnl) for trade in trades]),
            avg_r_multiple=(sum(r_multiples) / len(r_multiples)) if r_multiples else 0.0,
            avg_holding_bars=(sum(holding) / len(holding)) if holding else 0.0,
            best_trade=max((float(trade.pnl) for trade in trades), default=0.0),
            worst_trade=min((float(trade.pnl) for trade in trades), default=0.0),
        )


def confluence_bucket(score: float) -> str:
    """Return confluence bucket label."""
    value = max(0.0, min(float(score), 1.0))
    for lower, upper, label in CONFLUENCE_BUCKETS:
        if lower <= value < upper:
            return label
    return "UNKNOWN"


def _r_multiple(trade: Trade) -> float:
    risk_per_unit = abs(float(trade.entry) - float(trade.stop_loss))
    risk_amount = risk_per_unit * max(float(trade.position_size), 0.0)
    if risk_amount <= 0:
        return 0.0
    return float(trade.pnl) / risk_amount


def _profit_factor(gross_profit: float, gross_loss: float) -> float:
    if gross_loss > 0:
        return gross_profit / gross_loss
    if gross_profit > 0:
        return float("inf")
    return 0.0


def _max_drawdown(pnls: list[float]) -> float:
    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    for pnl in pnls:
        equity += pnl
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
    return max_dd


def _json_ready(value: Any) -> Any:
    if isinstance(value, float):
        if math.isinf(value):
            return "Infinity"
        if math.isnan(value):
            return None
        return value
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    return value

