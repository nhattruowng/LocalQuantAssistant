"""Strictly-causal liquidity sweep detection."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from price_action.swing_detector import SwingDetector, SwingType
from reasoning.evidence import Evidence, EvidenceDirection, EvidenceType


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
    fakeout_risk_score: float = 0.0
    evidence: list[Evidence] = field(default_factory=list)

    @property
    def liquidity_sweep_detected(self) -> bool:
        """Alias for API payload naming."""
        return self.detected

    @property
    def sweep_direction(self) -> str:
        """Alias for API payload naming."""
        return self.direction

    @property
    def swept_level(self) -> float | None:
        """Alias for API payload naming."""
        return self.level

    def to_dict(self) -> dict[str, Any]:
        return {
            "detected": self.detected,
            "direction": self.direction,
            "level": self.level,
            "swept_type": self.swept_type,
            "rejection_score": self.rejection_score,
            "volume_confirmed": self.volume_confirmed,
            "warning": self.warning,
            "liquidity_sweep_detected": self.liquidity_sweep_detected,
            "sweep_direction": self.sweep_direction,
            "swept_level": self.swept_level,
            "fakeout_risk_score": self.fakeout_risk_score,
            "evidence": [item.to_dict() for item in self.evidence],
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

    def analyze(
        self,
        candles: pd.DataFrame | list[Mapping[str, object]] | list[object],
    ) -> LiquiditySweepResult:
        """Analyze latest closed candle only with historical context."""
        frame = _to_frame(candles)
        return self.analyze_at(frame, len(frame) - 1)

    def analyze_at(
        self,
        candles: pd.DataFrame | list[Mapping[str, object]] | list[object],
        index: int,
    ) -> LiquiditySweepResult:
        """Analyze one index with data up to index."""
        frame = _to_frame(candles)
        if index < 0:
            raise ValueError("Index must be non-negative.")
        if index >= len(frame):
            raise ValueError("Index is outside available candle range.")
        window = frame.iloc[: index + 1].copy(deep=True)
        _validate_candles(window)
        if len(window) < 6:
            return _result(
                detected=False,
                direction="NONE",
                level=None,
                swept_type="NONE",
                rejection_score=0.0,
                volume_confirmed=False,
                warning=None,
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

        raw_sweep = False
        detected = False
        direction = "NONE"
        level = None
        swept_type = "NONE"
        rejection_score = 0.0

        if bearish_level is not None and high > bearish_level:
            raw_sweep = True
            direction = "SELL"
            level = bearish_level
            swept_type = _swept_type(eq_high_level, prior_swing_high, bearish_level)
            rejection_score = bearish_rejection if close < bearish_level else 0.0
            detected = close < bearish_level and bearish_rejection >= self._rejection_threshold
        elif bullish_level is not None and low < bullish_level:
            raw_sweep = True
            direction = "BUY"
            level = bullish_level
            swept_type = _swept_type(eq_low_level, prior_swing_low, bullish_level)
            rejection_score = bullish_rejection if close > bullish_level else 0.0
            detected = close > bullish_level and bullish_rejection >= self._rejection_threshold

        volume_confirmed, volume_warning = _volume_confirmation(
            window,
            threshold=self._volume_multiplier_threshold,
        )
        warning = None
        if direction != "NONE" and not volume_confirmed:
            warning = volume_warning or "Sweep detected but volume confirmation is weak."
        if raw_sweep and not detected and warning is None:
            warning = "Liquidity level was swept but rejection confirmation is weak."

        return _result(
            detected=detected and direction != "NONE",
            direction=direction,
            level=level,
            swept_type=swept_type,
            rejection_score=round(rejection_score, 4),
            volume_confirmed=volume_confirmed,
            warning=warning,
        )


def _result(
    *,
    detected: bool,
    direction: str,
    level: float | None,
    swept_type: str,
    rejection_score: float,
    volume_confirmed: bool,
    warning: str | None,
) -> LiquiditySweepResult:
    fakeout_risk = _fakeout_risk(detected, rejection_score, volume_confirmed, direction)
    result = LiquiditySweepResult(
        detected=detected,
        direction=direction,
        level=level,
        swept_type=swept_type,
        rejection_score=rejection_score,
        volume_confirmed=volume_confirmed,
        warning=warning,
        fakeout_risk_score=fakeout_risk,
    )
    return LiquiditySweepResult(
        detected=result.detected,
        direction=result.direction,
        level=result.level,
        swept_type=result.swept_type,
        rejection_score=result.rejection_score,
        volume_confirmed=result.volume_confirmed,
        warning=result.warning,
        fakeout_risk_score=result.fakeout_risk_score,
        evidence=_build_evidence(result),
    )


def _build_evidence(result: LiquiditySweepResult) -> list[Evidence]:
    evidence: list[Evidence] = []
    if result.direction in {"BUY", "SELL"}:
        direction = EvidenceDirection(result.direction)
        evidence.append(
            Evidence(
                name="Liquidity Sweep",
                source="ict.liquidity_sweep_detector",
                direction=direction,
                score=result.rejection_score,
                confidence=0.76 if result.detected else 0.55,
                weight=0.9,
                evidence_type=EvidenceType.SUPPORT if result.detected else EvidenceType.WARNING,
                reason=(
                    f"{result.swept_type} sweep direction={result.direction} "
                    f"level={result.level} rejection={result.rejection_score:.2f}."
                ),
                impact_on_score=0.0,
                is_critical=False,
            )
        )
    if result.warning:
        evidence.append(
            Evidence(
                name="Liquidity Sweep Warning",
                source="ict.liquidity_sweep_detector",
                direction=EvidenceDirection.NEUTRAL,
                score=max(0.1, 1.0 - result.fakeout_risk_score),
                confidence=0.78,
                weight=0.8,
                evidence_type=EvidenceType.WARNING,
                reason=result.warning,
                impact_on_score=-round(result.fakeout_risk_score * 0.12, 4),
                is_critical=False,
            )
        )
    if result.fakeout_risk_score >= 0.55:
        evidence.append(
            Evidence(
                name="Fakeout Risk",
                source="ict.liquidity_sweep_detector",
                direction=EvidenceDirection.NEUTRAL,
                score=result.fakeout_risk_score,
                confidence=0.75,
                weight=0.9,
                evidence_type=EvidenceType.WARNING,
                reason=f"Liquidity sweep fakeout risk score is {result.fakeout_risk_score:.2f}.",
                impact_on_score=-round(result.fakeout_risk_score * 0.18, 4),
                is_critical=False,
            )
        )
    return evidence


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


def _fakeout_risk(
    detected: bool,
    rejection_score: float,
    volume_confirmed: bool,
    direction: str,
) -> float:
    if direction == "NONE":
        return 0.0
    risk = 0.15
    risk += (1.0 - rejection_score) * 0.45
    if not detected:
        risk += 0.20
    if not volume_confirmed:
        risk += 0.35
    return round(_clip(risk), 4)


def _to_frame(candles: pd.DataFrame | list[Mapping[str, object]] | list[object]) -> pd.DataFrame:
    if isinstance(candles, pd.DataFrame):
        return candles.copy(deep=True)
    rows: list[dict[str, object]] = []
    for candle in candles:
        if isinstance(candle, Mapping):
            rows.append(dict(candle))
        else:
            rows.append(
                {
                    column: getattr(candle, column, None)
                    for column in ("timestamp", "open", "high", "low", "close", "volume")
                }
            )
    return pd.DataFrame(rows)


def _validate_candles(candles: pd.DataFrame) -> None:
    required = {"open", "high", "low", "close"}
    missing = [column for column in required if column not in candles]
    if missing:
        raise ValueError(f"Candle DataFrame is missing columns: {missing}.")
    if candles.empty:
        raise ValueError("Candle DataFrame must not be empty.")


def _clip(value: float) -> float:
    return max(0.0, min(float(value), 1.0))
