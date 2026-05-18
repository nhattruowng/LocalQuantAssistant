"""Signal engine that converts model probabilities into trade setups."""

from __future__ import annotations

import logging
import json
from typing import Mapping

from config.settings import Settings
from regime.market_regime import MarketRegime
from risk.risk_guard import RiskGuard, RiskGuardContext
from risk.risk_manager import RiskManager
from signals.models import (
    RiskPlan,
    SignalContext,
    SignalType,
    StrategyDecision,
    StrategyEnsembleResult,
    StrategyScore,
    StrategyType,
    TradeSetup,
)
from strategy.base import Strategy
from strategy.breakout import BreakoutStrategy
from strategy.mean_reversion import MeanReversionStrategy
from strategy.trend_following import TrendFollowingStrategy


class SignalEngine:
    """Builds conservative BUY/SELL/WAIT setups from model and market context."""

    def __init__(
        self,
        settings: Settings,
        risk_manager: RiskManager | None = None,
        risk_guard: RiskGuard | None = None,
        risk_guard_context: RiskGuardContext | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._settings = settings
        self._risk_manager = risk_manager or RiskManager(settings.risk)
        self._risk_guard = risk_guard
        self._risk_guard_context = risk_guard_context
        self._logger = logger or logging.getLogger("localquant.signal")
        self._strategies: dict[str, Strategy] = {
            MarketRegime.UPTREND.value: TrendFollowingStrategy(settings.signal),
            MarketRegime.DOWNTREND.value: TrendFollowingStrategy(settings.signal),
            MarketRegime.BREAKOUT_UP.value: BreakoutStrategy(settings.signal),
            MarketRegime.BREAKOUT_DOWN.value: BreakoutStrategy(settings.signal),
            MarketRegime.SIDEWAY.value: MeanReversionStrategy(settings.signal),
        }

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
    ) -> TradeSetup:
        """Generate a complete trade setup recommendation."""
        higher_features = dict(higher_timeframe_features or {})
        higher_regimes = dict(higher_timeframe_regimes or _higher_timeframe_regimes(higher_features))
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
                "multi_timeframe_enabled": multi_timeframe_enabled,
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
        diagnostics: dict[str, object] | None = None
        if self._ensemble_enabled():
            decision, diagnostics = self._ensemble_decision(context)
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

        risk_plan = self._risk_plan_for(context, decision, features, model_selection)
        if isinstance(risk_plan, TradeSetup):
            return risk_plan
        if not self._is_risk_acceptable(risk_plan):
            return self._wait(
                context,
                [
                    *decision.reasons,
                    (
                        f"Risk/reward {risk_plan.risk_reward:.2f} is below "
                        f"{self._settings.signal.min_risk_reward:.2f}."
                    ),
                ],
                decision.strategy,
                risk_plan,
                diagnostics=diagnostics,
                model_selection=model_selection,
            )

        setup = self._approved_setup(context, decision, risk_plan, diagnostics, model_selection)
        if self._risk_guard is not None and self._risk_guard_context is not None:
            guard = self._risk_guard.evaluate(setup, self._risk_guard_context)
            if not guard.allowed:
                return self._wait(
                    context,
                    guard.reasons,
                    decision.strategy,
                    risk_plan,
                    diagnostics={
                        **(diagnostics or {}),
                        "risk_guard_state": guard.state.value,
                        "risk_guard_reasons": guard.reasons,
                    },
                    model_selection=model_selection,
                )
        return setup

    def _strategy_for(self, context: SignalContext) -> Strategy | None:
        """Return the strategy for the current market regime."""
        return self._strategies.get(context.regime_value())

    def _ensemble_enabled(self) -> bool:
        """Return True when strategy ensemble mode is enabled."""
        ensemble = self._settings.signal.strategy_ensemble
        return bool(ensemble and ensemble.enabled)

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
    ) -> RiskPlan | TradeSetup:
        """Build a risk plan or a WAIT setup when risk planning fails."""
        try:
            risk_plan = self._risk_manager.build_plan(decision.signal, features)
        except (KeyError, ValueError) as error:
            return self._wait(
                context,
                [*decision.reasons, f"Risk plan failed: {error}."],
                decision.strategy,
                model_selection=model_selection,
            )

        if risk_plan is None:
            return self._wait(
                context,
                [*decision.reasons, "No risk plan was built."],
                decision.strategy,
                model_selection=model_selection,
            )
        return risk_plan

    def _is_risk_acceptable(self, risk_plan: RiskPlan) -> bool:
        """Return True when risk/reward passes the configured gate."""
        return risk_plan.risk_reward >= self._settings.signal.min_risk_reward

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
                "passed_conditions": list(passed_conditions),
                "failed_conditions": list(failed_conditions),
                "rejected_strategies": (diagnostics or {}).get("rejected_strategies", []),
            },
            "risk": {
                "risk_reward": risk_plan.risk_reward if risk_plan else None,
                "position_size": risk_plan.position_size if risk_plan else None,
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
            explanation = self._structured_explanation(
                context=context,
                final_signal=SignalType.WAIT,
                strategy=decision.strategy,
                reasons=reasons,
                risk_plan=risk_plan,
                diagnostics=diagnostics,
                mtf_explanation=mtf["explanation"],
                decision=decision,
            )
            return TradeSetup(
                symbol=context.symbol,
                timeframe=context.timeframe,
                timestamp=context.timestamp,
                market_regime=context.regime_value(),
                signal=SignalType.WAIT,
                strategy=decision.strategy,
                confidence=context.probability(SignalType.WAIT),
                entry=risk_plan.entry,
                stop_loss=risk_plan.stop_loss,
                take_profit_1=risk_plan.take_profit_1,
                take_profit_2=risk_plan.take_profit_2,
                risk_reward=risk_plan.risk_reward,
                position_size=risk_plan.position_size,
                reasons=reasons,
                risk_notes=risk_plan.risk_notes,
                explanation_v2=explanation,
                strategy_diagnostics={
                    **(diagnostics or {}),
                    "multi_timeframe": mtf["explanation"],
                },
                probabilities=_probability_values(context.probabilities),
                raw_probabilities=_probability_values(context.raw_probabilities),
                calibrated_probabilities=_probability_values(context.calibrated_probabilities),
                probability_source=context.probability_source,
                model_scope_used=(model_selection or {}).get("model_scope_used"),
                model_version=(model_selection or {}).get("model_version"),
                fallback_reason=(model_selection or {}).get("fallback_reason"),
            )
        confidence = round(confidence * float(mtf["confidence_multiplier"]), 4)
        diagnostics_with_mtf = {
            **(diagnostics or {}),
            "multi_timeframe": mtf["explanation"],
        }
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
            probabilities=_probability_values(context.probabilities),
            raw_probabilities=_probability_values(context.raw_probabilities),
            calibrated_probabilities=_probability_values(context.calibrated_probabilities),
            probability_source=context.probability_source,
            model_scope_used=(model_selection or {}).get("model_scope_used"),
            model_version=(model_selection or {}).get("model_version"),
            fallback_reason=(model_selection or {}).get("fallback_reason"),
        )

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
    ) -> TradeSetup:
        """Return a non-actionable WAIT setup."""
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
            explanation_v2=self._structured_explanation(
                context=context,
                final_signal=SignalType.WAIT,
                strategy=strategy,
                reasons=reasons,
                risk_plan=risk_plan,
                diagnostics=diagnostics,
                mtf_explanation=self._multi_timeframe_explanation_disabled_or_missing(context),
                decision=None,
            ),
            strategy_diagnostics=diagnostics,
            probabilities=_probability_values(context.probabilities),
            raw_probabilities=_probability_values(context.raw_probabilities),
            calibrated_probabilities=_probability_values(context.calibrated_probabilities),
            probability_source=context.probability_source,
            model_scope_used=(model_selection or {}).get("model_scope_used"),
            model_version=(model_selection or {}).get("model_version"),
            fallback_reason=(model_selection or {}).get("fallback_reason"),
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
