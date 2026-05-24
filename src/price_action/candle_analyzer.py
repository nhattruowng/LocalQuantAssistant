"""Causal candle, pullback, range, and exhaustion quality analysis."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from reasoning.evidence import Evidence, EvidenceDirection, EvidenceType


@dataclass(frozen=True)
class CandleAnalysis:
    """Score payload computed from candles up to the current close."""

    candle_strength_score: float
    rejection_wick_score: float
    range_quality_score: float
    chasing_penalty: float
    candle_body_strength: float = 0.0
    close_location_score: float = 0.5
    pullback_quality_score: float = 0.5
    trend_exhaustion_score: float = 0.0
    evidence: list[Evidence] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize analysis into API-friendly primitive values."""
        return {
            "candle_strength_score": self.candle_strength_score,
            "rejection_wick_score": self.rejection_wick_score,
            "pullback_quality_score": self.pullback_quality_score,
            "range_quality_score": self.range_quality_score,
            "chasing_penalty": self.chasing_penalty,
            "trend_exhaustion_score": self.trend_exhaustion_score,
            "candle_body_strength": self.candle_body_strength,
            "close_location_score": self.close_location_score,
            "evidence": [item.to_dict() for item in self.evidence],
        }


PriceActionContext = CandleAnalysis


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

    def analyze(self, candles: pd.DataFrame | list[Mapping[str, object]] | list[object]) -> CandleAnalysis:
        """Analyze candle quality using only provided historical candles."""
        frame = _to_frame(candles)
        _validate_candles(frame)
        window = frame.iloc[-self._range_window :].copy(deep=True)
        row = window.iloc[-1]
        open_price = _as_float(row.get("open"), 0.0)
        close = _as_float(row.get("close"), open_price)
        high = _as_float(row.get("high"), max(open_price, close))
        low = _as_float(row.get("low"), min(open_price, close))
        candle_range = max(high - low, 1e-9)
        body = abs(close - open_price)
        upper_wick = max(0.0, high - max(open_price, close))
        lower_wick = max(0.0, min(open_price, close) - low)

        candle_body_strength = _clip(body / candle_range)
        close_location = _clip((close - low) / candle_range)
        close_location_score = _close_location_score(close_location, close >= open_price)
        candle_strength = _clip(candle_body_strength * 0.7 + close_location_score * 0.3)
        rejection_wick = _clip(max(upper_wick, lower_wick) / candle_range)
        range_quality = self._range_quality(window)
        chasing_penalty = self._chasing_penalty(window, close)
        pullback_quality = self._pullback_quality(window, close)
        trend_exhaustion = self._trend_exhaustion(window, close, rejection_wick, chasing_penalty)
        analysis = CandleAnalysis(
            candle_strength_score=round(candle_strength, 4),
            rejection_wick_score=round(rejection_wick, 4),
            range_quality_score=round(range_quality, 4),
            chasing_penalty=round(chasing_penalty, 4),
            candle_body_strength=round(candle_body_strength, 4),
            close_location_score=round(close_location_score, 4),
            pullback_quality_score=round(pullback_quality, 4),
            trend_exhaustion_score=round(trend_exhaustion, 4),
        )
        return CandleAnalysis(
            candle_strength_score=analysis.candle_strength_score,
            rejection_wick_score=analysis.rejection_wick_score,
            range_quality_score=analysis.range_quality_score,
            chasing_penalty=analysis.chasing_penalty,
            candle_body_strength=analysis.candle_body_strength,
            close_location_score=analysis.close_location_score,
            pullback_quality_score=analysis.pullback_quality_score,
            trend_exhaustion_score=analysis.trend_exhaustion_score,
            evidence=_build_evidence(analysis),
        )

    def _range_quality(self, candles: pd.DataFrame) -> float:
        high = float(candles["high"].max())
        low = float(candles["low"].min())
        span = max(high - low, 1e-9)
        atr = _atr_value(candles, self._atr_column)
        span_in_atr = span / max(atr, 1e-9)
        highs_near_top, lows_near_bottom = _range_test_counts(candles, high, low)
        total_tests = highs_near_top + lows_near_bottom
        atr_change = _atr_expansion_score(candles, self._atr_column)
        compact_score = _clip(1.0 - max(0.0, (span_in_atr - 6.0) / 12.0))
        test_penalty = _clip(max(0, total_tests - 4) / 6.0)
        quality = compact_score - test_penalty * 0.35 - atr_change * 0.25
        return _clip(quality)

    def _chasing_penalty(self, candles: pd.DataFrame, close: float) -> float:
        row = candles.iloc[-1]
        ema = _as_float(row.get(self._ema_column), close)
        atr = _atr_value(candles, self._atr_column)
        atr_distance = abs(close - ema) / max(atr, 1e-9)
        return _clip(max(0.0, (atr_distance - 1.0) / 2.0))

    def _pullback_quality(self, candles: pd.DataFrame, close: float) -> float:
        ema = _as_float(candles.iloc[-1].get(self._ema_column), close)
        atr = _atr_value(candles, self._atr_column)
        distance_atr = abs(close - ema) / max(atr, 1e-9)
        proximity = _clip(1.0 - max(0.0, distance_atr - 0.25) / 1.75)
        if len(candles) < 3:
            return proximity
        closes = candles["close"].astype(float)
        recent_slope = closes.iloc[-1] - closes.iloc[-3]
        ema_bias = close - ema
        aligned_reclaim = (
            (ema_bias >= 0 and recent_slope >= 0)
            or (ema_bias <= 0 and recent_slope <= 0)
        )
        reclaim_bonus = 0.15 if aligned_reclaim else -0.1
        return _clip(proximity + reclaim_bonus)

    def _trend_exhaustion(
        self,
        candles: pd.DataFrame,
        close: float,
        rejection_wick_score: float,
        chasing_penalty: float,
    ) -> float:
        if len(candles) < 3:
            return _clip(max(rejection_wick_score, chasing_penalty) * 0.5)
        closes = candles["close"].astype(float)
        latest_move = closes.iloc[-1] - closes.iloc[-2]
        prior_move = closes.iloc[-2] - closes.iloc[-3]
        direction = 1 if latest_move >= 0 else -1
        row = candles.iloc[-1]
        high = _as_float(row.get("high"), close)
        low = _as_float(row.get("low"), close)
        open_price = _as_float(row.get("open"), close)
        candle_range = max(high - low, 1e-9)
        upper_wick = max(0.0, high - max(open_price, close)) / candle_range
        lower_wick = max(0.0, min(open_price, close) - low) / candle_range
        opposite_wick = upper_wick if direction >= 0 else lower_wick
        acceleration = abs(latest_move) > abs(prior_move) * 1.15
        stretched = chasing_penalty >= 0.55
        score = 0.0
        if stretched:
            score += 0.35
        if opposite_wick >= 0.35:
            score += 0.35
        if acceleration:
            score += 0.15
        if rejection_wick_score >= 0.55:
            score += 0.15
        return _clip(score)


def _build_evidence(analysis: CandleAnalysis) -> list[Evidence]:
    evidence: list[Evidence] = [
        Evidence(
            name="Candle Body Strength",
            source="price_action.candle_analyzer",
            direction=EvidenceDirection.NEUTRAL,
            score=analysis.candle_body_strength,
            confidence=0.7,
            weight=0.7,
            evidence_type=EvidenceType.SUPPORT,
            reason=f"Candle body strength is {analysis.candle_body_strength:.2f}.",
            impact_on_score=round((analysis.candle_body_strength - 0.5) * 0.10, 4),
        ),
        Evidence(
            name="Close Location",
            source="price_action.candle_analyzer",
            direction=EvidenceDirection.NEUTRAL,
            score=analysis.close_location_score,
            confidence=0.65,
            weight=0.6,
            evidence_type=EvidenceType.SUPPORT,
            reason=f"Close location score is {analysis.close_location_score:.2f}.",
            impact_on_score=round((analysis.close_location_score - 0.5) * 0.08, 4),
        ),
        Evidence(
            name="Pullback Quality",
            source="price_action.candle_analyzer",
            direction=EvidenceDirection.NEUTRAL,
            score=analysis.pullback_quality_score,
            confidence=0.7,
            weight=0.8,
            evidence_type=EvidenceType.SUPPORT,
            reason=f"Pullback quality score is {analysis.pullback_quality_score:.2f}.",
            impact_on_score=round((analysis.pullback_quality_score - 0.5) * 0.12, 4),
        ),
        Evidence(
            name="Range Quality",
            source="price_action.candle_analyzer",
            direction=EvidenceDirection.NEUTRAL,
            score=analysis.range_quality_score,
            confidence=0.7,
            weight=0.7,
            evidence_type=EvidenceType.SUPPORT
            if analysis.range_quality_score >= 0.55
            else EvidenceType.WARNING,
            reason=f"Range quality score is {analysis.range_quality_score:.2f}.",
            impact_on_score=round((analysis.range_quality_score - 0.5) * 0.10, 4),
        ),
    ]
    if analysis.rejection_wick_score >= 0.45:
        evidence.append(
            Evidence(
                name="Rejection Wick",
                source="price_action.candle_analyzer",
                direction=EvidenceDirection.NEUTRAL,
                score=analysis.rejection_wick_score,
                confidence=0.75,
                weight=0.9,
                evidence_type=EvidenceType.WARNING,
                reason=f"Rejection wick score is {analysis.rejection_wick_score:.2f}.",
                impact_on_score=-round(analysis.rejection_wick_score * 0.12, 4),
            )
        )
    if analysis.chasing_penalty >= 0.4:
        evidence.append(
            Evidence(
                name="Chasing Penalty",
                source="price_action.candle_analyzer",
                direction=EvidenceDirection.NEUTRAL,
                score=analysis.chasing_penalty,
                confidence=0.8,
                weight=1.0,
                evidence_type=EvidenceType.AGAINST,
                reason=f"Chasing penalty is {analysis.chasing_penalty:.2f}.",
                impact_on_score=-round(analysis.chasing_penalty * 0.18, 4),
            )
        )
    if analysis.trend_exhaustion_score >= 0.55:
        evidence.append(
            Evidence(
                name="Trend Exhaustion",
                source="price_action.candle_analyzer",
                direction=EvidenceDirection.NEUTRAL,
                score=analysis.trend_exhaustion_score,
                confidence=0.78,
                weight=1.0,
                evidence_type=EvidenceType.WARNING,
                reason=f"Trend exhaustion score is {analysis.trend_exhaustion_score:.2f}.",
                impact_on_score=-round(analysis.trend_exhaustion_score * 0.2, 4),
                is_critical=True,
            )
        )
    return evidence


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


def _atr_value(candles: pd.DataFrame, atr_column: str) -> float:
    if atr_column in candles:
        series = pd.to_numeric(candles[atr_column], errors="coerce").dropna()
        if not series.empty:
            return max(float(series.iloc[-1]), 1e-9)
    return max(float((candles["high"] - candles["low"]).mean()), 1e-9)


def _range_test_counts(candles: pd.DataFrame, high: float, low: float) -> tuple[int, int]:
    span = max(high - low, 1e-9)
    tolerance = span * 0.12
    highs_near_top = int((candles["high"].astype(float) >= high - tolerance).sum())
    lows_near_bottom = int((candles["low"].astype(float) <= low + tolerance).sum())
    return highs_near_top, lows_near_bottom


def _atr_expansion_score(candles: pd.DataFrame, atr_column: str) -> float:
    if len(candles) < 4:
        return 0.0
    if atr_column in candles:
        atr = pd.to_numeric(candles[atr_column], errors="coerce").dropna()
    else:
        atr = (candles["high"].astype(float) - candles["low"].astype(float)).dropna()
    if len(atr) < 4:
        return 0.0
    first = max(float(atr.iloc[0]), 1e-9)
    last = max(float(atr.iloc[-1]), 1e-9)
    return _clip((last / first - 1.0) / 1.5)


def _close_location_score(close_location: float, bullish: bool) -> float:
    return close_location if bullish else 1.0 - close_location


def _as_float(value: object, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(parsed):
        return default
    return parsed


def _clip(value: float) -> float:
    return max(0.0, min(float(value), 1.0))
