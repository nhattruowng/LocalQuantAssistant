"""ICT context builder for reasoning evidence."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from ict.fvg_detector import FVGDetector, FVGResult
from ict.liquidity_sweep_detector import LiquiditySweepDetector, LiquiditySweepResult
from ict.order_block_detector import OrderBlockDetector, OrderBlockResult
from reasoning.evidence import Evidence, EvidenceDirection, EvidenceType


@dataclass(frozen=True)
class ICTContext:
    """ICT supporting context for market reasoning."""

    liquidity_sweep_detected: bool
    sweep_direction: str
    nearest_order_block: dict[str, Any] | None
    distance_to_nearest_ob: float
    fvg_detected: bool
    fvg_fill_ratio: float
    ict_score: float
    fakeout_risk_score: float
    evidence: list[Evidence] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "liquidity_sweep_detected": self.liquidity_sweep_detected,
            "sweep_direction": self.sweep_direction,
            "nearest_order_block": self.nearest_order_block,
            "distance_to_nearest_ob": self.distance_to_nearest_ob,
            "fvg_detected": self.fvg_detected,
            "fvg_fill_ratio": self.fvg_fill_ratio,
            "ict_score": self.ict_score,
            "fakeout_risk_score": self.fakeout_risk_score,
            "evidence": [item.to_dict() for item in self.evidence],
        }


class ICTContextBuilder:
    """Build ICTContext from causal detectors."""

    def __init__(
        self,
        sweep_detector: LiquiditySweepDetector | None = None,
        order_block_detector: OrderBlockDetector | None = None,
        fvg_detector: FVGDetector | None = None,
        enabled: bool = True,
    ) -> None:
        self._sweep_detector = sweep_detector or LiquiditySweepDetector()
        self._order_block_detector = order_block_detector or OrderBlockDetector()
        self._fvg_detector = fvg_detector or FVGDetector()
        self._enabled = bool(enabled)

    def build(self, candles: pd.DataFrame, index: int | None = None) -> ICTContext:
        """Build context from candles up to index."""
        if not self._enabled:
            return self._empty_context()
        if candles.empty:
            return self._empty_context()
        target_index = len(candles) - 1 if index is None else int(index)
        sweep = self._sweep_detector.analyze_at(candles, target_index)
        ob = self._order_block_detector.analyze_at(candles, target_index)
        fvg = self._fvg_detector.analyze_at(candles, target_index)
        evidence = _build_ict_evidence(sweep, ob, fvg)
        ict_score = _ict_score(evidence)
        fakeout_risk = _fakeout_risk_score(sweep, fvg)
        return ICTContext(
            liquidity_sweep_detected=sweep.detected,
            sweep_direction=sweep.direction,
            nearest_order_block=ob.nearest_order_block,
            distance_to_nearest_ob=ob.distance_to_nearest_ob,
            fvg_detected=fvg.fvg_detected,
            fvg_fill_ratio=fvg.fvg_fill_ratio,
            ict_score=round(ict_score, 6),
            fakeout_risk_score=round(fakeout_risk, 6),
            evidence=evidence,
        )

    def _empty_context(self) -> ICTContext:
        return ICTContext(
            liquidity_sweep_detected=False,
            sweep_direction="NONE",
            nearest_order_block=None,
            distance_to_nearest_ob=1.0,
            fvg_detected=False,
            fvg_fill_ratio=0.0,
            ict_score=0.0,
            fakeout_risk_score=0.0,
            evidence=[],
        )


def _build_ict_evidence(
    sweep: LiquiditySweepResult,
    ob: OrderBlockResult,
    fvg: FVGResult,
) -> list[Evidence]:
    evidence: list[Evidence] = []
    if sweep.direction in {"BUY", "SELL"}:
        direction = EvidenceDirection(sweep.direction)
        evidence.append(
            Evidence(
                name="Liquidity Sweep",
                source="ict",
                direction=direction,
                score=sweep.rejection_score,
                confidence=0.75 if sweep.detected else 0.6,
                weight=1.0,
                evidence_type=EvidenceType.SUPPORT if sweep.detected else EvidenceType.WARNING,
                reason=(
                    f"{sweep.swept_type} liquidity sweep with rejection score "
                    f"{sweep.rejection_score:.2f}."
                ),
                impact_on_score=0.0,
                is_critical=sweep.detected,
            )
        )
        if sweep.warning:
            evidence.append(
                Evidence(
                    name="Sweep Volume Warning",
                    source="ict",
                    direction=EvidenceDirection.NEUTRAL,
                    score=0.4,
                    confidence=0.8,
                    weight=0.8,
                    evidence_type=EvidenceType.WARNING,
                    reason=sweep.warning,
                    impact_on_score=0.0,
                    is_critical=False,
                )
            )

    if ob.nearest_order_block is not None:
        ob_direction = EvidenceDirection(ob.nearest_order_block.get("direction", "NEUTRAL"))
        evidence.append(
            Evidence(
                name="Nearest Order Block",
                source="ict",
                direction=ob_direction,
                score=_clip(1.0 - ob.distance_to_nearest_ob / 0.02),
                confidence=ob.ob_mitigation_score,
                weight=0.9,
                evidence_type=EvidenceType.SUPPORT,
                reason=(
                    f"Nearest OB distance {ob.distance_to_nearest_ob:.4f}, "
                    f"mitigation score {ob.ob_mitigation_score:.2f}."
                ),
                impact_on_score=0.0,
                is_critical=False,
            )
        )

    if fvg.fvg_detected:
        direction = EvidenceDirection(fvg.direction)
        evidence.append(
            Evidence(
                name="Fair Value Gap",
                source="ict",
                direction=direction,
                score=_clip(1.0 - fvg.nearest_fvg_distance / 0.02),
                confidence=1.0 - _clip(fvg.fvg_fill_ratio),
                weight=0.8,
                evidence_type=EvidenceType.SUPPORT,
                reason=(
                    f"{fvg.direction} FVG detected, fill ratio {fvg.fvg_fill_ratio:.2f}, "
                    f"distance {fvg.nearest_fvg_distance:.4f}."
                ),
                impact_on_score=0.0,
                is_critical=False,
            )
        )
    return evidence


def _ict_score(evidence: list[Evidence]) -> float:
    if not evidence:
        return 0.0
    positive = sum(
        _clip(item.score) * _clip(item.confidence)
        for item in evidence
        if item.evidence_type is EvidenceType.SUPPORT
    )
    negative = sum(
        _clip(item.score) * _clip(item.confidence)
        for item in evidence
        if item.evidence_type in {EvidenceType.AGAINST, EvidenceType.WARNING}
    )
    return _clip(0.5 + (positive - negative) / max(len(evidence), 1))


def _fakeout_risk_score(sweep: LiquiditySweepResult, fvg: FVGResult) -> float:
    risk = 0.0
    if sweep.direction != "NONE" and not sweep.detected:
        risk += 0.35
    if sweep.warning:
        risk += 0.30
    if fvg.fvg_detected and fvg.fvg_fill_ratio > 0.75:
        risk += 0.35
    return _clip(risk)


def _clip(value: float) -> float:
    return max(0.0, min(float(value), 1.0))

