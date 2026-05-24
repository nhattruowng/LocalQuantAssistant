"""Tests for causal candle, pullback, and range analysis."""

from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd

from price_action.candle_analyzer import CandleAnalyzer


def test_strong_body_scores_high() -> None:
    candles = _candles([100.0, 101.0, 102.0, 103.0])
    candles.loc[candles.index[-1], ["open", "high", "low", "close"]] = [
        100.0,
        110.0,
        99.0,
        109.0,
    ]

    analysis = CandleAnalyzer(range_window=4).analyze(candles)

    assert analysis.candle_body_strength >= 0.8
    assert analysis.candle_strength_score >= 0.75
    assert analysis.close_location_score >= 0.8


def test_large_wick_rejection_scores_high() -> None:
    candles = _candles([100.0, 100.5, 101.0, 101.2])
    candles.loc[candles.index[-1], ["open", "high", "low", "close"]] = [
        100.0,
        113.0,
        99.0,
        101.0,
    ]

    analysis = CandleAnalyzer(range_window=4).analyze(candles)

    assert analysis.rejection_wick_score >= 0.75
    assert any(item.name == "Rejection Wick" for item in analysis.evidence)


def test_price_far_from_ema_creates_chasing_penalty() -> None:
    candles = _candles([100.0, 101.0, 102.0, 120.0], ema=100.0, atr=5.0)

    analysis = CandleAnalyzer(range_window=4).analyze(candles)

    assert analysis.chasing_penalty >= 0.9
    assert any(item.name == "Chasing Penalty" for item in analysis.evidence)


def test_clean_range_scores_high() -> None:
    candles = _candles([100.0, 101.0, 100.5, 101.2, 100.8, 101.1], atr=1.0)

    analysis = CandleAnalyzer(range_window=6).analyze(candles)

    assert analysis.range_quality_score >= 0.75


def test_range_quality_low_when_tests_many_and_atr_expands() -> None:
    candles = _candles(
        [100.0, 101.0, 100.2, 101.1, 100.1, 101.2, 100.0, 101.3],
        atr=1.0,
    )
    candles.loc[:, "atr_14"] = [1.0, 1.0, 1.1, 1.2, 1.4, 1.7, 2.1, 2.6]
    candles.loc[:, "high"] = [102.0, 102.1, 102.0, 102.2, 102.1, 102.2, 102.0, 102.3]
    candles.loc[:, "low"] = [99.0, 99.1, 99.0, 99.1, 99.0, 99.1, 99.0, 99.1]

    analysis = CandleAnalyzer(range_window=8).analyze(candles)

    assert analysis.range_quality_score <= 0.55


def test_trend_exhaustion_detected() -> None:
    candles = _candles([100.0, 106.0, 114.0, 121.0], ema=100.0, atr=5.0)
    candles.loc[candles.index[-1], ["open", "high", "low", "close"]] = [
        114.0,
        130.0,
        113.0,
        121.0,
    ]

    analysis = CandleAnalyzer(range_window=4).analyze(candles)

    assert analysis.trend_exhaustion_score >= 0.55
    assert any(item.name == "Trend Exhaustion" for item in analysis.evidence)


def test_analyzer_accepts_list_candles_and_is_causal() -> None:
    analyzer = CandleAnalyzer(range_window=4)
    candles = _candles([100.0, 101.0, 102.0, 103.0, 150.0])
    decision_index = 3

    from_full = analyzer.analyze(candles.iloc[: decision_index + 1].to_dict("records"))
    from_truncated = analyzer.analyze(candles.iloc[: decision_index + 1])

    assert from_full.to_dict() == from_truncated.to_dict()


def _candles(
    closes: list[float],
    *,
    ema: float | None = None,
    atr: float = 2.0,
) -> pd.DataFrame:
    rows = len(closes)
    timestamps = pd.date_range(
        datetime(2026, 1, 1, tzinfo=UTC),
        periods=rows,
        freq="h",
    )
    opens = [close - 0.2 for close in closes]
    highs = [max(open_price, close) + 0.6 for open_price, close in zip(opens, closes, strict=False)]
    lows = [min(open_price, close) - 0.6 for open_price, close in zip(opens, closes, strict=False)]
    ema_value = closes[0] if ema is None else ema
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": [1_000.0] * rows,
            "ema_20": [ema_value] * rows,
            "atr_14": [atr] * rows,
        }
    )
