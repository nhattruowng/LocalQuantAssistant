"""Strictly-causal market structure analyzer."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from price_action.candle_analyzer import CandleAnalysis, CandleAnalyzer
from price_action.swing_detector import SwingDetector, SwingPoint, SwingType
from reasoning.evidence import Evidence, EvidenceDirection, EvidenceType
from signals.decision_trace import DecisionTrace


STRUCTURE_HH_HL = "HH_HL"
STRUCTURE_LH_LL = "LH_LL"
STRUCTURE_RANGE = "RANGE"
STRUCTURE_UNKNOWN = "UNKNOWN"
DIRECTION_BULLISH = "BULLISH"
DIRECTION_BEARISH = "BEARISH"


@dataclass(frozen=True)
class PriceStructureContext:
    """Causal market-structure context for reasoning and analytics."""

    structure: str
    bos_detected: bool
    choch_detected: bool
    pullback_quality_score: float = 0.5
    candle_strength_score: float = 0.5
    rejection_wick_score: float = 0.0
    range_quality_score: float = 0.5
    chasing_penalty: float = 0.0
    evidence: list[Evidence] = field(default_factory=list)
    bos_direction: str | None = None
    choch_direction: str | None = None
    structure_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Serialize context into API-friendly primitive values."""
        return {
            "structure": self.structure,
            "bos_detected": self.bos_detected,
            "bos_direction": self.bos_direction,
            "choch_detected": self.choch_detected,
            "choch_direction": self.choch_direction,
            "structure_score": self.structure_score,
            "pullback_quality_score": self.pullback_quality_score,
            "candle_strength_score": self.candle_strength_score,
            "rejection_wick_score": self.rejection_wick_score,
            "range_quality_score": self.range_quality_score,
            "chasing_penalty": self.chasing_penalty,
            "evidence": [item.to_dict() for item in self.evidence],
        }


PriceActionContext = PriceStructureContext


class StructureAnalyzer:
    """Analyze HH/HL, LH/LL, range, BOS, and CHOCH without future candles."""

    def __init__(
        self,
        swing_detector: SwingDetector | None = None,
        candle_analyzer: CandleAnalyzer | None = None,
    ) -> None:
        self._swing_detector = swing_detector or SwingDetector(lookback=3, min_separation=1)
        self._candle_analyzer = candle_analyzer or CandleAnalyzer()

    def analyze(
        self,
        candles: pd.DataFrame | list[Mapping[str, object]] | list[object],
        trace: DecisionTrace | None = None,
    ) -> PriceStructureContext:
        """Analyze market structure at the latest closed candle."""
        frame = _to_frame(candles)
        if frame.empty:
            return _empty_context(trace)
        return self.analyze_at(frame, index=len(frame) - 1, trace=trace)

    def analyze_at(
        self,
        candles: pd.DataFrame | list[Mapping[str, object]] | list[object],
        index: int,
        trace: DecisionTrace | None = None,
    ) -> PriceStructureContext:
        """Analyze structure at one candle index using data up to that index only."""
        frame = _to_frame(candles)
        if index < 0:
            raise ValueError("Index must be non-negative.")
        if index >= len(frame):
            raise ValueError("Index is outside available candle range.")

        window = frame.iloc[: index + 1].copy(deep=True)
        _validate_candles(window)
        swings = self._swing_detector.detect(window)
        structure = _infer_structure(swings)
        prior_swings = self._swing_detector.detect(window.iloc[:-1]) if len(window) > 1 else []
        prior_structure = _infer_structure(prior_swings)
        bos_detected, bos_direction, choch_detected, choch_direction = _detect_bos_choch(
            window,
            prior_swings=prior_swings,
            prior_structure=prior_structure,
        )
        candle = self._candle_analyzer.analyze(window)
        pullback_quality = _pullback_quality(window, structure, swings)
        structure_score = _structure_score(
            structure=structure,
            bos_detected=bos_detected,
            choch_detected=choch_detected,
            pullback_quality_score=pullback_quality,
            candle=candle,
        )
        evidence = _build_evidence(
            structure=structure,
            bos_detected=bos_detected,
            bos_direction=bos_direction,
            choch_detected=choch_detected,
            choch_direction=choch_direction,
            structure_score=structure_score,
            pullback_quality_score=pullback_quality,
            candle=candle,
        )
        context = PriceStructureContext(
            structure=structure,
            bos_detected=bos_detected,
            bos_direction=bos_direction,
            choch_detected=choch_detected,
            choch_direction=choch_direction,
            structure_score=structure_score,
            evidence=evidence,
            pullback_quality_score=round(pullback_quality, 4),
            candle_strength_score=candle.candle_strength_score,
            rejection_wick_score=candle.rejection_wick_score,
            range_quality_score=candle.range_quality_score,
            chasing_penalty=candle.chasing_penalty,
        )
        _append_trace(trace, context)
        return context


def _detect_bos_choch(
    candles: pd.DataFrame,
    prior_swings: list[SwingPoint],
    prior_structure: str,
) -> tuple[bool, str | None, bool, str | None]:
    close = float(candles.iloc[-1]["close"])
    highs = [point for point in prior_swings if point.swing_type is SwingType.HIGH]
    lows = [point for point in prior_swings if point.swing_type is SwingType.LOW]
    bos_detected = False
    bos_direction: str | None = None
    choch_detected = False
    choch_direction: str | None = None

    if prior_structure == STRUCTURE_HH_HL:
        if highs and close > highs[-1].price:
            bos_detected = True
            bos_direction = DIRECTION_BULLISH
        if lows and close < lows[-1].price:
            choch_detected = True
            choch_direction = DIRECTION_BEARISH
    elif prior_structure == STRUCTURE_LH_LL:
        if lows and close < lows[-1].price:
            bos_detected = True
            bos_direction = DIRECTION_BEARISH
        if highs and close > highs[-1].price:
            choch_detected = True
            choch_direction = DIRECTION_BULLISH

    if bos_detected and choch_detected:
        # Simultaneous breaks are ambiguous; prefer CHOCH as reversal warning.
        bos_detected = False
        bos_direction = None
    return bos_detected, bos_direction, choch_detected, choch_direction


def _pullback_quality(
    candles: pd.DataFrame,
    structure: str,
    swings: list[SwingPoint],
) -> float:
    close = float(candles.iloc[-1]["close"])
    highs = [point for point in swings if point.swing_type is SwingType.HIGH]
    lows = [point for point in swings if point.swing_type is SwingType.LOW]
    if len(highs) < 1 or len(lows) < 1:
        return 0.5

    if structure == STRUCTURE_HH_HL:
        swing_high = highs[-1].price
        swing_low = lows[-1].price
        width = max(swing_high - swing_low, 1e-9)
        retrace = (swing_high - close) / width
        return _clip(1.0 - abs(retrace - 0.5) / 0.5)
    if structure == STRUCTURE_LH_LL:
        swing_high = highs[-1].price
        swing_low = lows[-1].price
        width = max(swing_high - swing_low, 1e-9)
        retrace = (close - swing_low) / width
        return _clip(1.0 - abs(retrace - 0.5) / 0.5)
    return 0.5


def _infer_structure(swings: list[SwingPoint]) -> str:
    highs = [point for point in swings if point.swing_type is SwingType.HIGH]
    lows = [point for point in swings if point.swing_type is SwingType.LOW]
    if len(highs) < 2 or len(lows) < 2:
        return STRUCTURE_UNKNOWN

    higher_high = highs[-1].price > highs[-2].price
    higher_low = lows[-1].price > lows[-2].price
    lower_high = highs[-1].price < highs[-2].price
    lower_low = lows[-1].price < lows[-2].price
    if higher_high and higher_low:
        return STRUCTURE_HH_HL
    if lower_high and lower_low:
        return STRUCTURE_LH_LL
    return STRUCTURE_RANGE


def _structure_score(
    *,
    structure: str,
    bos_detected: bool,
    choch_detected: bool,
    pullback_quality_score: float,
    candle: CandleAnalysis,
) -> float:
    base = {
        STRUCTURE_HH_HL: 0.78,
        STRUCTURE_LH_LL: 0.78,
        STRUCTURE_RANGE: 0.52,
        STRUCTURE_UNKNOWN: 0.35,
    }.get(structure, 0.35)
    base += (pullback_quality_score - 0.5) * 0.16
    base += (candle.candle_strength_score - 0.5) * 0.10
    if bos_detected:
        base += 0.12
    if choch_detected:
        base -= 0.08
    if candle.chasing_penalty >= 0.4:
        base -= candle.chasing_penalty * 0.08
    return round(_clip(base), 4)


def _build_evidence(
    *,
    structure: str,
    bos_detected: bool,
    bos_direction: str | None,
    choch_detected: bool,
    choch_direction: str | None,
    structure_score: float,
    pullback_quality_score: float,
    candle: CandleAnalysis,
) -> list[Evidence]:
    direction = _structure_direction(structure)
    evidence: list[Evidence] = [
        Evidence(
            name="Market Structure",
            source="price_action.structure_analyzer",
            direction=direction,
            score=structure_score,
            confidence=0.82 if structure in {STRUCTURE_HH_HL, STRUCTURE_LH_LL} else 0.55,
            weight=1.0,
            evidence_type=EvidenceType.SUPPORT
            if structure in {STRUCTURE_HH_HL, STRUCTURE_LH_LL}
            else EvidenceType.WARNING,
            reason=f"Detected structure: {structure}.",
            impact_on_score=round((structure_score - 0.5) * 0.24, 4),
            is_critical=False,
        ),
        Evidence(
            name="Pullback Quality",
            source="price_action.structure_analyzer",
            direction=direction,
            score=pullback_quality_score,
            confidence=0.7,
            weight=0.8,
            evidence_type=EvidenceType.SUPPORT,
            reason=f"Pullback quality score is {pullback_quality_score:.2f}.",
            impact_on_score=round((pullback_quality_score - 0.5) * 0.16, 4),
            is_critical=False,
        ),
        Evidence(
            name="Candle Strength",
            source="price_action.candle_analyzer",
            direction=direction,
            score=candle.candle_strength_score,
            confidence=0.7,
            weight=0.8,
            evidence_type=EvidenceType.SUPPORT,
            reason=f"Candle strength score is {candle.candle_strength_score:.2f}.",
            impact_on_score=round((candle.candle_strength_score - 0.5) * 0.12, 4),
            is_critical=False,
        ),
    ]

    if bos_detected:
        evidence.append(
            Evidence(
                name="Break of Structure",
                source="price_action.structure_analyzer",
                direction=_break_direction(bos_direction),
                score=1.0,
                confidence=0.86,
                weight=1.0,
                evidence_type=EvidenceType.SUPPORT,
                reason=f"{bos_direction or 'UNKNOWN'} BOS: close broke continuation structure.",
                impact_on_score=0.2,
                is_critical=True,
            )
        )
    if choch_detected:
        evidence.append(
            Evidence(
                name="Change of Character",
                source="price_action.structure_analyzer",
                direction=_break_direction(choch_direction),
                score=1.0,
                confidence=0.86,
                weight=1.0,
                evidence_type=EvidenceType.WARNING,
                reason=f"{choch_direction or 'UNKNOWN'} CHOCH: close broke opposite-side structure.",
                impact_on_score=-0.2,
                is_critical=True,
            )
        )
    if candle.rejection_wick_score >= 0.55:
        evidence.append(
            Evidence(
                name="Rejection Wick",
                source="price_action.candle_analyzer",
                direction=EvidenceDirection.NEUTRAL,
                score=candle.rejection_wick_score,
                confidence=0.75,
                weight=0.9,
                evidence_type=EvidenceType.WARNING,
                reason=f"Large rejection wick detected ({candle.rejection_wick_score:.2f}).",
                impact_on_score=-round(candle.rejection_wick_score * 0.12, 4),
                is_critical=False,
            )
        )
    if candle.chasing_penalty >= 0.4:
        evidence.append(
            Evidence(
                name="Chasing Penalty",
                source="price_action.candle_analyzer",
                direction=EvidenceDirection.NEUTRAL,
                score=candle.chasing_penalty,
                confidence=0.8,
                weight=1.0,
                evidence_type=EvidenceType.AGAINST,
                reason=f"Price is extended from EMA by ATR context ({candle.chasing_penalty:.2f}).",
                impact_on_score=-round(candle.chasing_penalty * 0.18, 4),
                is_critical=False,
            )
        )
    return evidence


def _append_trace(trace: DecisionTrace | None, context: PriceStructureContext) -> None:
    if trace is None:
        return
    warnings: list[str] = []
    if context.choch_detected:
        warnings.append(f"CHOCH_{context.choch_direction or 'UNKNOWN'}")
    if context.structure in {STRUCTURE_RANGE, STRUCTURE_UNKNOWN}:
        warnings.append(f"STRUCTURE_{context.structure}")
    details = context.to_dict()
    details["evidence_count"] = len(context.evidence)
    trace.add_step(
        step_name="market_structure",
        input_score=0.0,
        output_score=context.structure_score,
        passed=context.structure != STRUCTURE_UNKNOWN,
        details=details,
        warnings=warnings,
    )


def _empty_context(trace: DecisionTrace | None = None) -> PriceStructureContext:
    context = PriceStructureContext(
        structure=STRUCTURE_UNKNOWN,
        bos_detected=False,
        bos_direction=None,
        choch_detected=False,
        choch_direction=None,
        structure_score=0.0,
        evidence=[],
    )
    _append_trace(trace, context)
    return context


def _structure_direction(structure: str) -> EvidenceDirection:
    if structure == STRUCTURE_HH_HL:
        return EvidenceDirection.BUY
    if structure == STRUCTURE_LH_LL:
        return EvidenceDirection.SELL
    return EvidenceDirection.NEUTRAL


def _break_direction(direction: str | None) -> EvidenceDirection:
    if direction == DIRECTION_BULLISH:
        return EvidenceDirection.BUY
    if direction == DIRECTION_BEARISH:
        return EvidenceDirection.SELL
    return EvidenceDirection.NEUTRAL


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
    required = {"timestamp", "open", "high", "low", "close"}
    missing = [column for column in required if column not in candles]
    if missing:
        raise ValueError(f"Candle DataFrame is missing columns: {missing}.")
    if candles.empty:
        raise ValueError("Candle DataFrame must not be empty.")


def _clip(value: float) -> float:
    return max(0.0, min(float(value), 1.0))
