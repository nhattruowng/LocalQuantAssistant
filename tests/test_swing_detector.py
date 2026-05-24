"""Tests for confirmed causal swing detection."""

from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd

from price_action.swing_detector import SwingDetector, SwingType


def test_detect_swing_high() -> None:
    detector = SwingDetector(left_bars=2, confirmation_bars=1)
    candles = _candles(
        highs=[100.0, 102.0, 108.0, 103.0, 101.0],
        lows=[95.0, 96.0, 97.0, 96.5, 96.0],
    )

    result = detector.detect_report(candles)

    assert len(result.swing_highs) == 1
    assert result.latest_swing_high is not None
    assert result.latest_swing_high.index == 2
    assert result.latest_swing_high.price == 108.0
    assert result.latest_swing_high.swing_type is SwingType.HIGH
    assert result.latest_swing_high.confirmed_index == 3


def test_detect_swing_low() -> None:
    detector = SwingDetector(left_bars=2, confirmation_bars=1)
    candles = _candles(
        highs=[106.0, 105.0, 104.0, 105.5, 107.0],
        lows=[100.0, 98.0, 92.0, 97.0, 99.0],
    )

    result = detector.detect_report(candles)

    assert len(result.swing_lows) == 1
    assert result.latest_swing_low is not None
    assert result.latest_swing_low.index == 2
    assert result.latest_swing_low.price == 92.0
    assert result.latest_swing_low.swing_type is SwingType.LOW
    assert result.latest_swing_low.confirmed_index == 3


def test_detector_is_strictly_causal() -> None:
    detector = SwingDetector(left_bars=2, confirmation_bars=1)
    candles = _candles(
        highs=[100.0, 102.0, 108.0, 103.0, 101.0, 120.0, 99.0],
        lows=[95.0, 96.0, 97.0, 96.5, 96.0, 95.0, 94.0],
    )
    decision_index = 3

    from_full = detector.detect_report_at(candles, index=decision_index)
    from_truncated = detector.detect_report(candles.iloc[: decision_index + 1])

    assert from_full.to_dict() == from_truncated.to_dict()
    assert from_full.latest_swing_high is not None
    assert from_full.latest_swing_high.price == 108.0
    assert all(point.index <= decision_index for point in from_full.swing_highs)


def test_confirmation_requires_closed_candle_after_candidate() -> None:
    detector = SwingDetector(left_bars=2, confirmation_bars=1)
    candles = _candles(
        highs=[100.0, 102.0, 108.0],
        lows=[95.0, 96.0, 97.0],
    )

    result = detector.detect_report(candles)

    assert result.swing_highs == []
    assert result.latest_swing_high is None


def test_detector_does_not_crash_with_little_data() -> None:
    detector = SwingDetector(left_bars=3, confirmation_bars=2)

    result = detector.detect_report(_candles(highs=[100.0], lows=[95.0]))

    assert result.swing_highs == []
    assert result.swing_lows == []
    assert result.latest_swing_high is None
    assert result.latest_swing_low is None


def test_detector_accepts_list_candles_and_applies_atr_distance() -> None:
    detector = SwingDetector(
        left_bars=1,
        confirmation_bars=1,
        min_swing_distance_atr=2.0,
    )
    candles = _candles(
        highs=[100.0, 105.0, 101.0, 106.0, 102.0],
        lows=[95.0, 96.0, 95.5, 96.5, 96.0],
        atr=1.0,
    ).to_dict("records")

    result = detector.detect_report(candles)

    assert [point.price for point in result.swing_highs] == [105.0]


def _candles(
    *,
    highs: list[float],
    lows: list[float],
    atr: float = 2.0,
) -> pd.DataFrame:
    rows = len(highs)
    timestamps = pd.date_range(
        datetime(2026, 1, 1, tzinfo=UTC),
        periods=rows,
        freq="h",
    )
    closes = [(high + low) / 2.0 for high, low in zip(highs, lows, strict=False)]
    opens = list(closes)
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": [1_000.0] * rows,
            "atr_14": [atr] * rows,
        }
    )
