"""Tests for TP/SL first-touch labeling."""

from __future__ import annotations

import pandas as pd

from config.settings import LabelingSettings
from domain.enums import TradingAction
from labeling.label_generator import LabelGenerator


def test_label_generator_marks_buy_when_buy_tp_touches_first():
    generator = LabelGenerator(_settings())
    features = _base_features()
    features.loc[1, "high"] = 106.5

    labeled = generator.generate(features)

    assert labeled.loc[0, "label"] == TradingAction.BUY.value


def test_label_generator_marks_sell_when_sell_tp_touches_first():
    generator = LabelGenerator(_settings())
    features = _base_features()
    features.loc[1, "low"] = 93.5

    labeled = generator.generate(features)

    assert labeled.loc[0, "label"] == TradingAction.SELL.value


def test_label_generator_marks_wait_when_stop_touches_first():
    generator = LabelGenerator(_settings())
    features = _base_features()
    features.loc[1, "low"] = 96.5

    labeled = generator.generate(features)

    assert labeled.loc[0, "label"] == TradingAction.WAIT.value


def test_label_generator_does_not_mutate_input():
    generator = LabelGenerator(_settings())
    features = _base_features()
    expected = features.copy(deep=True)

    generator.generate(features)

    pd.testing.assert_frame_equal(features, expected)


def _settings() -> LabelingSettings:
    """Return compact first-touch settings for tests."""
    return LabelingSettings(
        lookahead_bars=3,
        stop_loss_atr_multiplier=1.5,
        take_profit_atr_multiplier=3.0,
    )


def _base_features() -> pd.DataFrame:
    """Build minimal feature data for label tests."""
    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-01-01", periods=5, freq="h", tz="UTC"),
            "open": [100.0] * 5,
            "high": [101.0] * 5,
            "low": [99.0] * 5,
            "close": [100.0] * 5,
            "volume": [1_000.0] * 5,
            "atr_14": [2.0] * 5,
        }
    )
