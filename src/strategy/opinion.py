"""Standard StrategyOpinion helpers for strategy/agent outputs."""

from __future__ import annotations

from collections.abc import Sequence

from reasoning.evidence import (
    Evidence,
    EvidenceDirection,
    support as support_evidence,
    warning as warning_evidence,
)
from signals.models import SetupGrade, SignalType, StrategyOpinion, StrategyType


def build_strategy_opinion(
    *,
    strategy_type: StrategyType | str,
    suggested_signal: SignalType | str,
    score: float,
    confidence: float,
    setup_grade: SetupGrade | str | None = None,
    evidence: Sequence[Evidence] | None = None,
    reasons: Sequence[str] | None = None,
    warnings: Sequence[str] | None = None,
    passed_conditions: Sequence[str] | None = None,
    failed_conditions: Sequence[str] | None = None,
    suggested_size_multiplier: float | None = None,
) -> StrategyOpinion:
    """Build a normalized StrategyOpinion without making a final decision."""
    strategy = _strategy(strategy_type)
    signal = _signal(suggested_signal)
    normalized_score = round(_clip(score), 4)
    normalized_confidence = round(_clip(confidence), 4)
    reason_list = list(reasons or [])
    warning_list = list(warnings or [])
    evidence_list = list(
        evidence
        if evidence is not None
        else _default_evidence(
            strategy,
            signal,
            normalized_score,
            normalized_confidence,
            reason_list,
            warning_list,
        )
    )
    return StrategyOpinion(
        strategy_type=strategy,
        suggested_signal=signal,
        score=normalized_score,
        confidence=normalized_confidence,
        setup_grade=_grade_value(setup_grade) if setup_grade is not None else grade_from_score(normalized_score),
        evidence=evidence_list,
        reasons=reason_list,
        warnings=warning_list,
        passed_conditions=list(passed_conditions or []),
        failed_conditions=list(failed_conditions or []),
        suggested_size_multiplier=round(
            _clip(
                _size_multiplier(normalized_score, warning_list)
                if suggested_size_multiplier is None
                else suggested_size_multiplier
            ),
            4,
        ),
    )


def wait_opinion(
    *,
    strategy_type: StrategyType | str,
    score: float,
    reasons: Sequence[str],
    warnings: Sequence[str] | None = None,
    failed_conditions: Sequence[str] | None = None,
) -> StrategyOpinion:
    """Build a standardized WAIT opinion for weak strategy setups."""
    normalized_score = _clip(score)
    return build_strategy_opinion(
        strategy_type=strategy_type,
        suggested_signal=SignalType.WAIT,
        score=normalized_score,
        confidence=normalized_score,
        reasons=reasons,
        warnings=warnings or [],
        failed_conditions=failed_conditions or reasons,
    )


def opinion_to_dict(opinion: StrategyOpinion) -> dict[str, object]:
    """Serialize an opinion for diagnostics and API payloads."""
    return {
        "strategy_type": opinion.strategy_type.value,
        "suggested_signal": opinion.suggested_signal.value,
        "score": opinion.score,
        "confidence": opinion.confidence,
        "setup_grade": opinion.setup_grade.value,
        "evidence": [item.to_dict() for item in opinion.evidence],
        "reasons": opinion.reasons,
        "warnings": opinion.warnings,
        "passed_conditions": opinion.passed_conditions,
        "failed_conditions": opinion.failed_conditions,
        "suggested_size_multiplier": opinion.suggested_size_multiplier,
    }


def grade_from_score(score: float) -> SetupGrade:
    """Convert numeric score into setup grade."""
    value = _clip(score)
    if value >= 0.9:
        return SetupGrade.A_PLUS
    if value >= 0.8:
        return SetupGrade.A
    if value >= 0.65:
        return SetupGrade.B
    if value >= 0.5:
        return SetupGrade.C
    return SetupGrade.D


def _default_evidence(
    strategy: StrategyType,
    signal: SignalType,
    score: float,
    confidence: float,
    reasons: list[str],
    warnings: list[str],
) -> list[Evidence]:
    source = f"strategy.{strategy.value.lower()}"
    direction = _evidence_direction(signal)
    evidence: list[Evidence] = []
    for reason in reasons:
        if signal is SignalType.WAIT:
            evidence.append(
                warning_evidence(
                    name="Strategy Wait Reason",
                    source=source,
                    reason=reason,
                    score=max(0.1, 1.0 - score),
                    confidence=max(confidence, 0.5),
                    weight=0.7,
                    direction=EvidenceDirection.NEUTRAL,
                )
            )
        else:
            evidence.append(
                support_evidence(
                    name="Strategy Opinion",
                    source=source,
                    direction=direction,
                    score=score,
                    confidence=confidence,
                    weight=0.8,
                    reason=reason,
                )
            )
    for item in warnings:
        evidence.append(
            warning_evidence(
                name="Strategy Warning",
                source=source,
                reason=item,
                score=max(0.1, 1.0 - score),
                confidence=max(confidence, 0.5),
                weight=0.6,
                direction=direction,
            )
        )
    return evidence


def _evidence_direction(signal: SignalType) -> EvidenceDirection:
    if signal is SignalType.BUY:
        return EvidenceDirection.BUY
    if signal is SignalType.SELL:
        return EvidenceDirection.SELL
    return EvidenceDirection.NEUTRAL


def _strategy(value: StrategyType | str) -> StrategyType:
    if isinstance(value, StrategyType):
        return value
    return StrategyType(str(value).upper())


def _signal(value: SignalType | str) -> SignalType:
    if isinstance(value, SignalType):
        return value
    return SignalType(str(value).upper())


def _grade_value(value: SetupGrade | str) -> SetupGrade:
    if isinstance(value, SetupGrade):
        return value
    return SetupGrade(str(value).upper())


def _size_multiplier(score: float, warnings: list[str]) -> float:
    if score >= 0.8 and not warnings:
        return 1.0
    if score >= 0.65:
        return 0.8 if warnings else 0.9
    if score >= 0.5:
        return 0.6
    return 0.0 if score < 0.35 else 0.4


def _clip(value: float) -> float:
    return max(0.0, min(float(value), 1.0))
