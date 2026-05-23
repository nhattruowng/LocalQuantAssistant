"""Tests for causal price action analyzers."""

from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd

from price_action.candle_analyzer import CandleAnalyzer
from price_action.structure_analyzer import StructureAnalyzer
from price_action.swing_detector import SwingDetector


def test_uptrend_hh_hl_detected() -> None:
    analyzer = _analyzer()
    candles = _candles_from_close([100, 103, 101, 105, 103, 107, 105])

    context = analyzer.analyze(candles)

    assert context.structure == "HH_HL"


def test_downtrend_lh_ll_detected() -> None:
    analyzer = _analyzer()
    candles = _candles_from_close([108, 104, 106, 102, 104, 100, 102])

    context = analyzer.analyze(candles)

    assert context.structure == "LH_LL"


def test_bos_detected() -> None:
    analyzer = _analyzer()
    candles = _candles_from_close([100, 103, 101, 105, 103, 106, 109])

    context = analyzer.analyze(candles)

    assert context.bos_detected is True
    assert context.choch_detected is False


def test_choch_detected() -> None:
    analyzer = _analyzer()
    candles = _candles_from_close([110, 106, 108, 104, 106, 102, 111])

    context = analyzer.analyze(candles)

    assert context.choch_detected is True
    assert context.bos_detected is False


def test_large_rejection_wick_scores_high() -> None:
    analyzer = _analyzer()
    candles = _candles_from_close([100, 100, 100, 100, 101])
    candles.loc[candles.index[-1], ["open", "high", "low", "close"]] = [100.0, 112.0, 99.0, 101.0]

    context = analyzer.analyze(candles)

    assert context.rejection_wick_score >= 0.7


def test_chasing_penalty_high_when_price_far_from_ema_atr() -> None:
    analyzer = _analyzer()
    candles = _candles_from_close([100, 100, 100, 100, 120], atr=5.0, ema=100.0)

    context = analyzer.analyze(candles)

    assert context.chasing_penalty >= 0.9


def test_analyzer_is_strictly_causal() -> None:
    analyzer = _analyzer()
    candles = _candles_from_close(
        [100, 101, 100.5, 102, 101.2, 103, 102.1, 104, 103.4, 105, 104.2, 106, 105.1]
    )
    check_index = 9

    from_full = analyzer.analyze_at(candles, index=check_index)
    from_truncated = analyzer.analyze(candles.iloc[: check_index + 1])

    assert from_full.to_dict() == from_truncated.to_dict()


def _analyzer() -> StructureAnalyzer:
    return StructureAnalyzer(
        swing_detector=SwingDetector(lookback=2, min_separation=1),
        candle_analyzer=CandleAnalyzer(range_window=5),
    )


def _candles_from_close(
    closes: list[float],
    atr: float = 2.0,
    ema: float | None = None,
) -> pd.DataFrame:
    rows = len(closes)
    timestamps = pd.date_range(
        datetime(2026, 1, 1, tzinfo=UTC),
        periods=rows,
        freq="h",
    )
    open_prices: list[float] = []
    for index, close in enumerate(closes):
        if index == 0:
            open_prices.append(close - 0.2)
        else:
            open_prices.append(closes[index - 1])
    highs = [max(open_price, close) + 1.0 for open_price, close in zip(open_prices, closes, strict=False)]
    lows = [min(open_price, close) - 1.0 for open_price, close in zip(open_prices, closes, strict=False)]
    ema_value = closes[0] if ema is None else ema
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": open_prices,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": [1_000.0] * rows,
            "ema_20": [ema_value] * rows,
            "atr_14": [atr] * rows,
        }
    )

