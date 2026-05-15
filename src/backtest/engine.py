"""Backward-compatible exports for backtesting."""

from __future__ import annotations

from backtest.models import BacktestReport as BacktestResult

__all__ = ["BacktestResult"]
