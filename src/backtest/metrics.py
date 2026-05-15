"""Backtest metric calculations."""

from __future__ import annotations

from backtest.models import BacktestReport, Trade, TradeResult


def build_report(
    symbol: str,
    timeframe: str,
    mode: str,
    trades: list[Trade],
) -> BacktestReport:
    """Calculate report metrics from closed trades."""
    wins = [trade.pnl for trade in trades if trade.result is TradeResult.WIN]
    losses = [trade.pnl for trade in trades if trade.result is TradeResult.LOSS]
    gross_profit = sum(pnl for pnl in wins if pnl > 0)
    gross_loss = abs(sum(pnl for pnl in losses if pnl < 0))
    net_profit = sum(trade.pnl for trade in trades)
    total_trades = len(trades)
    winrate = len(wins) / total_trades if total_trades else 0.0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf") if gross_profit > 0 else 0.0
    average_win = gross_profit / len(wins) if wins else 0.0
    average_loss = gross_loss / len(losses) if losses else 0.0
    expectancy = net_profit / total_trades if total_trades else 0.0
    average_rr = (
        sum(trade.risk_reward for trade in trades) / total_trades if total_trades else 0.0
    )
    return BacktestReport(
        symbol=symbol,
        timeframe=timeframe,
        mode=mode,
        total_trades=total_trades,
        winrate=winrate,
        gross_profit=gross_profit,
        gross_loss=gross_loss,
        net_profit=net_profit,
        profit_factor=profit_factor,
        max_drawdown=calculate_max_drawdown([trade.pnl for trade in trades]),
        average_win=average_win,
        average_loss=average_loss,
        expectancy=expectancy,
        average_risk_reward=average_rr,
        longest_win_streak=_longest_streak(trades, TradeResult.WIN),
        longest_loss_streak=_longest_streak(trades, TradeResult.LOSS),
        trades=trades,
    )


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
