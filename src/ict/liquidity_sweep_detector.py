"""Strictly-causal liquidity sweep detection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from price_action.swing_detector import SwingDetector, SwingType


@dataclass(frozen=True)
class LiquiditySweepResult:
    """Liquidity sweep detection output."""

    detected: bool
    direction: str
    level: float | None
    swept_type: str
    rejection_score: float
    volume_confirmed: bool
    warning: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "detected": self.detected,
            "direction": self.direction,
            "level": self.level,
            "swept_type": self.swept_type,
            "rejection_score": self.rejection_score,
            "volume_confirmed": self.volume_confirmed,
            "warning": self.warning,
        }


class LiquiditySweepDetector:
    """Detect equal-high/low and swing liquidity sweeps without future candles."""

    def __init__(
        self,
        lookback: int = 30,
        equal_tolerance_pct: float = 0.0015,
        rejection_threshold: float = 0.55,
        volume_multiplier_threshold: float = 1.10,
    ) -> None:
        self._lookback = max(8, int(lookback))
        self._equal_tolerance_pct = max(0.0, float(equal_tolerance_pct))
        self._rejection_threshold = _clip(rejection_threshold)
        self._volume_multiplier_threshold = max(0.0, float(volume_multiplier_threshold))
        self._swing_detector = SwingDetector(lookback=3, min_separation=1)

    def analyze(self, candles: pd.DataFrame) -> LiquiditySweepResult:
        """Analyze latest closed candle only with historical context."""
        return self.analyze_at(candles, len(candles) - 1)

    def analyze_at(self, candles: pd.DataFrame, index: int) -> LiquiditySweepResult:
        """Analyze one index with data up to index."""
        if index < 0:
            raise ValueError("Index must be non-negative.")
        window = candles.iloc[: index + 1].copy(deep=True)
        _validate_candles(window)
        if len(window) < 6:
            return LiquiditySweepResult(
                detected=False,
                direction="NONE",
                level=None,
                swept_type="NONE",
                rejection_score=0.0,
                volume_confirmed=False,
            )

        row = window.iloc[-1]
        high = float(row["high"])
        low = float(row["low"])
        close = float(row["close"])
        open_price = float(row["open"])
        candle_range = max(high - low, 1e-9)
        upper_wick = max(0.0, high - max(open_price, close))
        lower_wick = max(0.0, min(open_price, close) - low)
        bearish_rejection = _clip(upper_wick / candle_range)
        bullish_rejection = _clip(lower_wick / candle_range)

        lookback_window = window.iloc[-(self._lookback + 1) : -1]
        eq_high_level = _equal_level(lookback_window["high"], self._equal_tolerance_pct)
        eq_low_level = _equal_level(lookback_window["low"], self._equal_tolerance_pct)

        prior_swings = self._swing_detector.detect(window.iloc[:-1])
        prior_swing_high = _last_swing(prior_swings, SwingType.HIGH)
        prior_swing_low = _last_swing(prior_swings, SwingType.LOW)

        bearish_level = _max_level(eq_high_level, prior_swing_high)
        bullish_level = _min_level(eq_low_level, prior_swing_low)

        detected = False
        direction = "NONE"
        level = None
        swept_type = "NONE"
        rejection_score = 0.0

        if bearish_level is not None and high > bearish_level and close < bearish_level:
            detected = bearish_rejection >= self._rejection_threshold
            direction = "SELL"
            level = bearish_level
            swept_type = _swept_type(eq_high_level, prior_swing_high, bearish_level)
            rejection_score = bearish_rejection
        elif bullish_level is not None and low < bullish_level and close > bullish_level:
            detected = bullish_rejection >= self._rejection_threshold
            direction = "BUY"
            level = bullish_level
            swept_type = _swept_type(eq_low_level, prior_swing_low, bullish_level)
            rejection_score = bullish_rejection

        volume_confirmed, volume_warning = _volume_confirmation(
            window,
            threshold=self._volume_multiplier_threshold,
        )
        warning = None
        if direction != "NONE" and not volume_confirmed:
            warning = volume_warning or "Sweep detected but volume confirmation is weak."

        return LiquiditySweepResult(
            detected=detected and direction != "NONE",
            direction=direction,
            level=level,
            swept_type=swept_type,
            rejection_score=round(rejection_score, 4),
            volume_confirmed=volume_confirmed,
            warning=warning,
        )


def _volume_confirmation(
    candles: pd.DataFrame,
    threshold: float,
) -> tuple[bool, str | None]:
    if "volume" not in candles:
        return False, "Volume is unavailable."
    if len(candles) < 4:
        return False, "Insufficient volume history."
    current = float(candles.iloc[-1]["volume"])
    baseline = float(candles.iloc[:-1]["volume"].tail(20).mean())
    if baseline <= 0:
        return False, "Volume baseline is invalid."
    ratio = current / baseline
    if ratio >= threshold:
        return True, None
    return False, f"Volume ratio {ratio:.2f} is below threshold {threshold:.2f}."


def _equal_level(series: pd.Series, tolerance_pct: float) -> float | None:
    if len(series) < 4:
        return None
    values = [float(value) for value in series.tail(12).tolist()]
    for idx in range(len(values) - 1, 0, -1):
        current = values[idx]
        for jdx in range(idx - 1, -1, -1):
            compare = values[jdx]
            tolerance = max(abs(compare) * tolerance_pct, 1e-9)
            if abs(current - compare) <= tolerance:
                return (current + compare) / 2.0
    return None


def _last_swing(swings, swing_type: SwingType) -> float | None:
    for point in reversed(swings):
        if point.swing_type is swing_type:
            return float(point.price)
    return None


def _swept_type(equal_level: float | None, swing_level: float | None, selected: float) -> str:
    equal_match = equal_level is not None and abs(selected - equal_level) < 1e-9
    swing_match = swing_level is not None and abs(selected - swing_level) < 1e-9
    if equal_match and swing_match:
        return "EQUAL_AND_SWING"
    if equal_match:
        return "EQUAL_LEVELS"
    if swing_match:
        return "SWING_LEVEL"
    return "UNKNOWN"


def _max_level(a: float | None, b: float | None) -> float | None:
    if a is None:
        return b
    if b is None:
        return a
    return max(a, b)


def _min_level(a: float | None, b: float | None) -> float | None:
    if a is None:
        return b
    if b is None:
        return a
    return min(a, b)


def _validate_candles(candles: pd.DataFrame) -> None:
    required = {"open", "high", "low", "close"}
    missing = [column for column in required if column not in candles]
    if missing:
        raise ValueError(f"Candle DataFrame is missing columns: {missing}.")
    if candles.empty:
        raise ValueError("Candle DataFrame must not be empty.")


def _clip(value: float) -> float:
    return max(0.0, min(float(value), 1.0))

