"""Tests for signal engine decisions."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

from config.loader import load_settings
from config.settings import Settings
from regime.market_regime import MarketRegime
from signal.models import SignalType, StrategyType
from signal.signal_engine import SignalEngine


def test_signal_engine_generates_trend_following_buy():
    engine = SignalEngine(load_settings())

    setup = engine.generate(
        symbol="BTC/USDT",
        timeframe="15m",
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        market_regime=MarketRegime.UPTREND,
        features={
            **_base_features(),
            "close": 101.0,
            "ema_20": 100.0,
            "ema_50": 95.0,
            "rsi_14": 55.0,
        },
        probabilities={"BUY": 0.70, "SELL": 0.10, "WAIT": 0.20},
    )

    assert setup.signal is SignalType.BUY
    assert setup.strategy is StrategyType.TREND_FOLLOWING
    assert setup.risk_reward == 2.0
    assert setup.position_size is not None
    assert setup.confidence > 0.0


def test_signal_engine_generates_trend_following_sell():
    engine = SignalEngine(load_settings())

    setup = engine.generate(
        symbol="BTC/USDT",
        timeframe="15m",
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        market_regime=MarketRegime.DOWNTREND,
        features={
            **_base_features(),
            "close": 99.0,
            "ema_20": 100.0,
            "ema_50": 105.0,
            "rsi_14": 45.0,
        },
        probabilities={"BUY": 0.10, "SELL": 0.70, "WAIT": 0.20},
    )

    assert setup.signal is SignalType.SELL
    assert setup.strategy is StrategyType.TREND_FOLLOWING
    assert setup.stop_loss is not None
    assert setup.stop_loss > setup.entry
    assert setup.take_profit_2 < setup.entry


def test_signal_engine_returns_wait_when_probability_is_low():
    engine = SignalEngine(load_settings())

    setup = engine.generate(
        symbol="BTC/USDT",
        timeframe="15m",
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        market_regime=MarketRegime.UPTREND,
        features={
            **_base_features(),
            "close": 101.0,
            "ema_20": 100.0,
            "ema_50": 95.0,
            "rsi_14": 55.0,
        },
        probabilities={"BUY": 0.50, "SELL": 0.10, "WAIT": 0.40},
    )

    assert setup.signal is SignalType.WAIT
    assert setup.entry is None
    assert any("probability" in reason for reason in setup.reasons)


def test_signal_engine_returns_wait_when_risk_reward_is_too_low(
    settings: Settings,
    trend_buy_features: dict[str, float],
):
    strict_settings = replace(
        settings,
        signal=replace(settings.signal, min_risk_reward=3.0),
    )
    engine = SignalEngine(strict_settings)

    setup = engine.generate(
        symbol="BTC/USDT",
        timeframe="15m",
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        market_regime=MarketRegime.UPTREND,
        features=trend_buy_features,
        probabilities={"BUY": 0.70, "SELL": 0.10, "WAIT": 0.20},
    )

    assert setup.signal is SignalType.WAIT
    assert setup.risk_reward == 2.0
    assert any("Risk/reward" in reason for reason in setup.reasons)


def _base_features() -> dict[str, float]:
    """Return common technical feature values for signal tests."""
    return {
        "atr_14": 10.0,
        "volume_ratio": 1.3,
        "rolling_high_20": 120.0,
        "rolling_low_20": 80.0,
        "trend_score": 1.0,
    }
