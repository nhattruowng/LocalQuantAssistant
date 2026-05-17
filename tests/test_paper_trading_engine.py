"""Tests for paper trading simulation."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from config.settings import DatabaseSettings, PaperTradingSettings
from database.connection import create_database
from paper.paper_trading_engine import PaperTradingEngine
from signals.models import SignalType, StrategyType, TradeSetup


def test_paper_trading_engine_opens_buy_trade(tmp_path):
    database = create_database(DatabaseSettings(driver="sqlite", path=tmp_path / "app.db"))
    database.initialize()
    engine = PaperTradingEngine(database, _settings())

    account = engine.process_setup(_setup(SignalType.BUY), _candle(high=101.0, low=99.0))
    database.close()

    assert len(account.open_positions) == 1
    assert account.open_positions[0].direction == "BUY"
    assert account.current_balance == pytest.approx(10_000.0)


def test_paper_trading_engine_closes_buy_on_take_profit(tmp_path):
    database = create_database(DatabaseSettings(driver="sqlite", path=tmp_path / "app.db"))
    database.initialize()
    engine = PaperTradingEngine(database, _settings())

    engine.process_setup(_setup(SignalType.BUY), _candle(high=101.0, low=99.0))
    closed = engine.update_positions(_candle(high=116.0, low=100.0))
    account = engine.load_account(mark_price=115.0)
    database.close()

    assert len(closed) == 1
    assert closed[0].result == "WIN"
    assert closed[0].pnl == pytest.approx(15.0)
    assert account.current_balance == pytest.approx(10_015.0)
    assert len(account.open_positions) == 0
    assert len(account.closed_trades) == 1


def test_paper_trading_engine_closes_sell_on_stop_loss(tmp_path):
    database = create_database(DatabaseSettings(driver="sqlite", path=tmp_path / "app.db"))
    database.initialize()
    engine = PaperTradingEngine(database, _settings())

    engine.process_setup(_setup(SignalType.SELL), _candle(high=101.0, low=99.0))
    closed = engine.update_positions(_candle(high=106.0, low=99.0))
    account = engine.load_account(mark_price=105.0)
    database.close()

    assert len(closed) == 1
    assert closed[0].result == "LOSS"
    assert closed[0].pnl == pytest.approx(-5.0)
    assert account.current_balance == pytest.approx(9_995.0)


def test_paper_trading_engine_does_not_open_second_position(tmp_path):
    database = create_database(DatabaseSettings(driver="sqlite", path=tmp_path / "app.db"))
    database.initialize()
    engine = PaperTradingEngine(database, _settings())

    engine.process_setup(_setup(SignalType.BUY), _candle(high=101.0, low=99.0))
    account = engine.process_setup(_setup(SignalType.BUY), _candle(high=102.0, low=100.0))
    database.close()

    assert len(account.open_positions) == 1


def _settings() -> PaperTradingSettings:
    """Return enabled paper trading settings."""
    return PaperTradingSettings(enabled=True, initial_balance=10_000.0)


def _setup(signal: SignalType) -> TradeSetup:
    """Build an actionable setup for paper tests."""
    return TradeSetup(
        symbol="BTC/USDT",
        timeframe="15m",
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        market_regime="UPTREND",
        signal=signal,
        strategy=StrategyType.TREND_FOLLOWING,
        confidence=0.75,
        entry=100.0,
        stop_loss=95.0 if signal is SignalType.BUY else 105.0,
        take_profit_1=110.0 if signal is SignalType.BUY else 90.0,
        take_profit_2=115.0 if signal is SignalType.BUY else 85.0,
        risk_reward=3.0,
        position_size=1.0,
        reasons=["test"],
        risk_notes=[],
    )


def _candle(high: float, low: float) -> dict[str, object]:
    """Build a candle mapping for paper tests."""
    return {
        "timestamp": datetime(2026, 1, 1, tzinfo=UTC),
        "high": high,
        "low": low,
        "close": 100.0,
    }
