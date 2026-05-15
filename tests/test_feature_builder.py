"""Tests for feature engineering."""

from __future__ import annotations

import pandas as pd
import pandas.testing as pdt

from config.loader import load_settings
from features.feature_builder import ALL_FEATURE_COLUMNS, FeatureBuilder


def test_feature_builder_outputs_required_columns():
    builder = FeatureBuilder(load_settings().feature_toggles)
    features = builder.build(_candles(260))

    missing = [column for column in ALL_FEATURE_COLUMNS if column not in features]

    assert not missing


def test_feature_builder_does_not_mutate_raw_input():
    builder = FeatureBuilder(load_settings().feature_toggles)
    raw = _candles(260)
    expected = raw.copy(deep=True)

    builder.build(raw)

    pdt.assert_frame_equal(raw, expected)


def test_feature_builder_does_not_leak_future_data():
    builder = FeatureBuilder(load_settings().feature_toggles)
    raw = _candles(260)
    check_index = 220

    full_features = builder.build(raw)
    truncated_features = builder.build(raw.iloc[: check_index + 1])

    pdt.assert_series_equal(
        full_features.loc[check_index, ALL_FEATURE_COLUMNS],
        truncated_features.loc[check_index, ALL_FEATURE_COLUMNS],
        check_names=False,
    )


def test_feature_builder_can_drop_warmup_rows():
    builder = FeatureBuilder(load_settings().feature_toggles)

    features = builder.build(_candles(260), drop_warmup_rows=True)

    assert not features[ALL_FEATURE_COLUMNS].isna().any().any()


def _candles(rows: int) -> pd.DataFrame:
    """Build deterministic candle data for feature tests."""
    timestamps = pd.date_range("2026-01-01", periods=rows, freq="h", tz="UTC")
    index = pd.Series(range(rows), dtype="float64")
    close = 100.0 + index * 0.2 + ((index % 7) * 0.03)
    open_price = close - 0.1
    high = close + 0.4
    low = open_price - 0.3
    volume = 1_000.0 + index * 2.0
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }
    )
