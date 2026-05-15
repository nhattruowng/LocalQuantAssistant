"""Backtest agent."""

from __future__ import annotations

from agents.base import BaseAgent
from agents.context import AgentContext


class BacktestAgent(BaseAgent):
    """Runs a simple local backtest metric report."""

    name = "BacktestAgent"

    def run(self, context: AgentContext) -> AgentContext:
        """Generate baseline backtest metrics for available OHLCV data."""
        self.log_start(context)
        closes = [bar.close for bar in context.ohlcv]
        total_return = 0.0
        if len(closes) >= 2 and closes[0] > 0:
            total_return = (closes[-1] - closes[0]) / closes[0]

        context.backtest_report = {
            "bars": float(len(closes)),
            "total_return": total_return,
            "max_drawdown": self._max_drawdown(closes),
        }
        context.add_reason("Backtest metric report generated.")
        self.log_finish(context)
        return context

    def _max_drawdown(self, closes: list[float]) -> float:
        """Calculate max drawdown from close prices."""
        peak = 0.0
        max_drawdown = 0.0
        for close in closes:
            peak = max(peak, close)
            if peak > 0:
                max_drawdown = min(max_drawdown, (close - peak) / peak)
        return abs(max_drawdown)
