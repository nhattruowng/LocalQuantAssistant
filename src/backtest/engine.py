"""Backtest engine contracts."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BacktestResult:
    """Summary metrics for a completed backtest."""

    total_trades: int
    win_rate: float
    max_drawdown: float
