"""Evidence-driven confluence scoring engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from reasoning.conflict_resolver import ConflictResolver, ConflictResult
from reasoning.evidence import Evidence, EvidenceType
from signals.decision_trace import DecisionTrace


DEFAULT_SOURCE_WEIGHTS: dict[str, float] = {
    "regime_alignment": 0.12,
    "market_structure": 0.18,
    "price_action": 0.15,
    "ict_confluence": 0.15,
    "volume_confirmation": 0.12,
    "multi_timeframe_alignment": 0.10,
    "model_probability": 0.08,
    "risk_reward_quality": 0.05,
}


@dataclass(frozen=True)
class ConfluenceResult:
    """Output payload from confluence scoring."""

    raw_score: float
    evidence_for: list[Evidence] = field(default_factory=list)
    evidence_against: list[Evidence] = field(default_factory=list)
    warnings: list[Evidence] = field(default_factory=list)
    score_breakdown: list[dict[str, Any]] = field(default_factory=list)
    normalized_score: float = 0.0
    final_score: float = 0.0
    conflict_penalty: float = 0.0
    conflict_result: ConflictResult | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize result into API-friendly values."""
        conflict_payload = self.conflict_result.to_dict() if self.conflict_result else None
        return {
            "raw_score": self.raw_score,
            "evidence_for": [item.to_dict() for item in self.evidence_for],
            "evidence_against": [item.to_dict() for item in self.evidence_against],
            "warnings": [item.to_dict() for item in self.warnings],
            "score_breakdown": list(self.score_breakdown),
            "normalized_score": self.normalized_score,
            "final_score": self.final_score,
            "conflict_penalty": self.conflict_penalty,
            "conflict_result": conflict_payload,
        }


class ConfluenceEngine:
    """Compute confluence score from heterogeneous evidence."""

    def __init__(
        self,
        source_weights: Mapping[str, float] | None = None,
        empty_score: float = 0.0,
        conflict_resolver: ConflictResolver | None = None,
    ) -> None:
        merged = dict(DEFAULT_SOURCE_WEIGHTS)
        for key, value in (source_weights or {}).items():
            merged[str(key)] = max(0.0, float(value))
        self._source_weights = merged
        self._empty_score = _clip(empty_score)
        self._conflict_resolver = conflict_resolver or ConflictResolver()

    def evaluate(
        self,
        evidence: list[Evidence],
        trace: DecisionTrace | None = None,
    ) -> ConfluenceResult:
        """Score evidence confluence and optionally append a trace step."""
        if not evidence:
            conflict = self._conflict_resolver.evaluate([])
            result = ConfluenceResult(
                raw_score=self._empty_score,
                evidence_for=[],
                evidence_against=[],
                warnings=[],
                score_breakdown=[],
                normalized_score=self._empty_score,
                final_score=self._empty_score,
                conflict_penalty=0.0,
                conflict_result=conflict,
            )
            self._append_trace(trace, result)
            return result

        evidence_for = [item for item in evidence if item.evidence_type is EvidenceType.SUPPORT]
        evidence_against = [item for item in evidence if item.evidence_type is EvidenceType.AGAINST]
        warnings = [item for item in evidence if item.evidence_type is EvidenceType.WARNING]

        weighted_rows = []
        for item in evidence:
            source_key = _canonical_source(item.source)
            raw_weight = self._source_weights.get(source_key, max(0.0, float(item.weight)))
            weighted_rows.append(
                {
                    "evidence": item,
                    "source_key": source_key,
                    "raw_weight": max(0.0, raw_weight),
                }
            )

        total_weight = sum(row["raw_weight"] for row in weighted_rows)
        if total_weight <= 0.0:
            total_weight = float(len(weighted_rows))
            for row in weighted_rows:
                row["raw_weight"] = 1.0

        score_breakdown: list[dict[str, Any]] = []
        positive = 0.0
        negative = 0.0
        for row in weighted_rows:
            item: Evidence = row["evidence"]
            normalized_weight = row["raw_weight"] / total_weight
            base_impact = _clip(item.score) * _clip(item.confidence) * normalized_weight
            if item.evidence_type is EvidenceType.SUPPORT:
                signed_impact = base_impact
                positive += base_impact
            else:
                signed_impact = -base_impact
                negative += base_impact
            score_breakdown.append(
                {
                    "name": item.name,
                    "source": item.source,
                    "source_key": row["source_key"],
                    "evidence_type": item.evidence_type.value,
                    "score": _clip(item.score),
                    "confidence": _clip(item.confidence),
                    "weight": round(normalized_weight, 8),
                    "impact_on_score": round(signed_impact, 8),
                    "is_critical": item.is_critical,
                }
            )

        raw_score = _clip(positive - negative + self._empty_score)
        conflict_result = self._conflict_resolver.evaluate(evidence)
        final_score = _clip(raw_score - conflict_result.conflict_penalty)
        result = ConfluenceResult(
            raw_score=round(raw_score, 8),
            evidence_for=evidence_for,
            evidence_against=evidence_against,
            warnings=warnings,
            score_breakdown=score_breakdown,
            normalized_score=round(final_score, 8),
            final_score=round(final_score, 8),
            conflict_penalty=round(conflict_result.conflict_penalty, 8),
            conflict_result=conflict_result,
        )
        self._append_trace(trace, result)
        return result

    def _append_trace(self, trace: DecisionTrace | None, result: ConfluenceResult) -> None:
        """Append confluence step to a decision trace."""
        if trace is None:
            return
        trace.add_step(
            step_name="confluence_score",
            input_score=0.0,
            output_score=result.normalized_score,
            passed=result.normalized_score >= max(self._empty_score, 0.5),
            details={
                "raw_score": result.raw_score,
                "final_score": result.final_score,
                "conflict_penalty": result.conflict_penalty,
                "normalized_score": result.normalized_score,
                "evidence_for_count": len(result.evidence_for),
                "evidence_against_count": len(result.evidence_against),
                "warnings_count": len(result.warnings),
                "score_breakdown": result.score_breakdown,
            },
            warnings=[
                str(item.reason)
                for item in result.warnings
            ],
        )
        if result.conflict_result is None:
            return
        trace.add_step(
            step_name="conflict_resolution",
            input_score=result.raw_score,
            output_score=result.final_score,
            passed=result.conflict_result.recommended_action.value != "WAIT",
            details=result.conflict_result.to_dict(),
            warnings=list(result.conflict_result.conflict_reasons),
        )
        if result.conflict_result.recommended_action.value == "WAIT":
            trace.add_warning("Conflict resolver recommends WAIT.")


def _canonical_source(source: str) -> str:
    normalized = source.strip().lower().replace("-", "_").replace(" ", "_")
    if normalized in DEFAULT_SOURCE_WEIGHTS:
        return normalized
    if "regime" in normalized:
        return "regime_alignment"
    if "structure" in normalized:
        return "market_structure"
    if "price_action" in normalized or "candle" in normalized:
        return "price_action"
    if "ict" in normalized:
        return "ict_confluence"
    if "volume" in normalized:
        return "volume_confirmation"
    if "multi_timeframe" in normalized or "mtf" in normalized or "higher_timeframe" in normalized:
        return "multi_timeframe_alignment"
    if "model" in normalized or "probability" in normalized:
        return "model_probability"
    if "risk_reward" in normalized:
        return "risk_reward_quality"
    return normalized


def _clip(value: float) -> float:
    return max(0.0, min(float(value), 1.0))
