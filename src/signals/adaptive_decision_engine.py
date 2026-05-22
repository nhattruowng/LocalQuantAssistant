"""Adaptive decision engine for selecting final signal from strategy opinions."""

from __future__ import annotations

from config.settings import AdaptiveStrategySettings
from signals.models import (
    AdaptiveDecision,
    AdaptiveThresholdContext,
    DecisionConflictResult,
    SetupQualityGrade,
    SignalType,
    StrategyOpinion,
    StrategyType,
)
from signals.wait_reason import WaitReason
from strategy.memory import MemoryAdjustment, StrategyPerformanceMemory


class AdaptiveDecisionEngine:
    """Selects BUY/SELL/WAIT from soft strategy opinions using dynamic thresholds."""

    def __init__(self, settings: AdaptiveStrategySettings) -> None:
        self._settings = settings

    def decide(
        self,
        opinions: list[StrategyOpinion],
        threshold_context: AdaptiveThresholdContext,
        strategy_memory: StrategyPerformanceMemory | None = None,
    ) -> AdaptiveDecision:
        """Return the final adaptive decision."""
        threshold, threshold_reasons = self._adaptive_threshold(threshold_context)
        opinions, memory_adjustments = self._apply_memory(
            opinions,
            threshold_context,
            strategy_memory,
        )
        memory_threshold_adjustment = sum(
            adjustment.threshold_adjustment for adjustment in memory_adjustments
        )
        if memory_threshold_adjustment > 0:
            threshold = round(min(0.95, threshold + memory_threshold_adjustment), 4)
            threshold_reasons.append(
                f"Strategy memory increased threshold by {memory_threshold_adjustment:.3f}."
            )
        ordered = sorted(opinions, key=lambda opinion: opinion.score, reverse=True)
        actionable = [
            opinion
            for opinion in ordered
            if opinion.suggested_signal is not SignalType.WAIT
            and opinion.score >= self._settings.min_opinion_score
        ]
        conflict = self._conflict(actionable)
        rejected = [
            opinion
            for opinion in ordered
            if opinion not in actionable
        ]

        if not actionable:
            return self._wait(
                selected=None,
                rejected=ordered,
                threshold=threshold,
                score=0.0,
                confidence=0.0,
                quality=SetupQualityGrade.D,
                reasons=[*threshold_reasons, "No strategy opinion met min_opinion_score."],
                warnings=[],
                conflict=conflict,
                why_wait="No actionable strategy opinion.",
                wait_reason=WaitReason.WAIT_LOW_CONFIDENCE,
                memory_adjustments=memory_adjustments,
            )

        top = actionable[0]
        quality = _setup_quality(top.score, top.confidence, top.warnings)
        warnings = [*top.warnings]
        reasons = [
            *threshold_reasons,
            f"Selected {top.strategy_type.value} with score {top.score:.4f}.",
        ]

        if conflict.has_conflict:
            return self._wait(
                selected=top,
                rejected=[*rejected, *actionable[1:]],
                threshold=threshold,
                score=top.score,
                confidence=top.confidence,
                quality=quality,
                reasons=[*reasons, conflict.reason or "Conflicting BUY/SELL opinions."],
                warnings=warnings,
                conflict=conflict,
                why_wait="BUY/SELL opinions conflict with a small score gap.",
                wait_reason=WaitReason.WAIT_STRATEGY_CONFLICT,
                memory_adjustments=memory_adjustments,
            )
        if top.score < threshold:
            return self._wait(
                selected=top,
                rejected=[*rejected, *actionable[1:]],
                threshold=threshold,
                score=top.score,
                confidence=top.confidence,
                quality=quality,
                reasons=[*reasons, f"Score {top.score:.4f} is below adaptive threshold {threshold:.4f}."],
                warnings=warnings,
                conflict=conflict,
                why_wait="Selected opinion score is below adaptive threshold.",
                wait_reason=WaitReason.WAIT_LOW_CONFIDENCE,
                memory_adjustments=memory_adjustments,
            )
        if quality is SetupQualityGrade.D:
            return self._wait(
                selected=top,
                rejected=[*rejected, *actionable[1:]],
                threshold=threshold,
                score=top.score,
                confidence=top.confidence,
                quality=quality,
                reasons=[*reasons, "Setup quality is D."],
                warnings=warnings,
                conflict=conflict,
                why_wait="Setup quality is D.",
                wait_reason=WaitReason.WAIT_NO_CLEAR_SETUP,
                memory_adjustments=memory_adjustments,
            )
        if quality is SetupQualityGrade.C and not self._settings.allow_grade_c_signal:
            return self._wait(
                selected=top,
                rejected=[*rejected, *actionable[1:]],
                threshold=threshold,
                score=top.score,
                confidence=top.confidence,
                quality=quality,
                reasons=[*reasons, "Setup quality is C and grade C signals are disabled."],
                warnings=warnings,
                conflict=conflict,
                why_wait="Setup quality C is not allowed by config.",
                wait_reason=WaitReason.WAIT_NO_CLEAR_SETUP,
                memory_adjustments=memory_adjustments,
            )

        if quality is SetupQualityGrade.C:
            warnings.append("Setup quality is C; trade should be treated as reduced conviction.")
        return AdaptiveDecision(
            final_signal=top.suggested_signal,
            selected_strategy=top.strategy_type,
            selected_opinion=top,
            rejected_opinions=[*rejected, *actionable[1:]],
            adaptive_threshold=round(threshold, 4),
            final_score=top.score,
            final_confidence=_adjust_confidence(top.confidence, threshold_context),
            setup_quality=quality,
            decision_reasons=reasons,
            decision_warnings=warnings,
            size_multiplier=top.suggested_size_multiplier,
            conflict_result=conflict,
            memory_adjustments=memory_adjustments,
            wait_reason=None,
        )

    def _adaptive_threshold(
        self,
        context: AdaptiveThresholdContext,
    ) -> tuple[float, list[str]]:
        """Calculate dynamic threshold and explanatory reasons."""
        threshold = self._settings.base_threshold
        reasons = [f"Base adaptive threshold is {threshold:.2f}."]
        if context.regime_confidence < 0.65:
            adjustment = (0.65 - context.regime_confidence) * 0.25
            threshold += adjustment
            reasons.append(f"Regime confidence is low; threshold increased by {adjustment:.3f}.")
        if context.uncertainty_score >= self._settings.high_uncertainty_threshold:
            adjustment = (context.uncertainty_score - self._settings.high_uncertainty_threshold) * 0.20
            threshold += adjustment
            reasons.append(f"Uncertainty is high; threshold increased by {adjustment:.3f}.")
        if context.volatility_level == "HIGH":
            threshold += 0.05
            reasons.append("High volatility increased threshold by 0.050.")
        elif context.volatility_level == "EXTREME":
            threshold += 0.10
            reasons.append("Extreme volatility increased threshold by 0.100.")
        if context.higher_timeframe_conflict:
            threshold += 0.08
            reasons.append("Higher timeframe conflict increased threshold by 0.080.")
        if context.recent_strategy_performance is not None and context.recent_strategy_performance < 0:
            threshold += min(0.08, abs(context.recent_strategy_performance) * 0.10)
            reasons.append("Recent strategy performance is weak; threshold increased.")
        if self._settings.require_calibrated_probability and context.probability_source != "calibrated":
            threshold += 0.06
            reasons.append("Calibrated probability is required but unavailable; threshold increased.")
        if context.volume_quality >= 0.85:
            threshold -= 0.03
            reasons.append("Strong volume confirmation reduced threshold by 0.030.")
        if context.trend_alignment >= 0.85:
            threshold -= 0.03
            reasons.append("Clear trend alignment reduced threshold by 0.030.")
        return round(max(0.0, min(threshold, 0.95)), 4), reasons

    def _conflict(
        self,
        actionable: list[StrategyOpinion],
    ) -> DecisionConflictResult:
        """Detect close BUY/SELL conflict between top opinions."""
        if len(actionable) < 2:
            return DecisionConflictResult(has_conflict=False)
        top = actionable[0]
        second = actionable[1]
        signals = {top.suggested_signal, second.suggested_signal}
        gap = abs(top.score - second.score)
        has_conflict = signals == {SignalType.BUY, SignalType.SELL} and gap < self._settings.conflict_margin
        return DecisionConflictResult(
            has_conflict=has_conflict,
            top_signal=top.suggested_signal,
            second_signal=second.suggested_signal,
            score_gap=round(gap, 4),
            reason=(
                f"Top BUY/SELL opinions conflict with score gap {gap:.4f}."
                if has_conflict
                else None
            ),
        )

    def _apply_memory(
        self,
        opinions: list[StrategyOpinion],
        context: AdaptiveThresholdContext,
        memory: StrategyPerformanceMemory | None,
    ) -> tuple[list[StrategyOpinion], list[MemoryAdjustment]]:
        """Apply bounded strategy memory adjustments to opinions."""
        if (
            memory is None
            or context.symbol is None
            or context.timeframe is None
            or context.regime is None
        ):
            return opinions, []
        adjusted: list[StrategyOpinion] = []
        adjustments: list[MemoryAdjustment] = []
        for opinion in opinions:
            adjusted_opinion, adjustment = memory.apply_to_opinion(
                symbol=context.symbol,
                timeframe=context.timeframe,
                regime=context.regime,
                opinion=opinion,
                settings=self._settings,
            )
            adjusted.append(adjusted_opinion)
            if adjustment is not None:
                adjustments.append(adjustment)
        return adjusted, adjustments

    def _wait(
        self,
        selected: StrategyOpinion | None,
        rejected: list[StrategyOpinion],
        threshold: float,
        score: float,
        confidence: float,
        quality: SetupQualityGrade,
        reasons: list[str],
        warnings: list[str],
        conflict: DecisionConflictResult,
        why_wait: str,
        wait_reason: WaitReason,
        memory_adjustments: list[MemoryAdjustment] | None = None,
    ) -> AdaptiveDecision:
        """Build a WAIT adaptive decision."""
        return AdaptiveDecision(
            final_signal=SignalType.WAIT,
            selected_strategy=selected.strategy_type if selected else StrategyType.NONE,
            selected_opinion=selected,
            rejected_opinions=rejected,
            adaptive_threshold=round(threshold, 4),
            final_score=round(score, 4),
            final_confidence=round(confidence, 4),
            setup_quality=quality,
            decision_reasons=[*reasons, why_wait],
            decision_warnings=warnings,
            size_multiplier=0.0,
            conflict_result=conflict,
            memory_adjustments=list(memory_adjustments or []),
            wait_reason=wait_reason.value,
        )


def adaptive_decision_to_dict(decision: AdaptiveDecision) -> dict[str, object]:
    """Serialize adaptive decision diagnostics."""
    return {
        "final_signal": decision.final_signal.value,
        "selected_strategy": decision.selected_strategy.value,
        "selected_opinion": _opinion_to_dict(decision.selected_opinion),
        "rejected_opinions": [_opinion_to_dict(opinion) for opinion in decision.rejected_opinions],
        "adaptive_threshold": decision.adaptive_threshold,
        "final_score": decision.final_score,
        "final_confidence": decision.final_confidence,
        "setup_quality": decision.setup_quality.value,
        "decision_reasons": decision.decision_reasons,
        "decision_warnings": decision.decision_warnings,
        "size_multiplier": decision.size_multiplier,
        "memory_adjustments": [
            adjustment.to_dict() if hasattr(adjustment, "to_dict") else adjustment
            for adjustment in decision.memory_adjustments
        ],
        "conflict_result": {
            "has_conflict": decision.conflict_result.has_conflict,
            "top_signal": decision.conflict_result.top_signal.value if decision.conflict_result.top_signal else None,
            "second_signal": decision.conflict_result.second_signal.value if decision.conflict_result.second_signal else None,
            "score_gap": decision.conflict_result.score_gap,
            "reason": decision.conflict_result.reason,
        },
        "why_wait": _why_wait(decision),
        "wait_reason": decision.wait_reason,
    }


def _opinion_to_dict(opinion: StrategyOpinion | None) -> dict[str, object] | None:
    """Serialize one strategy opinion."""
    if opinion is None:
        return None
    return {
        "strategy_type": opinion.strategy_type.value,
        "suggested_signal": opinion.suggested_signal.value,
        "score": opinion.score,
        "confidence": opinion.confidence,
        "setup_grade": opinion.setup_grade.value,
        "reasons": opinion.reasons,
        "warnings": opinion.warnings,
        "passed_conditions": opinion.passed_conditions,
        "failed_conditions": opinion.failed_conditions,
        "suggested_size_multiplier": opinion.suggested_size_multiplier,
    }


def _setup_quality(
    score: float,
    confidence: float,
    warnings: list[str],
) -> SetupQualityGrade:
    """Convert score/confidence/warnings into final setup quality."""
    if score >= 0.85 and confidence >= 0.75 and not warnings:
        return SetupQualityGrade.A_PLUS
    if score >= 0.78:
        return SetupQualityGrade.A
    if score >= 0.68:
        return SetupQualityGrade.B
    if score >= 0.58:
        return SetupQualityGrade.C
    return SetupQualityGrade.D


def _adjust_confidence(
    confidence: float,
    context: AdaptiveThresholdContext,
) -> float:
    """Reduce confidence when context is unstable."""
    adjusted = confidence
    adjusted *= max(0.5, min(context.regime_confidence, 1.0))
    adjusted *= max(0.5, 1.0 - context.uncertainty_score * 0.35)
    if context.volatility_level == "HIGH":
        adjusted *= 0.95
    elif context.volatility_level == "EXTREME":
        adjusted *= 0.90
    if context.higher_timeframe_conflict:
        adjusted *= 0.90
    return round(max(0.0, min(adjusted, 1.0)), 4)


def _why_wait(decision: AdaptiveDecision) -> str | None:
    """Return the most relevant WAIT reason."""
    if decision.final_signal is not SignalType.WAIT:
        return None
    return decision.decision_reasons[-1] if decision.decision_reasons else "Adaptive decision returned WAIT."
