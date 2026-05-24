"""Strictly-causal market structure analyzer."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from price_action.candle_analyzer import CandleAnalysis, CandleAnalyzer
from price_action.swing_detector import SwingDetector, SwingPoint, SwingType
from reasoning.evidence import Evidence, EvidenceDirection, EvidenceType


@dataclass(frozen=True)
class PriceActionContext:
    """Causal price-action context for reasoning and analytics."""

    structure: str
    bos_detected: bool
    choch_detected: bool
    pullback_quality_score: float
    candle_strength_score: float
    rejection_wick_score: float
    range_quality_score: float
    chasing_penalty: float
    evidence: list[Evidence] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize context into API-friendly primitive values."""
        return {
            "structure": self.structure,
            "bos_detected": self.bos_detected,
            "choch_detected": self.choch_detected,
            "pullback_quality_score": self.pullback_quality_score,
            "candle_strength_score": self.candle_strength_score,
            "rejection_wick_score": self.rejection_wick_score,
            "range_quality_score": self.range_quality_score,
            "chasing_penalty": self.chasing_penalty,
            "evidence": [item.to_dict() for item in self.evidence],
        }


class StructureAnalyzer:
    """Analyze causal structure: HH/HL, LH/LL, BOS, CHOCH and candle context."""

    def __init__(
        self,
        swing_detector: SwingDetector | None = None,
        candle_analyzer: CandleAnalyzer | None = None,
    ) -> None:
        self._swing_detector = swing_detector or SwingDetector(lookback=3, min_separation=1)
        self._candle_analyzer = candle_analyzer or CandleAnalyzer()

    def analyze(self, candles: pd.DataFrame) -> PriceActionContext:
        """Analyze market structure at the latest closed candle."""
        return self.analyze_at(candles, index=len(candles) - 1)

    def analyze_at(self, candles: pd.DataFrame, index: int) -> PriceActionContext:
        """Analyze structure at one candle index using data up to that index only."""
        if index < 0:
            raise ValueError("Index must be non-negative.")
        window = candles.iloc[: index + 1].copy(deep=True)
        _validate_candles(window)
        swings = self._swing_detector.detect(window)
        structure = _infer_structure(swings)
        prior_swings = self._swing_detector.detect(window.iloc[:-1]) if len(window) > 1 else []
        prior_structure = _infer_structure(prior_swings)
        bos_detected, choch_detected = _detect_bos_choch(
            window,
            prior_swings=prior_swings,
            prior_structure=prior_structure,
        )
        candle = self._candle_analyzer.analyze(window)
        pullback_quality = _pullback_quality(window, structure, swings)
        evidence = _build_evidence(
            structure=structure,
            bos_detected=bos_detected,
            choch_detected=choch_detected,
            pullback_quality_score=pullback_quality,
            candle=candle,
        )
        return PriceActionContext(
            structure=structure,
            bos_detected=bos_detected,
            choch_detected=choch_detected,
            pullback_quality_score=round(pullback_quality, 4),
            candle_strength_score=candle.candle_strength_score,
            rejection_wick_score=candle.rejection_wick_score,
            range_quality_score=candle.range_quality_score,
            chasing_penalty=candle.chasing_penalty,
            evidence=evidence,
        )


def _detect_bos_choch(
    candles: pd.DataFrame,
    prior_swings: list[SwingPoint],
    prior_structure: str,
) -> tuple[bool, bool]:
    close = float(candles.iloc[-1]["close"])
    highs = [point for point in prior_swings if point.swing_type is SwingType.HIGH]
    lows = [point for point in prior_swings if point.swing_type is SwingType.LOW]
    bos = False
    choch = False

    if prior_structure == "HH_HL":
        if highs:
            bos = close > highs[-1].price
        if lows:
            choch = close < lows[-1].price
    elif prior_structure == "LH_LL":
        if lows:
            bos = close < lows[-1].price
        if highs:
            choch = close > highs[-1].price

    if bos and choch:
        # Simultaneous break is ambiguous; prioritize CHOCH as reversal warning.
        bos = False
    return bos, choch


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

    if structure == "HH_HL":
        swing_high = highs[-1].price
        swing_low = lows[-1].price
        width = max(swing_high - swing_low, 1e-9)
        retrace = (swing_high - close) / width
        return _clip(1.0 - abs(retrace - 0.5) / 0.5)
    if structure == "LH_LL":
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
        return "UNKNOWN"

    higher_high = highs[-1].price > highs[-2].price
    higher_low = lows[-1].price > lows[-2].price
    lower_high = highs[-1].price < highs[-2].price
    lower_low = lows[-1].price < lows[-2].price
    if higher_high and higher_low:
        return "HH_HL"
    if lower_high and lower_low:
        return "LH_LL"
    return "RANGE"


def _build_evidence(
    structure: str,
    bos_detected: bool,
    choch_detected: bool,
    pullback_quality_score: float,
    candle: CandleAnalysis,
) -> list[Evidence]:
    direction = _structure_direction(structure)
    evidence: list[Evidence] = [
        Evidence(
            name="Market Structure",
            source="price_action.structure_analyzer",
            direction=direction,
            score=1.0 if structure in {"HH_HL", "LH_LL"} else 0.5,
            confidence=0.8 if structure in {"HH_HL", "LH_LL"} else 0.5,
            weight=1.0,
            evidence_type=EvidenceType.SUPPORT
            if structure in {"HH_HL", "LH_LL"}
            else EvidenceType.WARNING,
            reason=f"Detected structure: {structure}.",
            impact_on_score=0.12 if structure in {"HH_HL", "LH_LL"} else -0.05,
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
                direction=direction,
                score=1.0,
                confidence=0.85,
                weight=1.0,
                evidence_type=EvidenceType.SUPPORT,
                reason="Price closed beyond the latest structural continuation level.",
                impact_on_score=0.2,
                is_critical=True,
            )
        )
    if choch_detected:
        evidence.append(
            Evidence(
                name="Change of Character",
                source="price_action.structure_analyzer",
                direction=EvidenceDirection.NEUTRAL,
                score=1.0,
                confidence=0.85,
                weight=1.0,
                evidence_type=EvidenceType.WARNING,
                reason="Price closed through a key opposite-side structure level.",
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


def _structure_direction(structure: str) -> EvidenceDirection:
    if structure == "HH_HL":
        return EvidenceDirection.BUY
    if structure == "LH_LL":
        return EvidenceDirection.SELL
    return EvidenceDirection.NEUTRAL


def _validate_candles(candles: pd.DataFrame) -> None:
    required = {"timestamp", "open", "high", "low", "close"}
    missing = [column for column in required if column not in candles]
    if missing:
        raise ValueError(f"Candle DataFrame is missing columns: {missing}.")
    if candles.empty:
        raise ValueError("Candle DataFrame must not be empty.")


def _clip(value: float) -> float:
    return max(0.0, min(float(value), 1.0))
