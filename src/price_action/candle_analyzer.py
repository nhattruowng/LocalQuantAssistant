"""Causal candle and range quality analysis."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import pandas as pd


@dataclass(frozen=True)
class CandleAnalysis:
    """Score payload computed from candles up to the current close."""

    candle_strength_score: float
    rejection_wick_score: float
    range_quality_score: float
    chasing_penalty: float


class CandleAnalyzer:
    """Compute causal candle-level quality scores."""

    def __init__(
        self,
        range_window: int = 20,
        ema_column: str = "ema_20",
        atr_column: str = "atr_14",
    ) -> None:
        self._range_window = max(3, int(range_window))
        self._ema_column = ema_column
        self._atr_column = atr_column

    def analyze(self, candles: pd.DataFrame) -> CandleAnalysis:
        """Analyze candle quality using only provided historical candles."""
        _validate_candles(candles)
        row = candles.iloc[-1]
        open_price = _as_float(row.get("open"), 0.0)
        close = _as_float(row.get("close"), open_price)
        high = _as_float(row.get("high"), max(open_price, close))
        low = _as_float(row.get("low"), min(open_price, close))
        candle_range = max(high - low, 1e-9)
        body = abs(close - open_price)
        upper_wick = max(0.0, high - max(open_price, close))
        lower_wick = max(0.0, min(open_price, close) - low)

        candle_strength = _clip(body / candle_range)
        rejection_wick = _clip(max(upper_wick, lower_wick) / candle_range)
        range_quality = self._range_quality(candles)
        chasing_penalty = self._chasing_penalty(candles, close)
        return CandleAnalysis(
            candle_strength_score=round(candle_strength, 4),
            rejection_wick_score=round(rejection_wick, 4),
            range_quality_score=round(range_quality, 4),
            chasing_penalty=round(chasing_penalty, 4),
        )

    def _range_quality(self, candles: pd.DataFrame) -> float:
        window = candles.iloc[-self._range_window :]
        high = float(window["high"].max())
        low = float(window["low"].min())
        span = max(high - low, 1e-9)
        atr = _atr_value(window, self._atr_column)
        span_in_atr = span / max(atr, 1e-9)
        # Compact multi-candle span => cleaner range, very large span => poor range.
        return _clip(1.0 - max(0.0, (span_in_atr - 6.0) / 12.0))

    def _chasing_penalty(self, candles: pd.DataFrame, close: float) -> float:
        row = candles.iloc[-1]
        ema = _as_float(row.get(self._ema_column), close)
        atr = _atr_value(candles.iloc[-self._range_window :], self._atr_column)
        atr_distance = abs(close - ema) / max(atr, 1e-9)
        # No penalty within ~1 ATR from EMA; grows quickly after that.
        return _clip(max(0.0, (atr_distance - 1.0) / 2.0))


def _validate_candles(candles: pd.DataFrame) -> None:
    required = {"open", "high", "low", "close"}
    missing = [column for column in required if column not in candles]
    if missing:
        raise ValueError(f"Candle DataFrame is missing columns: {missing}.")
    if candles.empty:
        raise ValueError("Candle DataFrame must not be empty.")


def _atr_value(candles: pd.DataFrame, atr_column: str) -> float:
    if atr_column in candles:
        series = candles[atr_column].dropna()
        if not series.empty:
            return max(float(series.iloc[-1]), 1e-9)
    # Fallback ATR approximation from mean candle range (causal).
    return max(float((candles["high"] - candles["low"]).mean()), 1e-9)


def _as_float(value: object, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clip(value: float) -> float:
    return max(0.0, min(float(value), 1.0))

