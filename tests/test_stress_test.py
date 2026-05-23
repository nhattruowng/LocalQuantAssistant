"""Tests for backtest stress-test scenario reporting."""

from __future__ import annotations

from pathlib import Path

from backtest.metrics import build_report
from backtest.models import Trade, TradeResult
from backtest.stress_test import BacktestStressTester
from signals.models import SignalType, StrategyType


class FakeBacktester:
    """Minimal backtester stub returning deterministic scenario reports."""

    def run_cost_scenarios(self, **kwargs):
        return {
            "zero_slippage_baseline": build_report(
                symbol="BTC/USDT",
                timeframe="15m",
                mode="baseline",
                trades=[_trade(10.0)],
            ),
            "normal": build_report(
                symbol="BTC/USDT",
                timeframe="15m",
                mode="normal",
                trades=[_trade(8.0)],
            ),
            "high_slippage": build_report(
                symbol="BTC/USDT",
                timeframe="15m",
                mode="high_slippage",
                trades=[_trade(6.0)],
            ),
            "stress": build_report(
                symbol="BTC/USDT",
                timeframe="15m",
                mode="stress",
                trades=[_trade(4.0)],
            ),
        }


def test_stress_tester_builds_ordered_scenario_report() -> None:
    report = BacktestStressTester().run(
        backtester=FakeBacktester(),
        features=None,  # not used by fake runner
        symbol="BTC/USDT",
        timeframe="15m",
        probability_provider=None,  # not used by fake runner
    )

    assert [item.scenario for item in report.scenarios] == [
        "zero_slippage_baseline",
        "normal",
        "high_slippage",
        "stress",
    ]
    assert report.scenarios[-1].net_profit <= report.scenarios[0].net_profit


def test_stress_tester_writes_json_csv_html() -> None:
    output_dir = Path("data/backtest/test_stress_outputs")
    tester = BacktestStressTester(output_dir=output_dir)
    report = tester.run(
        backtester=FakeBacktester(),
        features=None,
        symbol="BTC/USDT",
        timeframe="15m",
        probability_provider=None,
    )

    paths = tester.write(report)
    assert paths["json"].exists()
    assert paths["csv"].exists()
    assert paths["html"].exists()


def _trade(pnl: float) -> Trade:
    return Trade(
        symbol="BTC/USDT",
        timeframe="15m",
        direction=SignalType.BUY,
        strategy=StrategyType.TREND_FOLLOWING,
        opened_at="2026-01-01T00:00:00Z",
        closed_at="2026-01-01T01:00:00Z",
        entry=100.0,
        stop_loss=95.0,
        take_profit_1=105.0,
        take_profit_2=110.0,
        exit_price=110.0,
        position_size=1.0,
        gross_pnl=pnl,
        fees=0.0,
        slippage=0.0,
        pnl=pnl,
        risk_reward=2.0,
        result=TradeResult.WIN if pnl > 0 else TradeResult.LOSS if pnl < 0 else TradeResult.BREAKEVEN,
        confidence=0.75,
        reasons=[],
    )
