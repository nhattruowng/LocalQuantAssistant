"""Market reasoning brain skeleton based on evidence/confluence/conflict."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import TYPE_CHECKING, Any, Mapping

from config.settings import ReasoningBrainSettings
from reasoning.confluence_engine import ConfluenceEngine
from reasoning.conflict_resolver import ConflictAction, ConflictLevel, ConflictResolver
from reasoning.evidence import Evidence, EvidenceDirection, EvidenceType
from reasoning.setup_classifier import SetupClassifier, SetupType
from signals.decision_trace import DecisionTrace
from signals.models import RiskPlan, SignalType, StrategyType
from signals.wait_reason import WaitReason

if TYPE_CHECKING:
    from ict.ict_context_builder import ICTContextBuilder


@dataclass(frozen=True)
class MarketReasoningContext:
    """Input context for reasoning-brain decisioning."""

    symbol: str
    timeframe: str
    market_regime: str
    features: Mapping[str, object]
    probabilities: Mapping[str | SignalType, float]
    primary_signal: SignalType
    strategy: StrategyType
    risk_plan: RiskPlan | None = None
    diagnostics: Mapping[str, object] = field(default_factory=dict)
    model_version: str | None = None
    risk_guard_failed: bool = False

    def probability(self, signal: SignalType) -> float:
        value = self.probabilities.get(signal, self.probabilities.get(signal.value, 0.0))
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0


@dataclass(frozen=True)
class ReasoningDecision:
    """Final decision produced by market reasoning brain."""

    final_signal: SignalType
    setup_type: SetupType
    confluence_score: float
    confidence: float
    adaptive_threshold: float
    position_size_multiplier: float
    evidence_for: list[Evidence] = field(default_factory=list)
    evidence_against: list[Evidence] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    wait_reason: str | None = None
    conflict_level: ConflictLevel = ConflictLevel.NONE
    conflict_details: dict[str, object] = field(default_factory=dict)
    risk_notes: list[str] = field(default_factory=list)
    decision_trace: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "final_signal": self.final_signal.value,
            "setup_type": self.setup_type.value,
            "confluence_score": self.confluence_score,
            "confidence": self.confidence,
            "adaptive_threshold": self.adaptive_threshold,
            "position_size_multiplier": self.position_size_multiplier,
            "evidence_for": [item.to_dict() for item in self.evidence_for],
            "evidence_against": [item.to_dict() for item in self.evidence_against],
            "warnings": list(self.warnings),
            "wait_reason": self.wait_reason,
            "conflict_level": self.conflict_level.value,
            "conflict_details": dict(self.conflict_details),
            "risk_notes": list(self.risk_notes),
            "decision_trace": dict(self.decision_trace),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict())


class MarketReasoningBrain:
    """Evidence-driven decision brain layered on top of existing strategy engine."""

    def __init__(
        self,
        settings: ReasoningBrainSettings,
        confluence_engine: ConfluenceEngine | None = None,
        conflict_resolver: ConflictResolver | None = None,
        setup_classifier: SetupClassifier | None = None,
        ict_context_builder: ICTContextBuilder | None = None,
    ) -> None:
        self._settings = settings
        self._confluence_engine = confluence_engine or ConfluenceEngine()
        self._conflict_resolver = conflict_resolver or ConflictResolver()
        self._setup_classifier = setup_classifier or SetupClassifier()
        if ict_context_builder is not None:
            self._ict_context_builder = ict_context_builder
        else:
            try:
                from ict.ict_context_builder import ICTContextBuilder as _ICTContextBuilder
            except ImportError:
                self._ict_context_builder = None
            else:
                self._ict_context_builder = _ICTContextBuilder(enabled=True)

    def decide(self, context: MarketReasoningContext) -> ReasoningDecision:
        """Run evidence -> confluence -> conflict -> final reasoning decision flow."""
        trace = DecisionTrace(
            symbol=context.symbol,
            timeframe=context.timeframe,
            final_signal=SignalType.WAIT.value,
            final_confidence=context.probability(SignalType.WAIT),
            model_version=context.model_version,
            config_hash=None,
        )
        evidence = self._collect_evidence(context, trace)
        confluence = self._confluence_engine.evaluate(evidence, trace=trace)
        conflict = self._conflict_resolver.evaluate(evidence)
        capped_penalty = min(conflict.conflict_penalty, self._settings.max_conflict_penalty)
        final_score = _clip(confluence.raw_score - capped_penalty)
        strong_conflict = (
            conflict.conflict_level is ConflictLevel.HIGH
            or capped_penalty >= self._settings.strong_conflict_threshold
            or conflict.recommended_action is ConflictAction.WAIT
        )

        signal = SignalType.WAIT
        wait_reason: str | None = None
        size_multiplier = 0.0
        threshold = self._settings.min_confluence_score

        if context.risk_guard_failed or bool(context.diagnostics.get("blocked_by_risk_guard", False)):
            wait_reason = WaitReason.WAIT_RISK_BLOCK.value
        elif strong_conflict:
            wait_reason = WaitReason.WAIT_STRATEGY_CONFLICT.value
        elif final_score >= self._settings.min_confluence_score:
            signal = context.primary_signal
            size_multiplier = 1.0
        elif (
            final_score >= self._settings.medium_score_threshold
            and self._settings.allow_reduced_size_for_medium_score
        ):
            signal = context.primary_signal
            size_multiplier = 0.5
            threshold = self._settings.medium_score_threshold
        else:
            wait_reason = WaitReason.WAIT_LOW_CONFIDENCE.value

        setup_type = self._setup_classifier.classify(evidence, conflict, final_score)
        confidence = _clip((final_score + context.probability(signal if signal is not SignalType.WAIT else SignalType.WAIT)) / 2.0)
        conflict_details = conflict.to_dict()
        conflict_details["capped_conflict_penalty"] = round(capped_penalty, 8)

        trace.set_final(signal, round(confidence, 4), wait_reason=wait_reason)
        trace.add_step(
            step_name="final_decision",
            input_score=round(final_score, 4),
            output_score=round(final_score, 4),
            passed=signal is not SignalType.WAIT,
            details={
                "setup_type": setup_type.value,
                "confluence_score": round(final_score, 4),
                "conflict_level": conflict.conflict_level.value,
                "wait_reason": wait_reason,
                "position_size_multiplier": size_multiplier,
            },
            warnings=list(conflict.conflict_reasons),
        )
        if wait_reason:
            trace.add_warning(wait_reason)

        warnings = [item.reason for item in confluence.warnings]
        return ReasoningDecision(
            final_signal=signal,
            setup_type=setup_type,
            confluence_score=round(final_score, 8),
            confidence=round(confidence, 8),
            adaptive_threshold=round(threshold, 8),
            position_size_multiplier=round(size_multiplier, 8),
            evidence_for=list(confluence.evidence_for),
            evidence_against=[*confluence.evidence_against, *confluence.warnings],
            warnings=warnings,
            wait_reason=wait_reason,
            conflict_level=conflict.conflict_level,
            conflict_details=conflict_details,
            risk_notes=list(context.risk_plan.risk_notes if context.risk_plan else []),
            decision_trace=trace.to_dict(),
        )

    def _collect_evidence(
        self,
        context: MarketReasoningContext,
        trace: DecisionTrace,
    ) -> list[Evidence]:
        evidence: list[Evidence] = []
        evidence.extend(self._regime_evidence(context))
        evidence.extend(self._price_action_evidence(context))
        evidence.extend(self._ict_evidence(context, trace))
        evidence.extend(self._strategy_evidence(context))
        evidence.extend(self._model_evidence(context))
        evidence.extend(self._volume_evidence(context))
        evidence.extend(self._mtf_evidence(context))
        evidence.extend(self._risk_reward_evidence(context))
        return evidence

    def _regime_evidence(self, context: MarketReasoningContext) -> list[Evidence]:
        confidence = _clip(_as_float(context.features.get("regime_confidence"), 1.0))
        regime = context.market_regime.upper()
        expected = _signal_from_regime(regime)
        if expected is None:
            return []
        aligned = expected is context.primary_signal
        return [
            Evidence(
                name="Regime Alignment",
                source="regime_alignment",
                direction=context.primary_signal if aligned else _opposite(context.primary_signal),
                score=confidence,
                confidence=confidence,
                weight=1.0,
                evidence_type=EvidenceType.SUPPORT if aligned else EvidenceType.AGAINST,
                reason=f"Regime {regime} {'aligns' if aligned else 'opposes'} entry direction.",
                impact_on_score=0.0,
                is_critical=False,
            )
        ]

    def _price_action_evidence(self, context: MarketReasoningContext) -> list[Evidence]:
        payload = context.features.get("price_action_context")
        if isinstance(payload, Mapping):
            embedded = payload.get("evidence")
            if isinstance(embedded, list):
                parsed = [_parse_evidence_item(item) for item in embedded]
                return [item for item in parsed if item is not None]
        return []

    def _strategy_evidence(self, context: MarketReasoningContext) -> list[Evidence]:
        opinions = context.diagnostics.get("strategy_opinions")
        if not isinstance(opinions, list):
            return []
        evidence: list[Evidence] = []
        for opinion in opinions:
            if not isinstance(opinion, Mapping):
                continue
            signal = str(opinion.get("suggested_signal", "WAIT")).upper()
            if signal not in {"BUY", "SELL"}:
                continue
            direction = EvidenceDirection(signal)
            evidence.append(
                Evidence(
                    name=f"Strategy Opinion {opinion.get('strategy_type', 'UNKNOWN')}",
                    source="strategy_opinion",
                    direction=direction,
                    score=_clip(_as_float(opinion.get("score"), 0.0)),
                    confidence=_clip(_as_float(opinion.get("confidence"), 0.0)),
                    weight=1.0,
                    evidence_type=(
                        EvidenceType.SUPPORT
                        if direction.value == context.primary_signal.value
                        else EvidenceType.AGAINST
                    ),
                    reason="Strategy opinion contribution.",
                    impact_on_score=0.0,
                    is_critical=False,
                )
            )
        return evidence

    def _ict_evidence(self, context: MarketReasoningContext, trace: DecisionTrace) -> list[Evidence]:
        """Collect optional ICT evidence and append ict_confluence trace step."""
        diagnostics = context.diagnostics
        if self._ict_context_builder is None:
            trace.add_step(
                step_name="ict_confluence",
                input_score=0.0,
                output_score=0.0,
                passed=True,
                details={"enabled": False, "reason": "ICT dependencies unavailable."},
                warnings=[],
            )
            return []
        ict_meta = diagnostics.get("ict")
        enabled = True
        if isinstance(ict_meta, Mapping) and "enabled" in ict_meta:
            enabled = bool(ict_meta.get("enabled", True))

        if not enabled:
            trace.add_step(
                step_name="ict_confluence",
                input_score=0.0,
                output_score=0.0,
                passed=True,
                details={"enabled": False, "reason": "ICT module disabled."},
                warnings=[],
            )
            return []

        payload = diagnostics.get("ict_context", context.features.get("ict_context"))
        if isinstance(payload, Mapping):
            evidence = _parse_embedded_evidence(payload.get("evidence"))
            ict_score = _clip(_as_float(payload.get("ict_score"), 0.0))
            trace.add_step(
                step_name="ict_confluence",
                input_score=0.0,
                output_score=round(ict_score, 4),
                passed=ict_score >= 0.5,
                details={
                    "enabled": True,
                    "liquidity_sweep_detected": bool(payload.get("liquidity_sweep_detected", False)),
                    "sweep_direction": str(payload.get("sweep_direction", "NONE")),
                    "fvg_detected": bool(payload.get("fvg_detected", False)),
                    "fakeout_risk_score": _clip(_as_float(payload.get("fakeout_risk_score"), 0.0)),
                    "evidence_count": len(evidence),
                },
                warnings=[],
            )
            return evidence

        candles = self._extract_candles(context)
        if candles is None or candles.empty:
            trace.add_step(
                step_name="ict_confluence",
                input_score=0.0,
                output_score=0.0,
                passed=True,
                details={
                    "enabled": True,
                    "reason": "No candle history provided for ICT analysis.",
                },
                warnings=[],
            )
            return []

        target_index = len(candles) - 1
        raw_index = diagnostics.get("candle_index")
        if raw_index is not None:
            try:
                target_index = int(raw_index)
            except (TypeError, ValueError):
                target_index = len(candles) - 1

        ict_context = self._ict_context_builder.build(candles, index=target_index)
        trace.add_step(
            step_name="ict_confluence",
            input_score=0.0,
            output_score=round(ict_context.ict_score, 4),
            passed=ict_context.ict_score >= 0.5,
            details={
                "enabled": True,
                "liquidity_sweep_detected": ict_context.liquidity_sweep_detected,
                "sweep_direction": ict_context.sweep_direction,
                "fvg_detected": ict_context.fvg_detected,
                "fakeout_risk_score": ict_context.fakeout_risk_score,
                "evidence_count": len(ict_context.evidence),
            },
            warnings=[item.reason for item in ict_context.evidence if item.evidence_type is EvidenceType.WARNING],
        )
        return list(ict_context.evidence)

    def _extract_candles(self, context: MarketReasoningContext) -> Any | None:
        """Read optional candle history payload for ICT analysis."""
        diagnostics = context.diagnostics
        candidates = [
            diagnostics.get("candles"),
            diagnostics.get("ohlcv"),
            context.features.get("candles"),
            context.features.get("ohlcv"),
        ]
        for candidate in candidates:
            frame = _to_candles_dataframe(candidate)
            if frame is not None and not frame.empty:
                return frame
        return None

    def _model_evidence(self, context: MarketReasoningContext) -> list[Evidence]:
        buy = _clip(context.probability(SignalType.BUY))
        sell = _clip(context.probability(SignalType.SELL))
        direction = SignalType.BUY if buy >= sell else SignalType.SELL
        signal_conf = max(buy, sell)
        return [
            Evidence(
                name="Model Probability",
                source="model_probability",
                direction=EvidenceDirection(direction.value),
                score=signal_conf,
                confidence=signal_conf,
                weight=1.0,
                evidence_type=(
                    EvidenceType.SUPPORT
                    if direction is context.primary_signal
                    else EvidenceType.AGAINST
                ),
                reason="Model directional probability.",
                impact_on_score=0.0,
                is_critical=False,
            )
        ]

    def _volume_evidence(self, context: MarketReasoningContext) -> list[Evidence]:
        ratio = _as_float(context.features.get("volume_ratio"), 1.0)
        score = _clip((ratio - 0.8) / 1.2)
        return [
            Evidence(
                name="Volume Confirmation",
                source="volume_confirmation",
                direction=context.primary_signal,
                score=score,
                confidence=_clip(min(1.0, ratio / 2.0)),
                weight=1.0,
                evidence_type=EvidenceType.SUPPORT if ratio >= 1.0 else EvidenceType.WARNING,
                reason=f"Volume ratio={ratio:.2f}.",
                impact_on_score=0.0,
                is_critical=False,
            )
        ]

    def _mtf_evidence(self, context: MarketReasoningContext) -> list[Evidence]:
        mtf = context.diagnostics.get("multi_timeframe")
        if not isinstance(mtf, Mapping):
            return []
        conflict = bool(mtf.get("conflict", False))
        multiplier = _clip(_as_float(mtf.get("confidence_multiplier"), 1.0))
        return [
            Evidence(
                name="Multi Timeframe Alignment",
                source="multi_timeframe_alignment",
                direction=context.primary_signal if not conflict else _opposite(context.primary_signal),
                score=1.0 - multiplier if conflict else multiplier,
                confidence=max(multiplier, 1.0 - multiplier),
                weight=1.0,
                evidence_type=EvidenceType.AGAINST if conflict else EvidenceType.SUPPORT,
                reason="Higher timeframe alignment check.",
                impact_on_score=0.0,
                is_critical=conflict and bool(mtf.get("blocked", False)),
            )
        ]

    def _risk_reward_evidence(self, context: MarketReasoningContext) -> list[Evidence]:
        if context.risk_plan is None:
            return []
        rr = _as_float(context.risk_plan.risk_reward, 0.0)
        score = _clip(rr / 3.0)
        return [
            Evidence(
                name="Risk Reward Quality",
                source="risk_reward_quality",
                direction=context.primary_signal,
                score=score,
                confidence=0.8,
                weight=1.0,
                evidence_type=EvidenceType.SUPPORT if rr >= 2.0 else EvidenceType.AGAINST,
                reason=f"Risk/reward={rr:.2f}.",
                impact_on_score=0.0,
                is_critical=rr < 1.0,
            )
        ]


def _parse_evidence_item(value: object) -> Evidence | None:
    if not isinstance(value, Mapping):
        return None
    try:
        return Evidence(
            name=str(value.get("name", "Unknown Evidence")),
            source=str(value.get("source", "price_action")),
            direction=EvidenceDirection(str(value.get("direction", "NEUTRAL")).upper()),
            score=_clip(_as_float(value.get("score"), 0.0)),
            confidence=_clip(_as_float(value.get("confidence"), 0.0)),
            weight=_clip(_as_float(value.get("weight"), 1.0)),
            evidence_type=EvidenceType(str(value.get("evidence_type", "WARNING")).upper()),
            reason=str(value.get("reason", "")),
            impact_on_score=_as_float(value.get("impact_on_score"), 0.0),
            is_critical=bool(value.get("is_critical", False)),
        )
    except (TypeError, ValueError):
        return None


def _parse_embedded_evidence(value: object) -> list[Evidence]:
    if not isinstance(value, list):
        return []
    parsed = [_parse_evidence_item(item) for item in value]
    return [item for item in parsed if item is not None]


def _to_candles_dataframe(value: object) -> Any | None:
    if value is None:
        return None
    if hasattr(value, "iloc") and hasattr(value, "copy") and hasattr(value, "empty"):
        return value.copy(deep=True)
    if isinstance(value, list):
        try:
            import pandas as pd
        except ImportError:
            return None
        rows = [item for item in value if isinstance(item, Mapping)]
        if not rows:
            return None
        frame = pd.DataFrame.from_records(rows)
        return frame if not frame.empty else None
    return None


def _signal_from_regime(regime: str) -> SignalType | None:
    if regime in {"UPTREND", "BREAKOUT_UP"}:
        return SignalType.BUY
    if regime in {"DOWNTREND", "BREAKOUT_DOWN"}:
        return SignalType.SELL
    return None


def _opposite(signal: SignalType) -> EvidenceDirection:
    if signal is SignalType.BUY:
        return EvidenceDirection.SELL
    if signal is SignalType.SELL:
        return EvidenceDirection.BUY
    return EvidenceDirection.NEUTRAL


def _as_float(value: object, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clip(value: float) -> float:
    return max(0.0, min(float(value), 1.0))
