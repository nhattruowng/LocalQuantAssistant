"""Tests for grouped backtest analysis."""

from __future__ import annotations

import pytest

from backtest.analysis import GroupedBacktestAnalyzer, MetricsAggregator, confidence_bucket
from backtest.metrics import build_report
from backtest.models import Trade, TradeResult
from backtest.report_writer import BacktestReportWriter
from signals.models import SignalType, StrategyType


def test_metrics_aggregator_calculates_winrate():
    report = MetricsAggregator().aggregate(
        [
            _trade(pnl=10.0, result=TradeResult.WIN),
            _trade(pnl=-5.0, result=TradeResult.LOSS),
        ]
    )

    assert report.total_trades == 2
    assert report.winrate == 0.5


def test_metrics_aggregator_calculates_profit_factor():
    report = MetricsAggregator().aggregate(
        [
            _trade(pnl=20.0, result=TradeResult.WIN),
            _trade(pnl=-5.0, result=TradeResult.LOSS),
        ]
    )

    assert report.gross_profit == 20.0
    assert report.gross_loss == 5.0
    assert report.profit_factor == 4.0


def test_metrics_aggregator_calculates_expectancy():
    report = MetricsAggregator().aggregate(
        [
            _trade(pnl=10.0, result=TradeResult.WIN),
            _trade(pnl=-4.0, result=TradeResult.LOSS),
            _trade(pnl=0.0, result=TradeResult.BREAKEVEN),
        ]
    )

    assert report.expectancy == pytest.approx(2.0)


def test_grouped_analyzer_groups_by_market_regime():
    grouped = GroupedBacktestAnalyzer().analyze(
        [
            _trade(pnl=10.0, result=TradeResult.WIN, market_regime="UPTREND"),
            _trade(pnl=-5.0, result=TradeResult.LOSS, market_regime="DOWNTREND"),
            _trade(pnl=7.0, result=TradeResult.WIN, market_regime="UPTREND"),
        ]
    )

    assert grouped["by_market_regime"]["UPTREND"].total_trades == 2
    assert grouped["by_market_regime"]["DOWNTREND"].total_trades == 1


def test_grouped_analyzer_groups_by_confidence_bucket():
    grouped = GroupedBacktestAnalyzer().analyze(
        [
            _trade(pnl=10.0, result=TradeResult.WIN, confidence=0.59),
            _trade(pnl=12.0, result=TradeResult.WIN, confidence=0.72),
            _trade(pnl=-3.0, result=TradeResult.LOSS, confidence=0.75),
        ]
    )

    assert confidence_bucket(0.59) == "0.50-0.60"
    assert grouped["by_confidence_bucket"]["0.50-0.60"].total_trades == 1
    assert grouped["by_confidence_bucket"]["0.70-0.80"].total_trades == 2


def test_metrics_aggregator_handles_no_trades():
    report = MetricsAggregator().aggregate([])

    assert report.total_trades == 0
    assert report.winrate == 0.0
    assert report.net_profit == 0.0
    assert report.profit_factor == 0.0
    assert report.best_trade == 0.0
    assert report.worst_trade == 0.0


def test_metrics_aggregator_handles_zero_gross_loss():
    report = MetricsAggregator().aggregate(
        [
            _trade(pnl=10.0, result=TradeResult.WIN),
            _trade(pnl=5.0, result=TradeResult.WIN),
        ]
    )

    assert report.gross_loss == 0.0
    assert report.profit_factor == float("inf")


def test_metrics_aggregator_uses_net_pnl_for_profit_buckets():
    report = MetricsAggregator().aggregate(
        [
            _trade(pnl=-1.0, result=TradeResult.WIN),
            _trade(pnl=5.0, result=TradeResult.LOSS),
        ]
    )

    assert report.winrate == 0.5
    assert report.gross_profit == 5.0
    assert report.gross_loss == 1.0


def test_report_writer_exports_grouped_json_and_html(tmp_path):
    report = build_report(
        symbol="BTC/USDT",
        timeframe="15m",
        mode="test",
        trades=[_trade(pnl=10.0, result=TradeResult.WIN)],
    )

    trades_path, summary_path, report_path, html_path = BacktestReportWriter(tmp_path).write(report)

    assert trades_path.exists()
    assert summary_path.exists()
    assert report_path.exists()
    assert html_path.exists()
    assert "by_market_regime" in summary_path.read_text(encoding="utf-8")
    html = html_path.read_text(encoding="utf-8")
    assert "By Market Regime" in html
    assert "By Signal Type" in html


def _trade(
    pnl: float,
    result: TradeResult,
    market_regime: str = "UPTREND",
    strategy: StrategyType = StrategyType.TREND_FOLLOWING,
    direction: SignalType = SignalType.BUY,
    confidence: float = 0.72,
    confidence_bucket_value: str | None = None,
    volatility_bucket_value: str = "NORMAL",
    holding_bars: int = 3,
) -> Trade:
    """Build a minimal closed trade for metric tests."""
    return Trade(
        symbol="BTC/USDT",
        timeframe="15m",
        direction=direction,
        strategy=strategy,
        opened_at="2026-01-01T00:00:00",
        closed_at="2026-01-01T00:45:00",
        entry=100.0,
        stop_loss=90.0,
        take_profit_1=115.0,
        take_profit_2=120.0,
        exit_price=120.0 if pnl >= 0 else 90.0,
        position_size=1.0,
        gross_pnl=pnl,
        fees=0.0,
        slippage=0.0,
        pnl=pnl,
        risk_reward=2.0,
        result=result,
        confidence=confidence,
        reasons=[],
        market_regime=market_regime,
        confidence_bucket=confidence_bucket_value or confidence_bucket(confidence),
        volatility_bucket=volatility_bucket_value,
        atr_percent=0.02,
        holding_bars=holding_bars,
    )
