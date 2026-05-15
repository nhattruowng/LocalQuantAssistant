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
    assert report.winrate == 1.0


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


def test_backtester_calculates_buy_pnl_after_costs():
    settings = load_settings()
    report = Backtester(settings).run(
        features=_features(future_high=131.0, future_low=99.0),
        symbol="BTC/USDT",
        timeframe="15m",
        probability_provider=AlwaysBuyProvider(),
    )
    trade = report.trades[0]
    entry_raw = 100.0
    exit_raw = 130.0
    position_size = (
        settings.risk.account_balance
        * settings.risk.risk_per_trade_pct
        / (10.0 * settings.risk.stop_loss_atr_multiplier)
    )
    expected_entry = entry_raw * (1.0 + settings.backtest.slippage_rate)
    expected_exit = exit_raw * (1.0 - settings.backtest.slippage_rate)
    expected_gross = (expected_exit - expected_entry) * position_size
    expected_fees = (
        abs(expected_entry * position_size) * settings.backtest.fee_rate
        + abs(expected_exit * position_size) * settings.backtest.fee_rate
    )

    assert trade.position_size == pytest.approx(position_size)
    assert trade.gross_pnl == pytest.approx(expected_gross)
    assert trade.pnl == pytest.approx(expected_gross - expected_fees)
    assert report.net_profit == pytest.approx(trade.pnl)


def test_backtester_does_not_open_overlapping_positions():
    report = Backtester(load_settings()).run(
        features=_features_from_bars(
            highs=[101.0, 101.0, 131.0, 101.0, 131.0],
            lows=[99.0, 99.0, 99.0, 99.0, 99.0],
        ),
        symbol="BTC/USDT",
        timeframe="15m",
        probability_provider=AlwaysBuyProvider(),
    )
    timestamps = list(pd.date_range(datetime(2026, 1, 1, tzinfo=UTC), periods=5, freq="h"))

    assert report.total_trades == 2
    assert [trade.opened_at for trade in report.trades] == [timestamps[0], timestamps[3]]
    assert report.trades[0].closed_at == timestamps[2]


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


def _features_from_bars(highs: list[float], lows: list[float]) -> pd.DataFrame:
    """Build deterministic backtest features from future high/low paths."""
    rows = len(highs)
    timestamps = pd.date_range(datetime(2026, 1, 1, tzinfo=UTC), periods=rows, freq="h")
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": [100.0] * rows,
            "high": highs,
            "low": lows,
            "close": [100.0] * rows,
            "volume": [1_000.0] * rows,
            "market_regime": ["UPTREND"] * rows,
            "atr_14": [10.0] * rows,
            "ema_20": [99.0] * rows,
            "ema_50": [95.0] * rows,
            "rsi_14": [55.0] * rows,
            "volume_ratio": [1.3] * rows,
            "rolling_high_20": [120.0] * rows,
            "rolling_low_20": [80.0] * rows,
            "trend_score": [1.0] * rows,
        }
    )
