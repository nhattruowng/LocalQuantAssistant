"""Tests for the OHLCV data quality gate."""

from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd

from data.data_quality import (
    DataQualityAction,
    DataQualityGate,
    DataQualitySeverity,
)


def test_clean_data_passes_true() -> None:
    candles = _candles(20)

    report = DataQualityGate().evaluate(candles, timeframe="15m")

    assert report.passed is True
    assert report.score == 1.0
    assert report.issues == []
    assert report.severity is DataQualitySeverity.LOW
    assert report.recommended_action is DataQualityAction.CONTINUE


def test_missing_candle_detected_without_mutating_source() -> None:
    candles = _candles(6).drop(index=2).reset_index(drop=True)
    original = candles.copy(deep=True)

    report = DataQualityGate().evaluate(candles, timeframe="15m")

    assert any("Missing candles detected" in issue for issue in report.issues)
    assert candles.equals(original)


def test_duplicate_timestamp_detected() -> None:
    candles = _candles(6)
    candles.loc[3, "timestamp"] = candles.loc[2, "timestamp"]

    report = DataQualityGate().evaluate(candles, timeframe="15m")

    assert report.severity is DataQualitySeverity.HIGH
    assert any("Duplicated timestamp" in issue for issue in report.issues)


def test_ohlc_invalid_detected() -> None:
    candles = _candles(6)
    candles.loc[2, "high"] = 90.0
    candles.loc[2, "low"] = 100.0

    report = DataQualityGate().evaluate(candles, timeframe="15m")

    assert report.severity is DataQualitySeverity.HIGH
    assert any("OHLC invalid" in issue for issue in report.issues)


def test_negative_or_null_volume_detected() -> None:
    candles = _candles(6)
    candles.loc[2, "volume"] = -1.0

    report = DataQualityGate().evaluate(candles, timeframe="15m")

    assert report.severity is DataQualitySeverity.HIGH
    assert any("Negative volume" in issue for issue in report.issues)


def test_outlier_volume_detected() -> None:
    candles = _candles(10)
    candles.loc[6, "volume"] = 10_000.0

    report = DataQualityGate().evaluate(candles, timeframe="15m")

    assert report.severity is DataQualitySeverity.MEDIUM
    assert report.recommended_action is DataQualityAction.WARN
    assert any("Outlier volume" in issue for issue in report.issues)


def test_high_severity_recommends_block() -> None:
    candles = _candles(6)
    candles.loc[2, "close"] = 160.0
    candles.loc[2, "high"] = 161.0

    report = DataQualityGate().evaluate(candles, timeframe="15m")

    assert report.severity is DataQualitySeverity.HIGH
    assert report.recommended_action is DataQualityAction.BLOCK
    assert report.passed is False


def test_evaluate_at_uses_only_past_and_current_candles() -> None:
    candles = _candles(8)
    candles.loc[7, "timestamp"] = candles.loc[6, "timestamp"]

    report = DataQualityGate().evaluate_at(candles, index=5, timeframe="15m")

    assert report.passed is True
    assert not any("Duplicated timestamp" in issue for issue in report.issues)


def _candles(rows: int) -> pd.DataFrame:
    timestamps = pd.date_range(
        datetime(2026, 1, 1, tzinfo=UTC),
        periods=rows,
        freq="15min",
    )
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": [100.0] * rows,
            "high": [102.0] * rows,
            "low": [99.0] * rows,
            "close": [101.0] * rows,
            "volume": [1_000.0] * rows,
        }
    )
