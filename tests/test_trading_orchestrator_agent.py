"""Tests for the trading orchestrator pipeline."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

from agents.trading_orchestrator_agent import TradingOrchestratorAgent
from config.loader import load_settings
from config.settings import SignalSettings
from domain.entities import OHLCVBar
from domain.enums import TradingAction


def test_trading_orchestrator_returns_complete_buy_setup():
    settings = load_settings()
    orchestrator = TradingOrchestratorAgent(settings)

    trade_setup = orchestrator.analyze("BTCUSDT", _uptrend_bars(settings.data.min_bars))

    assert trade_setup.symbol == "BTCUSDT"
    assert trade_setup.action is TradingAction.BUY
    assert trade_setup.risk_plan is not None
    assert trade_setup.explanation
    assert any("Final action approved" in reason for reason in trade_setup.reasons)


def test_trading_orchestrator_blocks_low_risk_reward():
    settings = load_settings()
    settings = replace(
        settings,
        signal=SignalSettings(min_confidence=0.55, min_risk_reward=3.0),
    )
    orchestrator = TradingOrchestratorAgent(settings)

    trade_setup = orchestrator.analyze("BTCUSDT", _uptrend_bars(settings.data.min_bars))

    assert trade_setup.action is TradingAction.WAIT
    assert trade_setup.risk_plan is None
    assert any("risk/reward is below threshold" in reason for reason in trade_setup.reasons)


def _uptrend_bars(count: int) -> list[OHLCVBar]:
    """Build deterministic uptrend OHLCV bars for tests."""
    start = datetime(2026, 1, 1, tzinfo=UTC)
    bars: list[OHLCVBar] = []
    for index in range(count):
        close = 100.0 + index * 0.5
        open_price = close - 0.2
        bars.append(
            OHLCVBar(
                timestamp=start + timedelta(minutes=index),
                open=open_price,
                high=close + 0.1,
                low=open_price - 0.1,
                close=close,
                volume=1_000.0 + index,
            )
        )
    return bars
