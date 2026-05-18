"""Backtest metric calculations."""

from __future__ import annotations

from backtest.analysis import (
    GroupedBacktestAnalyzer,
    MetricsAggregator,
    calculate_max_drawdown,
)
from backtest.models import BacktestReport, Trade, TradeResult


def build_report(
    symbol: str,
    timeframe: str,
    mode: str,
    trades: list[Trade],
) -> BacktestReport:
    """Calculate report metrics from closed trades."""
    summary = MetricsAggregator().aggregate(trades)
    profitable_trades = [trade.pnl for trade in trades if trade.pnl > 0]
    losing_trades = [trade.pnl for trade in trades if trade.pnl < 0]
    average_win = summary.gross_profit / len(profitable_trades) if profitable_trades else 0.0
    average_loss = summary.gross_loss / len(losing_trades) if losing_trades else 0.0
    average_rr = (
        sum(trade.risk_reward for trade in trades) / summary.total_trades
        if summary.total_trades
        else 0.0
    )
    return BacktestReport(
        symbol=symbol,
        timeframe=timeframe,
        mode=mode,
        total_trades=summary.total_trades,
        winrate=summary.winrate,
        gross_profit=summary.gross_profit,
        gross_loss=summary.gross_loss,
        net_profit=summary.net_profit,
        profit_factor=summary.profit_factor,
        max_drawdown=summary.max_drawdown,
        average_win=average_win,
        average_loss=average_loss,
        expectancy=summary.expectancy,
        average_risk_reward=average_rr,
        longest_win_streak=_longest_streak(trades, TradeResult.WIN),
        longest_loss_streak=_longest_streak(trades, TradeResult.LOSS),
        trades=trades,
        grouped=GroupedBacktestAnalyzer().analyze(trades),
    )


def _longest_streak(trades: list[Trade], result: TradeResult) -> int:
    """Return longest consecutive streak for a result."""
    longest = 0
    current = 0
    for trade in trades:
        if trade.result is result:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest
