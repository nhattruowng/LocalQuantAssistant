"""Tests for rule-based market regime detection."""

from __future__ import annotations

from dataclasses import replace

import pandas as pd

from config.loader import load_settings
from config.settings import MarketRegimeSettings
from regime.market_regime import MarketRegime
from regime.regime_detector import MarketRegimeDetector


def test_detects_uptrend():
    detector = MarketRegimeDetector(_settings_without_volatility_filter())
    features = _base_features()
    features.loc[features.index[-1], ["close", "ema_20", "ema_50", "ema_20_slope"]] = [
        110.0,
        105.0,
        100.0,
        0.5,
    ]

    result = detector.detect(features)

    assert result["market_regime"].iloc[-1] == MarketRegime.UPTREND.value


def test_detects_downtrend():
    detector = MarketRegimeDetector(_settings_without_volatility_filter())
    features = _base_features()
    features.loc[features.index[-1], ["close", "ema_20", "ema_50", "ema_20_slope"]] = [
        90.0,
        95.0,
        100.0,
        -0.5,
    ]

    result = detector.detect(features)

    assert result["market_regime"].iloc[-1] == MarketRegime.DOWNTREND.value


def test_detects_sideway():
    detector = MarketRegimeDetector(_settings_without_volatility_filter())
    features = _base_features()
    features.loc[features.index[-1], ["close", "ema_20", "ema_50", "ema_20_slope"]] = [
        100.0,
        100.1,
        99.9,
        0.0,
    ]
    features.loc[features.index[-1], ["bollinger_width", "atr_percent"]] = [0.02, 0.01]

    result = detector.detect(features)

    assert result["market_regime"].iloc[-1] == MarketRegime.SIDEWAY.value


def test_detects_breakout_up():
    detector = MarketRegimeDetector(_default_settings())
    features = _base_features()
    features.loc[features.index[-1], ["close", "high", "volume_ratio", "atr_percent"]] = [
        130.0,
        131.0,
        2.0,
        0.03,
    ]

    result = detector.detect(features)

    assert result["market_regime"].iloc[-1] == MarketRegime.BREAKOUT_UP.value
    assert result["breakout_score"].iloc[-1] > 0


def test_detects_breakout_down():
    detector = MarketRegimeDetector(_default_settings())
    features = _base_features()
    features.loc[features.index[-1], ["close", "low", "volume_ratio", "atr_percent"]] = [
        70.0,
        69.0,
        2.0,
        0.03,
    ]

    result = detector.detect(features)

    assert result["market_regime"].iloc[-1] == MarketRegime.BREAKOUT_DOWN.value
    assert result["breakout_score"].iloc[-1] > 0


def test_detects_high_volatility():
    detector = MarketRegimeDetector(_default_settings())
    features = _base_features()
    features["atr_percent"] = [0.01] * (len(features) - 1) + [0.08]

    result = detector.detect(features)

    assert result["market_regime"].iloc[-1] == MarketRegime.HIGH_VOLATILITY.value


def test_detects_low_volatility():
    detector = MarketRegimeDetector(_default_settings())
    features = _base_features()
    features["atr_percent"] = [0.08] * (len(features) - 1) + [0.005]

    result = detector.detect(features)

    assert result["market_regime"].iloc[-1] == MarketRegime.LOW_VOLATILITY.value


def test_detects_unknown_when_indicators_missing():
    detector = MarketRegimeDetector(_default_settings())
    features = _base_features()
    features.loc[features.index[-1], "ema_20"] = None

    result = detector.detect(features)

    assert result["market_regime"].iloc[-1] == MarketRegime.UNKNOWN.value


def _default_settings() -> MarketRegimeSettings:
    """Return default regime settings for detector tests."""
    return load_settings().market_regime


def _settings_without_volatility_filter() -> MarketRegimeSettings:
    """Disable volatility percentile classification for directional tests."""
    settings = _default_settings()
    return replace(
        settings,
        high_volatility_percentile=1.1,
        low_volatility_percentile=-0.1,
    )


def _base_features(rows: int = 40) -> pd.DataFrame:
    """Build feature-like rows with stable non-breakout market structure."""
    timestamps = pd.date_range("2026-01-01", periods=rows, freq="h", tz="UTC")
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": [100.0] * rows,
            "high": [102.0] * rows,
            "low": [98.0] * rows,
            "close": [100.0] * rows,
            "volume": [1_000.0] * rows,
            "ema_20": [101.0] * rows,
            "ema_50": [99.0] * rows,
            "ema_20_slope": [0.1] * rows,
            "bollinger_width": [0.05] * rows,
            "atr_percent": [0.02] * rows,
            "volume_ratio": [1.0] * rows,
        }
    )
