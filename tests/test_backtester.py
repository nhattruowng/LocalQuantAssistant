"""Tests for the backtesting engine."""

from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd
import pytest

from backtest.backtester import Backtester
from backtest.metrics import calculate_max_drawdown
from backtest.models import TradeResult
from config.loader import load_settings


class AlwaysBuyProvider:
    """Fake probability provider that always supports BUY."""

    mode = "test"

    def predict_proba(self, row: pd.Series) -> dict[str, float]:
        return {"BUY": 0.70, "SELL": 0.10, "WAIT": 0.20}


def test_backtester_closes_buy_on_tp_hit():
    report = Backtester(load_settings()).run(
        features=_features(future_high=131.0, future_low=99.0),
        symbol="BTC/USDT",
        timeframe="15m",
        probability_provider=AlwaysBuyProvider(),
    )

    assert report.total_trades == 1
    assert report.trades[0].result is TradeResult.WIN
    assert report.trades[0].exit_price > report.trades[0].entry


def test_backtester_closes_buy_on_sl_hit():
    report = Backtester(load_settings()).run(
        features=_features(future_high=101.0, future_low=84.0),
        symbol="BTC/USDT",
        timeframe="15m",
        probability_provider=AlwaysBuyProvider(),
    )

    assert report.total_trades == 1
    assert report.trades[0].result is TradeResult.LOSS
    assert report.trades[0].exit_price < report.trades[0].entry


def test_backtester_uses_conservative_same_candle_sl_first():
    report = Backtester(load_settings()).run(
        features=_features(future_high=131.0, future_low=84.0),
        symbol="BTC/USDT",
        timeframe="15m",
        probability_provider=AlwaysBuyProvider(),
    )

    assert report.total_trades == 1
    assert report.trades[0].result is TradeResult.LOSS


def test_backtester_applies_fee_and_slippage():
    settings = load_settings()
    report = Backtester(settings).run(
        features=_features(future_high=131.0, future_low=99.0),
        symbol="BTC/USDT",
        timeframe="15m",
        probability_provider=AlwaysBuyProvider(),
    )
    trade = report.trades[0]

    assert trade.entry == pytest.approx(100.0 * (1.0 + settings.backtest.slippage_rate))
    assert trade.fees > 0.0
    assert trade.slippage > 0.0
    assert trade.pnl == pytest.approx(trade.gross_pnl - trade.fees)


def test_calculate_max_drawdown():
    assert calculate_max_drawdown([10.0, -5.0, -20.0, 15.0]) == 25.0


def _features(future_high: float, future_low: float) -> pd.DataFrame:
    """Build minimal feature rows that create one valid trend BUY setup."""
    timestamps = pd.date_range(datetime(2026, 1, 1, tzinfo=UTC), periods=3, freq="h")
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": [100.0, 100.0, 100.0],
            "high": [101.0, future_high, 101.0],
            "low": [99.0, future_low, 99.0],
            "close": [100.0, 100.0, 100.0],
            "volume": [1_000.0, 1_000.0, 1_000.0],
            "market_regime": ["UPTREND", "UPTREND", "UPTREND"],
            "atr_14": [10.0, 10.0, 10.0],
            "ema_20": [99.0, 99.0, 99.0],
            "ema_50": [95.0, 95.0, 95.0],
            "rsi_14": [55.0, 55.0, 55.0],
            "volume_ratio": [1.3, 1.3, 1.3],
            "rolling_high_20": [120.0, 120.0, 120.0],
            "rolling_low_20": [80.0, 80.0, 80.0],
            "trend_score": [1.0, 1.0, 1.0],
        }
    )
