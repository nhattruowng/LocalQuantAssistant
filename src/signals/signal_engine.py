"""Signal engine that converts model probabilities into trade setups."""

from __future__ import annotations

from dataclasses import replace
import logging
import json
from typing import Mapping

from config.settings import Settings
from data.data_quality import DataQualityAction, DataQualityReport, DataQualitySeverity
from regime.market_regime import MarketRegime
from reasoning.market_reasoning_brain import MarketReasoningBrain, MarketReasoningContext
from risk.risk_guard import RiskGuard, RiskGuardContext
from risk.risk_manager import RiskManager
from risk.safety_filters import SafetyFilterEngine
from signals.adaptive_decision_engine import (
    AdaptiveDecisionEngine,
    adaptive_decision_to_dict,
)
from signals.decision_trace import DecisionTrace
from signals.models import (
    AdaptiveThresholdContext,
    RiskPlan,
    SignalContext,
    SignalType,
    StrategyDecision,
    StrategyEnsembleResult,
    StrategyScore,
    StrategyType,
    TradeSetup,
)
from signals.wait_reason import WaitReason, infer_wait_reason, normalize_wait_reason
from strategy.base import Strategy
from strategy.breakout import BreakoutStrategy
from strategy.mean_reversion import MeanReversionStrategy
from strategy.memory import StrategyPerformanceMemory
from strategy.opinion_agents import (
    BreakoutOpinionAgent,
    MeanReversionOpinionAgent,
    TrendFollowingOpinionAgent,
    opinion_to_dict,
)
from strategy.trend_following import TrendFollowingStrategy


class SignalEngine:
    """Builds conservative BUY/SELL/WAIT setups from model and market context."""

    def __init__(
        self,
        settings: Settings,
        risk_manager: RiskManager | None = None,
        risk_guard: RiskGuard | None = None,
        risk_guard_context: RiskGuardContext | None = None,
        strategy_memory: StrategyPerformanceMemory | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._settings = settings
        self._risk_manager = risk_manager or RiskManager(settings.risk)
        self._risk_guard = risk_guard
        self._risk_guard_context = risk_guard_context
        self._strategy_memory = strategy_memory
        self._logger = logger or logging.getLogger("localquant.signal")
        self._market_reasoning_brain = MarketReasoningBrain(settings.reasoning_brain)
        self._strategies: dict[str, Strategy] = {
            MarketRegime.UPTREND.value: TrendFollowingStrategy(settings.signal),
            MarketRegime.DOWNTREND.value: TrendFollowingStrategy(settings.signal),
            MarketRegime.BREAKOUT_UP.value: BreakoutStrategy(settings.signal),
            MarketRegime.BREAKOUT_DOWN.value: BreakoutStrategy(settings.signal),
            MarketRegime.SIDEWAY.value: MeanReversionStrategy(settings.signal),
        }
        self._opinion_agents = [
            TrendFollowingOpinionAgent(settings.signal),
            BreakoutOpinionAgent(settings.signal),
            MeanReversionOpinionAgent(settings.signal),
        ]

    def generate(
        self,
        symbol: str,
        timeframe: str,
        timestamp,
        market_regime: MarketRegime | str,
        features: Mapping[str, float],
        probabilities: Mapping[str | SignalType, float],
        raw_probabilities: Mapping[str | SignalType, float] | None = None,
        calibrated_probabilities: Mapping[str | SignalType, float] | None = None,
        probability_source: str = "raw",
        model_scope_used: str | None = None,
        model_version: str | None = None,
        fallback_reason: str | None = None,
        higher_timeframe_features: Mapping[str, Mapping[str, object]] | None = None,
        higher_timeframe_regimes: Mapping[str, MarketRegime | str] | None = None,
        multi_timeframe_enabled: bool | None = None,
        data_quality_report: DataQualityReport | Mapping[str, object] | None = None,
    ) -> TradeSetup:
        """Generate a complete trade setup recommendation."""
        higher_features = dict(higher_timeframe_features or {})
        higher_regimes = dict(higher_timeframe_regimes or _higher_timeframe_regimes(higher_features))
        effective_mtf_enabled = bool(
            self._settings.signal.multi_timeframe
            and self._settings.signal.multi_timeframe.enabled
        )
        if multi_timeframe_enabled is not None:
            effective_mtf_enabled = bool(multi_timeframe_enabled)
        context = SignalContext(
            symbol=symbol,
            timeframe=timeframe,
            timestamp=timestamp,
            market_regime=market_regime,
            features=features,
            probabilities=probabilities,
            primary_timeframe=timeframe,
            higher_timeframes=tuple(higher_features.keys()),
            primary_features=features,
            higher_timeframe_features=higher_features,
            primary_regime=market_regime,
            higher_timeframe_regimes=higher_regimes,
            model_prediction={
                "probabilities": _probability_values(probabilities) or {},
                "raw_probabilities": _probability_values(raw_probabilities),
                "calibrated_probabilities": _probability_values(calibrated_probabilities),
                "probability_source": probability_source,
            },
            explanation_context={
                "multi_timeframe_enabled": effective_mtf_enabled,
            },
            regime_scores=_regime_scores(features),
            regime_confidence=_regime_confidence(features),
            transition_warning=_transition_warning(features),
            raw_probabilities=raw_probabilities,
            calibrated_probabilities=calibrated_probabilities,
            probability_source=probability_source,
        )
        model_selection = {
            "model_scope_used": model_scope_used,
            "model_version": model_version,
            "fallback_reason": fallback_reason,
        }
        data_quality = _coerce_data_quality_report(
            data_quality_report
            or features.get("data_quality_report")
            or features.get("data_quality")
        )
        base_diagnostics: dict[str, object] = {}
        if data_quality is not None:
            base_diagnostics["data_quality"] = data_quality.to_dict()
        if _should_hard_block_data_quality(self._settings, data_quality):
            return self._wait(
                context,
                [
                    "Data quality gate blocked signal: "
                    + "; ".join(data_quality.issues or ["severity is HIGH."]),
                ],
                StrategyType.NONE,
                diagnostics={
                    **base_diagnostics,
                    "blocked_by_risk_guard": True,
                    "blocked_by_data_quality": True,
                },
                model_selection=model_selection,
                wait_reason=WaitReason.WAIT_DATA_QUALITY.value,
            )

        diagnostics: dict[str, object] | None = dict(base_diagnostics) if base_diagnostics else None
        if self._adaptive_strategy_enabled():
            decision, decision_diagnostics = self._adaptive_decision(context)
            diagnostics = _merge_diagnostics(base_diagnostics, decision_diagnostics)
            if decision is None:
                return self._wait(
                    context,
                    list(diagnostics.get("reasons", ["No adaptive strategy opinion selected."])),
                    StrategyType.NONE,
                    diagnostics=diagnostics,
                    model_selection=model_selection,
                )
        elif self._ensemble_enabled():
            decision, decision_diagnostics = self._ensemble_decision(context)
            diagnostics = _merge_diagnostics(base_diagnostics, decision_diagnostics)
            if decision is None:
                return self._wait(
                    context,
                    list(diagnostics.get("reasons", ["No ensemble strategy selected."])) if diagnostics else ["No ensemble strategy selected."],
                    StrategyType.NONE,
                    diagnostics=diagnostics,
                    model_selection=model_selection,
                )
        else:
            strategy = self._strategy_for(context)
            if strategy is None:
                return self._wait(
                    context,
                    [f"No strategy for regime {context.regime_value()}."],
                    diagnostics=diagnostics,
                    model_selection=model_selection,
                )
            decision = strategy.evaluate(context)

        if decision.signal is SignalType.WAIT:
            return self._wait(
                context,
                decision.reasons,
                decision.strategy,
                diagnostics=diagnostics,
                model_selection=model_selection,
            )

        risk_plan = self._risk_plan_for(context, decision, features, model_selection, diagnostics)
        if isinstance(risk_plan, TradeSetup):
            return risk_plan
        safety = SafetyFilterEngine(self._settings.safety_filters).evaluate(context, decision)
        diagnostics = {
            **(diagnostics or {}),
            "safety_filters": safety.filters,
            "safety_filter_reasons": safety.reasons,
            "safety_filter_warnings": safety.warnings,
            "mean_reversion_danger_score": safety.mean_reversion_danger_score,
            "breakout_fakeout_score": safety.breakout_fakeout_score,
        }
        if safety.blocked:
            return self._wait(
                context,
                [*decision.reasons, *safety.reasons],
                decision.strategy,
                risk_plan,
                diagnostics={
                    **diagnostics,
                    "blocked_by_risk_guard": True,
                    "blocked_by_safety_filter": True,
                },
                model_selection=model_selection,
            )
        risk_plan = self._apply_dynamic_position_sizing(context, decision, risk_plan, diagnostics)
        if not self._is_risk_acceptable(risk_plan):
            return self._wait(
                context,
                [
                    *decision.reasons,
                    (
                        f"Risk/reward {risk_plan.risk_reward:.2f} is below "
                        f"{self._min_risk_reward():.2f}."
                    ),
                ],
                decision.strategy,
                risk_plan,
                diagnostics={
                    **(diagnostics or {}),
                    "blocked_by_risk_guard": True,
                    "min_risk_reward": self._min_risk_reward(),
                },
                model_selection=model_selection,
            )

        setup = self._approved_setup(context, decision, risk_plan, diagnostics, model_selection)
        if self._risk_guard is not None and self._risk_guard_context is not None:
            guard = self._risk_guard.evaluate(setup, self._risk_guard_context)
            if not guard.allowed:
                guard_wait_reason = (
                    WaitReason.WAIT_DATA_QUALITY.value
                    if any("data quality" in reason.lower() for reason in guard.reasons)
                    else None
                )
                return self._wait(
                    context,
                    guard.reasons,
                    decision.strategy,
                    risk_plan,
                    diagnostics={
                        **(diagnostics or {}),
                        "risk_guard_state": guard.state.value,
                        "risk_guard_reasons": guard.reasons,
                        "blocked_by_risk_guard": True,
                    },
                    model_selection=model_selection,
                    wait_reason=guard_wait_reason,
                )
        return setup

    def _strategy_for(self, context: SignalContext) -> Strategy | None:
        """Return the strategy for the current market regime."""
        return self._strategies.get(context.regime_value())

    def _ensemble_enabled(self) -> bool:
        """Return True when strategy ensemble mode is enabled."""
        ensemble = self._settings.signal.strategy_ensemble
        return bool(ensemble and ensemble.enabled)

    def _adaptive_strategy_enabled(self) -> bool:
        """Return True when Strategy Opinion Ensemble is enabled."""
        return bool(
            self._settings.adaptive_strategy.enabled
            or self._settings.market_regime.adaptive_strategy_enabled
        )

    def _reasoning_brain_enabled(self) -> bool:
        """Return True when market reasoning brain is enabled."""
        return bool(self._settings.reasoning_brain.enabled)

    def _adaptive_decision(
        self,
        context: SignalContext,
    ) -> tuple[StrategyDecision | None, dict[str, object]]:
        """Evaluate all strategy opinions and let AdaptiveDecisionEngine select."""
        opinions = [agent.evaluate(context) for agent in self._opinion_agents]
        decision = AdaptiveDecisionEngine(self._settings.adaptive_strategy).decide(
            opinions,
            _adaptive_threshold_context(context),
            strategy_memory=self._strategy_memory,
        )
        decision_payload = adaptive_decision_to_dict(decision)
        diagnostics: dict[str, object] = {
            "adaptive_strategy": True,
            "strategy_opinions": [opinion_to_dict(opinion) for opinion in opinions],
            "adaptive_decision": decision_payload,
            "adaptive_threshold": decision.adaptive_threshold,
            "setup_quality": decision.setup_quality.value,
            "conflict_result": decision_payload["conflict_result"],
            "decision_warnings": decision.decision_warnings,
            "why_wait": decision_payload["why_wait"],
            "rejected_strategies": [opinion_to_dict(opinion) for opinion in decision.rejected_opinions],
            "memory_adjustments": decision_payload["memory_adjustments"],
            "reasons": decision.decision_reasons,
            "wait_reason": decision.wait_reason,
        }
        if decision.selected_opinion is not None:
            top = decision.selected_opinion
            diagnostics["selected_strategy_opinion"] = opinion_to_dict(top)
            diagnostics["selected_strategy"] = {
                "strategy_type": top.strategy_type.value,
                "signal": top.suggested_signal.value,
                "score": top.score,
                "confidence": top.confidence,
                "reasons": top.reasons,
                "failed_conditions": top.failed_conditions,
            }
        if decision.final_signal is SignalType.WAIT:
            return None, diagnostics

        top = decision.selected_opinion
        if top is None:
            return None, diagnostics
        return StrategyDecision(
            signal=decision.final_signal,
            strategy=decision.selected_strategy,
            model_probability=context.probability(decision.final_signal),
            trend_score=decision.final_score,
            indicator_score=decision.final_score,
            volume_score=decision.final_score,
            reasons=[
                *decision.decision_reasons,
                *[f"Warning: {warning}" for warning in decision.decision_warnings],
            ],
            score=decision.final_score,
            confidence=decision.final_confidence,
            failed_conditions=top.failed_conditions,
        ), diagnostics

    def _ensemble_decision(
        self,
        context: SignalContext,
    ) -> tuple[StrategyDecision | None, dict[str, object]]:
        """Evaluate multiple strategies and select the strongest candidate."""
        ensemble = self._settings.signal.strategy_ensemble
        if ensemble is None:
            raise ValueError("Strategy ensemble settings are required.")
        decisions = self._ensemble_candidates(context)
        scores = [_strategy_score(decision) for decision in decisions]
        actionable = [
            (decision, score)
            for decision, score in zip(decisions, scores, strict=False)
            if decision.signal is not SignalType.WAIT and score.score >= ensemble.min_strategy_score
        ]
        rejected = [
            score
            for score in scores
            if score.signal is SignalType.WAIT or score.score < ensemble.min_strategy_score
        ]
        if not actionable:
            result = StrategyEnsembleResult(
                selected=None,
                candidates=scores,
                rejected=rejected,
                reasons=["No strategy candidate passed ensemble threshold."],
            )
            return None, _ensemble_diagnostics(result, context)

        actionable.sort(key=lambda item: item[1].score, reverse=True)
        top_decision, top_score = actionable[0]
        if len(actionable) > 1:
            second_decision, second_score = actionable[1]
            conflict = (
                top_decision.signal is not second_decision.signal
                and {top_decision.signal, second_decision.signal} == {SignalType.BUY, SignalType.SELL}
                and abs(top_score.score - second_score.score) < ensemble.conflict_margin
            )
            if conflict:
                result = StrategyEnsembleResult(
                    selected=None,
                    candidates=scores,
                    rejected=rejected,
                    conflict=True,
                    reasons=[
                        "Top BUY/SELL strategy candidates conflict with a small score margin."
                    ],
                )
                return None, _ensemble_diagnostics(result, context)

        result = StrategyEnsembleResult(
            selected=top_score,
            candidates=scores,
            rejected=rejected,
            reasons=[
                f"Selected {top_score.strategy_type.value} with ensemble score {top_score.score:.4f}."
            ],
        )
        return top_decision, _ensemble_diagnostics(result, context)

    def _ensemble_candidates(self, context: SignalContext) -> list[StrategyDecision]:
        """Run strategy candidates across soft-regime possibilities."""
        return [
            TrendFollowingStrategy(self._settings.signal).evaluate(_with_regime(context, MarketRegime.UPTREND)),
            TrendFollowingStrategy(self._settings.signal).evaluate(_with_regime(context, MarketRegime.DOWNTREND)),
            BreakoutStrategy(self._settings.signal).evaluate(_with_regime(context, MarketRegime.BREAKOUT_UP)),
            BreakoutStrategy(self._settings.signal).evaluate(_with_regime(context, MarketRegime.BREAKOUT_DOWN)),
            MeanReversionStrategy(self._settings.signal).evaluate(_with_regime(context, MarketRegime.SIDEWAY)),
        ]

    def _risk_plan_for(
        self,
        context: SignalContext,
        decision: StrategyDecision,
        features: Mapping[str, float],
        model_selection: dict[str, str | None] | None = None,
        diagnostics: dict[str, object] | None = None,
    ) -> RiskPlan | TradeSetup:
        """Build a risk plan or a WAIT setup when risk planning fails."""
        try:
            risk_plan = self._risk_manager.build_plan(decision.signal, features)
        except (KeyError, ValueError) as error:
            return self._wait(
                context,
                [*decision.reasons, f"Risk plan failed: {error}."],
                decision.strategy,
                diagnostics=diagnostics,
                model_selection=model_selection,
            )

        if risk_plan is None:
            return self._wait(
                context,
                [*decision.reasons, "No risk plan was built."],
                decision.strategy,
                diagnostics=diagnostics,
                model_selection=model_selection,
            )
        return risk_plan

    def _is_risk_acceptable(self, risk_plan: RiskPlan) -> bool:
        """Return True when risk/reward passes the configured gate."""
        return risk_plan.risk_reward >= self._min_risk_reward()

    def _min_risk_reward(self) -> float:
        """Return the effective minimum risk/reward threshold."""
        return max(self._settings.signal.min_risk_reward, self._settings.risk.min_risk_reward)

    def _apply_dynamic_position_sizing(
        self,
        context: SignalContext,
        decision: StrategyDecision,
        risk_plan: RiskPlan,
        diagnostics: dict[str, object] | None,
    ) -> RiskPlan:
        """Apply setup-quality, context, memory, and drawdown sizing multipliers."""
        if not self._settings.risk.dynamic_sizing_enabled:
            return replace(
                risk_plan,
                base_position_size=risk_plan.base_position_size or risk_plan.position_size,
                final_position_size=risk_plan.position_size,
                size_multiplier=1.0,
            )

        setup_quality = str((diagnostics or {}).get("setup_quality") or _quality_from_score(decision.score))
        multipliers = [
            ("setup_quality_multiplier", _setup_quality_multiplier(setup_quality)),
            ("regime_confidence_multiplier", _regime_confidence_multiplier(context.regime_confidence)),
            ("volatility_multiplier", _volatility_multiplier(str((context.primary_features or context.features).get("volatility_level", "NORMAL")))),
            ("memory_performance_multiplier", _memory_performance_multiplier(diagnostics)),
            ("drawdown_multiplier", _drawdown_multiplier(self._risk_guard_context)),
        ]
        size_multiplier = 1.0
        adjustments: list[dict[str, object]] = []
        for name, multiplier in multipliers:
            bounded = max(0.0, min(float(multiplier), 1.0))
            size_multiplier *= bounded
            adjustments.append({"name": name, "multiplier": round(bounded, 4)})
        base_position_size = risk_plan.base_position_size or risk_plan.position_size
        final_position_size = base_position_size * size_multiplier
        notes = list(risk_plan.risk_notes)
        if size_multiplier < 0.999:
            notes.append(f"Dynamic position sizing applied: {size_multiplier:.2f}x.")
        return replace(
            risk_plan,
            position_size=final_position_size,
            base_position_size=base_position_size,
            final_position_size=final_position_size,
            size_multiplier=round(size_multiplier, 4),
            risk_adjustments=adjustments,
            safety_filters=list((diagnostics or {}).get("safety_filters", [])),
            risk_notes=notes,
        )

    def _apply_opinion_size_multiplier(
        self,
        risk_plan: RiskPlan,
        diagnostics: dict[str, object] | None,
    ) -> RiskPlan:
        """Apply adaptive opinion size multiplier to the risk plan."""
        if not diagnostics:
            return risk_plan
        opinion = diagnostics.get("selected_strategy_opinion")
        if not isinstance(opinion, dict):
            return risk_plan
        try:
            multiplier = float(opinion.get("suggested_size_multiplier", 1.0))
        except (TypeError, ValueError):
            return risk_plan
        multiplier = max(0.0, min(multiplier, 1.0))
        if multiplier >= 0.999:
            return risk_plan
        return replace(
            risk_plan,
            position_size=risk_plan.position_size * multiplier,
            risk_notes=[
                *risk_plan.risk_notes,
                f"Adaptive strategy opinion size multiplier applied: {multiplier:.2f}.",
            ],
        )

    def _multi_timeframe_confirmation(
        self,
        context: SignalContext,
        decision: StrategyDecision,
    ) -> dict[str, object]:
        """Apply higher timeframe confirmation to an actionable decision."""
        config = self._settings.signal.multi_timeframe
        enabled_override = context.explanation_context.get("multi_timeframe_enabled")
        enabled = bool(config and config.enabled)
        if enabled_override is not None:
            enabled = bool(enabled_override)
        if not enabled:
            return {
                "blocked": False,
                "confidence_multiplier": 1.0,
                "reasons": [],
                "explanation": self._multi_timeframe_explanation_disabled_or_missing(context),
            }

        configured_timeframes = tuple(config.confirmation_timeframes) if config else ()
        observed_timeframes = tuple(context.higher_timeframes)
        requested_timeframes = configured_timeframes or observed_timeframes
        missing = [
            timeframe
            for timeframe in requested_timeframes
            if timeframe not in context.higher_timeframe_features
        ]
        confirmations: list[dict[str, object]] = []
        conflict_timeframes: list[str] = []
        aligned_timeframes: list[str] = []
        breakout_missing_confirmation: list[str] = []

        for timeframe in observed_timeframes:
            payload = context.higher_timeframe_features.get(timeframe, {})
            regime = _regime_string(
                context.higher_timeframe_regimes.get(
                    timeframe,
                    payload.get("market_regime", "UNKNOWN"),
                )
            )
            confidence = _feature_float(payload, "regime_confidence", 1.0)
            scores = _regime_scores(payload)
            strong_regime_score = max(scores.values(), default=confidence)
            strength = max(confidence, strong_regime_score)
            conflict = _timeframe_conflicts(decision.signal, regime, strength)
            aligned = _timeframe_aligns(decision.signal, regime)
            volume_ratio = _feature_float(payload, "volume_ratio", 0.0)
            atr_percent = _feature_float(payload, "atr_percent", 0.0)
            volatility_score = _feature_float(payload, "volatility_score", atr_percent)
            breakout_confirmed = (
                volume_ratio >= self._settings.signal.breakout_volume_ratio_threshold
                or volatility_score > 0.0
                or atr_percent > 0.0
            )
            if conflict:
                conflict_timeframes.append(timeframe)
            if aligned:
                aligned_timeframes.append(timeframe)
            if (
                decision.strategy is StrategyType.BREAKOUT_CONFIRMATION
                and not breakout_confirmed
            ):
                breakout_missing_confirmation.append(timeframe)
            confirmations.append(
                {
                    "timeframe": timeframe,
                    "regime": regime,
                    "confidence": round(confidence, 4),
                    "strength": round(strength, 4),
                    "aligned": aligned,
                    "conflict": conflict,
                    "volume_ratio": volume_ratio,
                    "atr_percent": atr_percent,
                    "breakout_confirmed": breakout_confirmed,
                }
            )

        reasons: list[str] = []
        multiplier = 1.0
        blocked = False
        if missing and not confirmations:
            reasons.append(
                "Higher timeframe confirmation data is missing; continuing with primary timeframe only."
            )
        if conflict_timeframes:
            reason = (
                "Multi-timeframe conflict: higher timeframe trend opposes "
                f"{decision.signal.value} on {', '.join(conflict_timeframes)}."
            )
            if config and config.require_higher_tf_alignment:
                blocked = True
                reasons.append(f"Blocked by multi-timeframe confirmation: {reason}")
            else:
                penalty = config.conflict_penalty if config else 0.35
                multiplier = min(multiplier, max(0.0, 1.0 - penalty))
                reasons.append(
                    f"{reason} Confidence reduced by {penalty:.0%}."
                )
        elif aligned_timeframes:
            reasons.append(
                "Higher timeframe confirmation aligns with the primary signal."
            )

        if breakout_missing_confirmation:
            penalty = config.conflict_penalty if config else 0.35
            if config and config.require_higher_tf_alignment:
                blocked = True
                reasons.append(
                    "Blocked by multi-timeframe confirmation: breakout lacks higher timeframe volume/volatility confirmation."
                )
            else:
                multiplier = min(multiplier, max(0.0, 1.0 - penalty))
                reasons.append(
                    "Breakout lacks higher timeframe volume/volatility confirmation; confidence was reduced."
                )

        return {
            "blocked": blocked,
            "confidence_multiplier": multiplier,
            "reasons": reasons,
            "explanation": {
                "enabled": True,
                "primary_timeframe": context.primary_timeframe or context.timeframe,
                "confirmation_timeframes": list(requested_timeframes),
                "missing_timeframes": missing,
                "confirmations": confirmations,
                "conflict": bool(conflict_timeframes),
                "aligned_timeframes": aligned_timeframes,
                "confidence_multiplier": round(multiplier, 4),
                "blocked": blocked,
                "reasons": reasons,
            },
        }

    def _multi_timeframe_explanation_disabled_or_missing(
        self,
        context: SignalContext,
    ) -> dict[str, object]:
        """Return a neutral multi-timeframe explanation payload."""
        config = self._settings.signal.multi_timeframe
        enabled_override = context.explanation_context.get("multi_timeframe_enabled")
        enabled = bool(config and config.enabled)
        if enabled_override is not None:
            enabled = bool(enabled_override)
        return {
            "enabled": enabled,
            "primary_timeframe": context.primary_timeframe or context.timeframe,
            "confirmation_timeframes": list(config.confirmation_timeframes if config else ()),
            "missing_timeframes": list(config.confirmation_timeframes if enabled and config else ()),
            "confirmations": [],
            "conflict": False,
            "aligned_timeframes": [],
            "confidence_multiplier": 1.0,
            "blocked": False,
            "reasons": [],
        }

    def _structured_explanation(
        self,
        context: SignalContext,
        final_signal: SignalType,
        strategy: StrategyType,
        reasons: list[str],
        risk_plan: RiskPlan | None,
        diagnostics: dict[str, object] | None,
        mtf_explanation: dict[str, object],
        decision: StrategyDecision | None,
    ) -> dict[str, object]:
        """Build the structured explanation payload returned as explanation_v2."""
        probabilities = _probability_values(context.probabilities) or {}
        reasoning = (
            diagnostics.get("reasoning_decision")
            if diagnostics and isinstance(diagnostics.get("reasoning_decision"), dict)
            else None
        )
        selected_strategy = (
            diagnostics.get("selected_strategy")
            if diagnostics and isinstance(diagnostics.get("selected_strategy"), dict)
            else None
        )
        passed_conditions = (
            decision.reasons
            if decision is not None
            else reasons
        )
        failed_conditions = decision.failed_conditions if decision is not None else []
        summary = _decision_summary(final_signal, strategy, reasons, mtf_explanation)
        higher = [
            {
                "timeframe": timeframe,
                "regime": _regime_string(
                    context.higher_timeframe_regimes.get(
                        timeframe,
                        context.higher_timeframe_features.get(timeframe, {}).get("market_regime", "UNKNOWN"),
                    )
                ),
                "confidence": _feature_float(
                    context.higher_timeframe_features.get(timeframe, {}),
                    "regime_confidence",
                    1.0,
                ),
            }
            for timeframe in context.higher_timeframes
        ]
        return {
            "final_decision": final_signal.value,
            "wait_reason": (diagnostics or {}).get("wait_reason")
            if final_signal is SignalType.WAIT
            else None,
            "summary": summary,
            "regime": {
                "primary": context.regime_value(),
                "confidence": round(context.regime_confidence, 4),
                "regime_scores": dict(context.soft_regime_scores()),
                "uncertainty_score": _feature_float(
                    context.primary_features or context.features,
                    "regime_uncertainty_score",
                    round(1.0 - context.regime_confidence, 4),
                ),
                "transition_warning": context.transition_warning,
                "volatility_level": str(
                    (context.primary_features or context.features).get(
                        "volatility_level",
                        "UNKNOWN",
                    )
                ),
                "transition_warnings": _json_list(
                    (context.primary_features or context.features).get(
                        "market_transition_warnings",
                        [],
                    )
                ),
                "higher_timeframes": higher,
            },
            "strategy": {
                "selected": strategy.value,
                "selected_score": selected_strategy.get("score") if selected_strategy else None,
                "selected_opinion": (diagnostics or {}).get("selected_strategy_opinion"),
                "strategy_opinions": (diagnostics or {}).get("strategy_opinions", []),
                "adaptive_threshold": (diagnostics or {}).get("adaptive_threshold"),
                "conflict_result": (diagnostics or {}).get("conflict_result"),
                "setup_quality": (diagnostics or {}).get("setup_quality"),
                "decision_warnings": (diagnostics or {}).get("decision_warnings", []),
                "why_wait": (diagnostics or {}).get("why_wait"),
                "wait_reason": (diagnostics or {}).get("wait_reason"),
                "setup_type": reasoning.get("setup_type") if reasoning else None,
                "confluence_score": reasoning.get("confluence_score") if reasoning else None,
                "evidence_for": reasoning.get("evidence_for", []) if reasoning else [],
                "evidence_against": reasoning.get("evidence_against", []) if reasoning else [],
                "conflict_level": reasoning.get("conflict_level") if reasoning else None,
                "passed_conditions": list(passed_conditions),
                "failed_conditions": list(failed_conditions),
                "rejected_strategies": (diagnostics or {}).get("rejected_strategies", []),
                "memory_adjustments": (diagnostics or {}).get("memory_adjustments", []),
            },
            "risk": {
                "risk_reward": risk_plan.risk_reward if risk_plan else None,
                "position_size": risk_plan.position_size if risk_plan else None,
                "base_position_size": risk_plan.base_position_size if risk_plan else None,
                "final_position_size": risk_plan.final_position_size if risk_plan else None,
                "size_multiplier": risk_plan.size_multiplier if risk_plan else None,
                "risk_adjustments": risk_plan.risk_adjustments if risk_plan else [],
                "safety_filters": (diagnostics or {}).get("safety_filters", risk_plan.safety_filters if risk_plan else []),
                "mean_reversion_danger_score": (diagnostics or {}).get("mean_reversion_danger_score"),
                "breakout_fakeout_score": (diagnostics or {}).get("breakout_fakeout_score"),
                "blocked_by_risk_guard": bool((diagnostics or {}).get("blocked_by_risk_guard", False)),
                "final_risk_decision": (
                    "BLOCKED"
                    if (diagnostics or {}).get("blocked_by_risk_guard")
                    else "APPROVED"
                    if final_signal is not SignalType.WAIT
                    else "WAIT"
                ),
                "risk_notes": risk_plan.risk_notes if risk_plan else [],
            },
            "model": {
                "probability_source": context.probability_source,
                "buy_probability": probabilities.get(SignalType.BUY.value),
                "sell_probability": probabilities.get(SignalType.SELL.value),
                "wait_probability": probabilities.get(SignalType.WAIT.value),
                "raw_probabilities": _probability_values(context.raw_probabilities),
                "calibrated_probabilities": _probability_values(context.calibrated_probabilities),
            },
            "multi_timeframe": mtf_explanation,
            "data_quality": (diagnostics or {}).get("data_quality"),
            "final_decision_summary": summary,
        }

    def _approved_setup(
        self,
        context: SignalContext,
        decision: StrategyDecision,
        risk_plan: RiskPlan,
        diagnostics: dict[str, object] | None = None,
        model_selection: dict[str, str | None] | None = None,
    ) -> TradeSetup:
        """Create an actionable setup after strategy and risk checks pass."""
        confidence = self._score(decision, risk_plan)
        reasons = list(decision.reasons)
        if self._ensemble_enabled():
            ensemble = self._settings.signal.strategy_ensemble
            if ensemble and context.regime_confidence < ensemble.low_regime_confidence_threshold:
                confidence = round(confidence * max(context.regime_confidence, 0.0), 4)
                reasons.append(
                    f"Regime confidence {context.regime_confidence:.2f} is low; final confidence was reduced."
                )
            if context.transition_warning:
                reasons.append("Market regime transition warning is active.")
            if diagnostics and diagnostics.get("reasons"):
                reasons.extend(str(reason) for reason in diagnostics["reasons"])
        mtf = self._multi_timeframe_confirmation(context, decision)
        reasons.extend(str(reason) for reason in mtf["reasons"])
        if mtf["blocked"]:
            return self._wait(
                context=context,
                reasons=reasons,
                strategy=decision.strategy,
                risk_plan=risk_plan,
                diagnostics={
                    **(diagnostics or {}),
                    "multi_timeframe": mtf["explanation"],
                },
                model_selection=model_selection,
                mtf_explanation=mtf["explanation"],
                wait_reason=WaitReason.WAIT_MTF_CONFLICT.value,
            )
        confidence = round(confidence * float(mtf["confidence_multiplier"]), 4)
        diagnostics_with_mtf = {
            **(diagnostics or {}),
            "multi_timeframe": mtf["explanation"],
        }
        if self._reasoning_brain_enabled():
            reasoning = self._market_reasoning_brain.decide(
                self._reasoning_context(
                    context=context,
                    decision=decision,
                    risk_plan=risk_plan,
                    diagnostics=diagnostics_with_mtf,
                    model_selection=model_selection,
                )
            )
            diagnostics_with_mtf["reasoning_decision"] = reasoning.to_dict()
            if reasoning.final_signal is SignalType.WAIT:
                wait_reasons = [
                    *reasons,
                    f"Reasoning brain setup_type={reasoning.setup_type.value}.",
                    f"Reasoning confluence score {reasoning.confluence_score:.4f} below actionable threshold.",
                    *list(reasoning.warnings),
                ]
                return self._wait(
                    context=context,
                    reasons=wait_reasons,
                    strategy=decision.strategy,
                    risk_plan=risk_plan,
                    diagnostics=diagnostics_with_mtf,
                    model_selection=model_selection,
                    mtf_explanation=mtf["explanation"],
                    wait_reason=reasoning.wait_reason,
                )
            confidence = round(min(confidence, reasoning.confidence), 4)
            risk_plan = self._apply_reasoning_size_multiplier(
                risk_plan,
                reasoning.position_size_multiplier,
            )
        diagnostics_with_mtf["decision_trace"] = self._decision_trace(
            context=context,
            final_signal=decision.signal,
            strategy=decision.strategy,
            reasons=reasons,
            final_confidence=confidence,
            diagnostics=diagnostics_with_mtf,
            wait_reason=None,
            model_selection=model_selection,
        )
        self._logger.info(
            "Signal generated: symbol=%s timeframe=%s signal=%s strategy=%s confidence=%.4f",
            context.symbol,
            context.timeframe,
            decision.signal.value,
            decision.strategy.value,
            confidence,
        )
        return TradeSetup(
            symbol=context.symbol,
            timeframe=context.timeframe,
            timestamp=context.timestamp,
            market_regime=context.regime_value(),
            signal=decision.signal,
            strategy=decision.strategy,
            confidence=confidence,
            entry=risk_plan.entry,
            stop_loss=risk_plan.stop_loss,
            take_profit_1=risk_plan.take_profit_1,
            take_profit_2=risk_plan.take_profit_2,
            risk_reward=risk_plan.risk_reward,
            position_size=risk_plan.position_size,
            reasons=reasons,
            risk_notes=risk_plan.risk_notes,
            explanation_v2=self._structured_explanation(
                context=context,
                final_signal=decision.signal,
                strategy=decision.strategy,
                reasons=reasons,
                risk_plan=risk_plan,
                diagnostics=diagnostics_with_mtf,
                mtf_explanation=mtf["explanation"],
                decision=decision,
            ),
            strategy_diagnostics=diagnostics_with_mtf,
            base_position_size=risk_plan.base_position_size,
            final_position_size=risk_plan.final_position_size,
            size_multiplier=risk_plan.size_multiplier,
            risk_adjustments=risk_plan.risk_adjustments,
            safety_filters=risk_plan.safety_filters,
            blocked_by_risk_guard=bool(diagnostics_with_mtf.get("blocked_by_risk_guard", False)),
            probabilities=_probability_values(context.probabilities),
            raw_probabilities=_probability_values(context.raw_probabilities),
            calibrated_probabilities=_probability_values(context.calibrated_probabilities),
            probability_source=context.probability_source,
            model_scope_used=(model_selection or {}).get("model_scope_used"),
            model_version=(model_selection or {}).get("model_version"),
            fallback_reason=(model_selection or {}).get("fallback_reason"),
            wait_reason=None,
            reasoning_decision=(
                diagnostics_with_mtf.get("reasoning_decision")
                if self._reasoning_brain_enabled()
                else None
            ),
        )

    def _reasoning_context(
        self,
        context: SignalContext,
        decision: StrategyDecision,
        risk_plan: RiskPlan,
        diagnostics: dict[str, object],
        model_selection: dict[str, str | None] | None,
    ) -> MarketReasoningContext:
        """Build market-reasoning context from current strategy/risk state."""
        return MarketReasoningContext(
            symbol=context.symbol,
            timeframe=context.timeframe,
            market_regime=context.regime_value(),
            features=context.primary_features or context.features,
            probabilities=context.probabilities,
            primary_signal=decision.signal,
            strategy=decision.strategy,
            risk_plan=risk_plan,
            diagnostics=diagnostics,
            model_version=(model_selection or {}).get("model_version"),
            risk_guard_failed=bool(diagnostics.get("blocked_by_risk_guard", False)),
        )

    def _apply_reasoning_size_multiplier(
        self,
        risk_plan: RiskPlan,
        multiplier: float,
    ) -> RiskPlan:
        """Apply reasoning-brain size multiplier on top of existing plan."""
        bounded = max(0.0, min(float(multiplier), 1.0))
        if bounded >= 0.999:
            return risk_plan
        base_size = risk_plan.base_position_size or risk_plan.position_size
        prior_multiplier = (
            float(risk_plan.size_multiplier)
            if risk_plan.size_multiplier is not None
            else 1.0
        )
        combined_multiplier = max(0.0, min(prior_multiplier * bounded, 1.0))
        final_size = base_size * combined_multiplier
        return replace(
            risk_plan,
            position_size=final_size,
            final_position_size=final_size,
            size_multiplier=round(combined_multiplier, 4),
            risk_notes=[
                *risk_plan.risk_notes,
                f"Reasoning brain size multiplier applied: {bounded:.2f}.",
            ],
        )

    def _decision_trace(
        self,
        context: SignalContext,
        final_signal: SignalType,
        strategy: StrategyType,
        reasons: list[str],
        final_confidence: float,
        diagnostics: dict[str, object] | None,
        wait_reason: str | None,
        model_selection: dict[str, str | None] | None,
    ) -> dict[str, object]:
        """Build a compact decision trace payload for diagnostics."""
        trace = DecisionTrace(
            symbol=context.symbol,
            timeframe=context.timeframe,
            final_signal=final_signal.value,
            final_confidence=round(final_confidence, 4),
            model_version=(model_selection or {}).get("model_version"),
            config_hash=None,
            wait_reason=wait_reason,
        )
        final_score = 0.0
        if isinstance(diagnostics, dict):
            final_score = _optional_feature_float(diagnostics, "adaptive_threshold") or 0.0
            selected = diagnostics.get("selected_strategy")
            if isinstance(selected, dict):
                selected_score = _optional_feature_float(selected, "score")
                if selected_score is not None:
                    final_score = selected_score
        details: dict[str, object] = {
            "strategy": strategy.value,
            "reason_count": len(reasons),
            "latest_reasons": reasons[-3:],
        }
        if wait_reason is not None:
            details["wait_reason"] = wait_reason
        if diagnostics and isinstance(diagnostics.get("multi_timeframe"), dict):
            details["multi_timeframe"] = diagnostics["multi_timeframe"]
        if diagnostics and isinstance(diagnostics.get("drift_report"), dict):
            details["drift_report"] = diagnostics["drift_report"]
        data_quality = _coerce_data_quality_report(
            (diagnostics or {}).get("data_quality")
            if isinstance(diagnostics, dict)
            else None
        )
        if data_quality is not None:
            trace.add_step(
                step_name="data_quality",
                input_score=1.0,
                output_score=data_quality.score,
                passed=data_quality.recommended_action is not DataQualityAction.BLOCK,
                details=data_quality.to_dict(),
                warnings=list(data_quality.issues),
            )
        trace.add_step(
            step_name="final_decision",
            input_score=round(final_score, 4),
            output_score=round(final_score, 4),
            passed=final_signal is not SignalType.WAIT,
            details=details,
            warnings=[
                str(item)
                for item in (diagnostics or {}).get("decision_warnings", [])
                if isinstance(item, str)
            ],
        )
        if wait_reason is not None:
            trace.add_warning(wait_reason)
        drift_report = diagnostics.get("drift_report") if isinstance(diagnostics, dict) else None
        if isinstance(drift_report, dict) and str(drift_report.get("drift_level", "")).upper() == "HIGH":
            trace.add_warning("MODEL_DRIFT_HIGH")
        return trace.to_dict()

    def _score(self, decision: StrategyDecision, risk_plan: RiskPlan) -> float:
        """Calculate weighted confidence score."""
        rr_score = max(0.0, min(risk_plan.risk_reward / self._settings.signal.min_risk_reward, 1.0))
        score = (
            decision.model_probability * self._settings.signal.model_score_weight
            + decision.trend_score * self._settings.signal.trend_score_weight
            + decision.indicator_score * self._settings.signal.indicator_score_weight
            + decision.volume_score * self._settings.signal.volume_score_weight
            + rr_score * self._settings.signal.risk_reward_score_weight
        )
        return round(max(0.0, min(score, 1.0)), 4)

    def _wait(
        self,
        context: SignalContext,
        reasons: list[str],
        strategy: StrategyType = StrategyType.NONE,
        risk_plan: RiskPlan | None = None,
        diagnostics: dict[str, object] | None = None,
        model_selection: dict[str, str | None] | None = None,
        mtf_explanation: dict[str, object] | None = None,
        wait_reason: str | None = None,
    ) -> TradeSetup:
        """Return a non-actionable WAIT setup."""
        diagnostics_payload = dict(diagnostics or {})
        reason = normalize_wait_reason(
            wait_reason
            or infer_wait_reason(
                reasons=reasons,
                diagnostics=diagnostics_payload,
                volatility_level=str(
                    (context.primary_features or context.features).get("volatility_level", "UNKNOWN")
                ),
                transition_warning=context.transition_warning,
            ).value
        ).value
        diagnostics_payload["wait_reason"] = reason
        diagnostics_payload["decision_trace"] = self._decision_trace(
            context=context,
            final_signal=SignalType.WAIT,
            strategy=strategy,
            reasons=reasons,
            final_confidence=context.probability(SignalType.WAIT),
            diagnostics=diagnostics_payload,
            wait_reason=reason,
            model_selection=model_selection,
        )
        resolved_mtf_explanation = (
            mtf_explanation
            if mtf_explanation is not None
            else (
                diagnostics_payload.get("multi_timeframe")
                if isinstance(diagnostics_payload.get("multi_timeframe"), dict)
                else self._multi_timeframe_explanation_disabled_or_missing(context)
            )
        )
        return TradeSetup(
            symbol=context.symbol,
            timeframe=context.timeframe,
            timestamp=context.timestamp,
            market_regime=context.regime_value(),
            signal=SignalType.WAIT,
            strategy=strategy,
            confidence=context.probability(SignalType.WAIT),
            entry=risk_plan.entry if risk_plan else None,
            stop_loss=risk_plan.stop_loss if risk_plan else None,
            take_profit_1=risk_plan.take_profit_1 if risk_plan else None,
            take_profit_2=risk_plan.take_profit_2 if risk_plan else None,
            risk_reward=risk_plan.risk_reward if risk_plan else None,
            position_size=risk_plan.position_size if risk_plan else None,
            reasons=reasons,
            risk_notes=risk_plan.risk_notes if risk_plan else [],
            base_position_size=risk_plan.base_position_size if risk_plan else None,
            final_position_size=risk_plan.final_position_size if risk_plan else None,
            size_multiplier=risk_plan.size_multiplier if risk_plan else None,
            risk_adjustments=risk_plan.risk_adjustments if risk_plan else [],
            safety_filters=(
                list((diagnostics_payload or {}).get("safety_filters", []))
                if diagnostics_payload
                else risk_plan.safety_filters if risk_plan else []
            ),
            blocked_by_risk_guard=bool((diagnostics_payload or {}).get("blocked_by_risk_guard", False)),
            explanation_v2=self._structured_explanation(
                context=context,
                final_signal=SignalType.WAIT,
                strategy=strategy,
                reasons=reasons,
                risk_plan=risk_plan,
                diagnostics=diagnostics_payload,
                mtf_explanation=resolved_mtf_explanation,
                decision=None,
            ),
            strategy_diagnostics=diagnostics_payload,
            probabilities=_probability_values(context.probabilities),
            raw_probabilities=_probability_values(context.raw_probabilities),
            calibrated_probabilities=_probability_values(context.calibrated_probabilities),
            probability_source=context.probability_source,
            model_scope_used=(model_selection or {}).get("model_scope_used"),
            model_version=(model_selection or {}).get("model_version"),
            fallback_reason=(model_selection or {}).get("fallback_reason"),
            wait_reason=reason,
            reasoning_decision=(
                diagnostics_payload.get("reasoning_decision")
                if isinstance(diagnostics_payload.get("reasoning_decision"), dict)
                else None
            ),
        )


def _with_regime(context: SignalContext, regime: MarketRegime) -> SignalContext:
    """Return a copy of context with a candidate regime."""
    return SignalContext(
        symbol=context.symbol,
        timeframe=context.timeframe,
        timestamp=context.timestamp,
        market_regime=regime,
        features=context.features,
        probabilities=context.probabilities,
        primary_timeframe=context.primary_timeframe,
        higher_timeframes=context.higher_timeframes,
        primary_features=context.primary_features,
        higher_timeframe_features=context.higher_timeframe_features,
        primary_regime=regime,
        higher_timeframe_regimes=context.higher_timeframe_regimes,
        model_prediction=context.model_prediction,
        strategy_scores=context.strategy_scores,
        risk_plan=context.risk_plan,
        explanation_context=context.explanation_context,
        regime_scores=context.regime_scores,
        regime_confidence=context.regime_confidence,
        transition_warning=context.transition_warning,
        raw_probabilities=context.raw_probabilities,
        calibrated_probabilities=context.calibrated_probabilities,
        probability_source=context.probability_source,
    )


def _adaptive_threshold_context(context: SignalContext) -> AdaptiveThresholdContext:
    """Build threshold context from signal features and higher timeframe state."""
    features = context.primary_features or context.features
    uncertainty = _feature_float(
        features,
        "regime_uncertainty_score",
        max(0.0, 1.0 - context.regime_confidence),
    )
    volume_ratio = _feature_float(features, "volume_ratio", 1.0)
    trend_alignment = abs(_feature_float(features, "trend_score", 0.0))
    return AdaptiveThresholdContext(
        symbol=context.symbol,
        timeframe=context.timeframe,
        regime=context.regime_value(),
        regime_confidence=context.regime_confidence,
        uncertainty_score=uncertainty,
        volatility_level=str(features.get("volatility_level", "NORMAL")),
        higher_timeframe_conflict=_has_higher_timeframe_conflict(context),
        recent_strategy_performance=_optional_feature_float(
            features,
            "recent_strategy_performance",
        ),
        probability_source=context.probability_source,
        volume_quality=max(0.0, min(volume_ratio / 1.5, 1.0)),
        trend_alignment=max(0.0, min(trend_alignment, 1.0)),
    )


def _setup_quality_multiplier(quality: str) -> float:
    """Map setup quality to risk multiplier."""
    normalized = quality.upper()
    return {
        "A_PLUS": 1.0,
        "A": 0.8,
        "B": 0.5,
        "C": 0.25,
        "D": 0.0,
    }.get(normalized, 0.5)


def _quality_from_score(score: float) -> str:
    """Infer setup quality when adaptive diagnostics are unavailable."""
    if score >= 0.85:
        return "A_PLUS"
    if score >= 0.78:
        return "A"
    if score >= 0.68:
        return "B"
    if score >= 0.58:
        return "C"
    return "D"


def _regime_confidence_multiplier(confidence: float) -> float:
    """Map regime confidence to risk multiplier."""
    if confidence >= 0.75:
        return 1.0
    if confidence >= 0.60:
        return 0.75
    if confidence >= 0.50:
        return 0.5
    return 0.0


def _volatility_multiplier(level: str) -> float:
    """Map volatility level to risk multiplier."""
    normalized = level.upper()
    if normalized == "LOW":
        return 0.8
    if normalized == "HIGH":
        return 0.5
    if normalized == "EXTREME":
        return 0.0
    return 1.0


def _memory_performance_multiplier(diagnostics: Mapping[str, object] | None) -> float:
    """Read memory size multiplier from adaptive diagnostics."""
    adjustments = (diagnostics or {}).get("memory_adjustments", [])
    if not isinstance(adjustments, list) or not adjustments:
        return 1.0
    multiplier = 1.0
    for adjustment in adjustments:
        if not isinstance(adjustment, dict):
            continue
        try:
            multiplier = min(multiplier, float(adjustment.get("size_multiplier", 1.0)))
        except (TypeError, ValueError):
            continue
        if adjustment.get("blocked"):
            return 0.0
    return max(0.0, min(multiplier, 1.0))


def _drawdown_multiplier(context: RiskGuardContext | None) -> float:
    """Reduce risk as paper equity drawdown increases."""
    if context is None or context.initial_balance <= 0:
        return 1.0
    drawdown = max(0.0, (context.initial_balance - context.equity) / context.initial_balance)
    if drawdown >= 0.05:
        return 0.5
    if drawdown >= 0.02:
        return 0.75
    return 1.0


def _merge_diagnostics(
    base: Mapping[str, object] | None,
    override: Mapping[str, object] | None,
) -> dict[str, object]:
    """Merge optional diagnostic payloads without mutating either input."""
    return {**dict(base or {}), **dict(override or {})}


def _coerce_data_quality_report(value: object) -> DataQualityReport | None:
    """Parse a data quality report from an object or serialized mapping."""
    if isinstance(value, DataQualityReport):
        return value
    if isinstance(value, Mapping):
        return DataQualityReport.from_mapping(value)
    return None


def _should_hard_block_data_quality(
    settings: Settings,
    report: DataQualityReport | None,
) -> bool:
    """Return True when data quality should stop signal generation."""
    if report is None or not settings.risk_guard.hard_block_data_quality_fail:
        return False
    return (
        report.severity is DataQualitySeverity.HIGH
        or report.recommended_action is DataQualityAction.BLOCK
    )


def _has_higher_timeframe_conflict(context: SignalContext) -> bool:
    """Return True when higher timeframes conflict with strongest model side."""
    buy_probability = context.probability(SignalType.BUY)
    sell_probability = context.probability(SignalType.SELL)
    signal = SignalType.BUY if buy_probability >= sell_probability else SignalType.SELL
    for regime in context.higher_timeframe_regimes.values():
        value = regime.value if isinstance(regime, MarketRegime) else str(regime)
        if signal is SignalType.BUY and value in {
            MarketRegime.DOWNTREND.value,
            MarketRegime.BREAKOUT_DOWN.value,
        }:
            return True
        if signal is SignalType.SELL and value in {
            MarketRegime.UPTREND.value,
            MarketRegime.BREAKOUT_UP.value,
        }:
            return True
    return False


def _higher_timeframe_regimes(
    payloads: Mapping[str, Mapping[str, object]],
) -> dict[str, str]:
    """Infer higher timeframe regime labels from feature payloads."""
    return {
        timeframe: _regime_string(payload.get("market_regime", "UNKNOWN"))
        for timeframe, payload in payloads.items()
    }


def _regime_string(value: object) -> str:
    """Return a market regime value as string."""
    if isinstance(value, MarketRegime):
        return value.value
    return str(value)


def _feature_float(
    payload: Mapping[str, object],
    key: str,
    default: float,
) -> float:
    """Read a finite-ish float from a feature payload."""
    try:
        return float(payload.get(key, default))
    except (TypeError, ValueError):
        return default


def _optional_feature_float(
    payload: Mapping[str, object],
    key: str,
) -> float | None:
    """Read an optional numeric feature value."""
    if key not in payload:
        return None
    try:
        return float(payload[key])
    except (TypeError, ValueError):
        return None


def _timeframe_conflicts(signal: SignalType, regime: str, strength: float) -> bool:
    """Return True when higher timeframe strongly opposes the entry side."""
    if strength < 0.65:
        return False
    if signal is SignalType.BUY:
        return regime in {MarketRegime.DOWNTREND.value, MarketRegime.BREAKOUT_DOWN.value}
    if signal is SignalType.SELL:
        return regime in {MarketRegime.UPTREND.value, MarketRegime.BREAKOUT_UP.value}
    return False


def _timeframe_aligns(signal: SignalType, regime: str) -> bool:
    """Return True when higher timeframe direction agrees with entry side."""
    if signal is SignalType.BUY:
        return regime in {MarketRegime.UPTREND.value, MarketRegime.BREAKOUT_UP.value}
    if signal is SignalType.SELL:
        return regime in {MarketRegime.DOWNTREND.value, MarketRegime.BREAKOUT_DOWN.value}
    return False


def _decision_summary(
    final_signal: SignalType,
    strategy: StrategyType,
    reasons: list[str],
    mtf_explanation: Mapping[str, object],
) -> str:
    """Build a compact human-readable final decision summary."""
    if final_signal is SignalType.WAIT:
        if reasons:
            return f"WAIT because {reasons[-1]}"
        return "WAIT because no actionable setup passed all checks."
    if mtf_explanation.get("conflict"):
        return (
            f"{final_signal.value} from {strategy.value}, but higher timeframe conflict "
            "reduced confidence."
        )
    if mtf_explanation.get("aligned_timeframes"):
        return (
            f"{final_signal.value} from {strategy.value} with higher timeframe confirmation."
        )
    return f"{final_signal.value} from {strategy.value} on the primary timeframe."


def _strategy_score(decision: StrategyDecision) -> StrategyScore:
    """Convert a strategy decision into a score model."""
    score = decision.score or round(
        max(
            0.0,
            min(
                decision.model_probability * 0.5
                + decision.trend_score * 0.2
                + decision.indicator_score * 0.2
                + decision.volume_score * 0.1,
                1.0,
            ),
        ),
        4,
    )
    return StrategyScore(
        strategy_type=decision.strategy,
        signal=decision.signal,
        score=score,
        confidence=decision.confidence or decision.model_probability,
        reasons=decision.reasons,
        failed_conditions=decision.failed_conditions,
    )


def _strategy_score_dict(score: StrategyScore) -> dict[str, object]:
    """Serialize strategy score diagnostics."""
    return {
        "strategy_type": score.strategy_type.value,
        "signal": score.signal.value,
        "score": score.score,
        "confidence": score.confidence,
        "reasons": score.reasons,
        "failed_conditions": score.failed_conditions,
    }


def _ensemble_diagnostics(
    result: StrategyEnsembleResult,
    context: SignalContext,
) -> dict[str, object]:
    """Serialize ensemble result for API responses and explanations."""
    diagnostics: dict[str, object] = {
        "regime_confidence": context.regime_confidence,
        "transition_warning": context.transition_warning,
        "candidates": [_strategy_score_dict(score) for score in result.candidates],
        "rejected_strategies": [
            _strategy_score_dict(score) for score in result.rejected
        ],
        "conflict": result.conflict,
        "reasons": result.reasons,
    }
    if result.selected is not None:
        diagnostics["selected_strategy"] = _strategy_score_dict(result.selected)
    return diagnostics


def _regime_scores(features: Mapping[str, object]) -> Mapping[str, float]:
    """Read soft regime scores from feature payload."""
    raw = features.get("regime_scores")
    if isinstance(raw, Mapping):
        return {str(key): float(value) for key, value in raw.items()}
    if isinstance(raw, str):
        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        if isinstance(decoded, dict):
            return {str(key): float(value) for key, value in decoded.items()}
    return {}


def _regime_confidence(features: Mapping[str, object]) -> float:
    """Read regime confidence from feature payload."""
    try:
        return float(features.get("regime_confidence", 1.0))
    except (TypeError, ValueError):
        return 1.0


def _transition_warning(features: Mapping[str, object]) -> bool:
    """Read transition warning from feature payload."""
    value = features.get("transition_warning", False)
    if isinstance(value, str):
        return value.lower() in {"true", "1", "yes"}
    return bool(value)


def _json_list(value: object) -> list[object]:
    """Return list payloads from JSON strings or list values."""
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return []
        return decoded if isinstance(decoded, list) else []
    return []


def _probability_values(
    probabilities: Mapping[str | SignalType, float] | None,
) -> dict[str, float] | None:
    """Return string-keyed probabilities for API serialization."""
    if probabilities is None:
        return None
    return {
        key.value if isinstance(key, SignalType) else str(key): float(value)
        for key, value in probabilities.items()
    }
