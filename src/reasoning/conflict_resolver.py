"""Conflict analysis for evidence-driven reasoning."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import json

from reasoning.evidence import Evidence, EvidenceDirection, EvidenceType


class ConflictLevel(str, Enum):
    """Severity buckets for evidence conflicts."""

    NONE = "NONE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ConflictAction(str, Enum):
    """Risk action recommended by the conflict resolver."""

    CONTINUE = "CONTINUE"
    REDUCE_SIZE = "REDUCE_SIZE"
    WAIT = "WAIT"


class ConflictType(str, Enum):
    """Named conflict families for analytics and explainability."""

    REGIME_VS_STRUCTURE = "REGIME_VS_STRUCTURE"
    MODEL_VS_PRICE_ACTION = "MODEL_VS_PRICE_ACTION"
    ICT_VS_VOLUME = "ICT_VS_VOLUME"
    MTF_VS_ENTRY_SIGNAL = "MTF_VS_ENTRY_SIGNAL"
    BREAKOUT_VS_REJECTION = "BREAKOUT_VS_REJECTION"
    RISK_VS_SIGNAL = "RISK_VS_SIGNAL"
    BUY_SELL_EVIDENCE_CONFLICT = "BUY_SELL_EVIDENCE_CONFLICT"


@dataclass(frozen=True)
class ConflictResult:
    """Result payload returned after evidence conflict analysis."""

    conflict_level: ConflictLevel
    conflict_penalty: float
    conflict_reasons: list[str] = field(default_factory=list)
    recommended_action: ConflictAction = ConflictAction.CONTINUE

    def to_dict(self) -> dict[str, object]:
        return {
            "conflict_level": self.conflict_level.value,
            "conflict_penalty": self.conflict_penalty,
            "conflict_reasons": list(self.conflict_reasons),
            "recommended_action": self.recommended_action.value,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict())


class ConflictResolver:
    """Resolve contradictory evidence into an explicit risk action."""

    def __init__(
        self,
        buy_sell_margin: float = 0.12,
        strong_mtf_threshold: float = 0.75,
        medium_mtf_threshold: float = 0.55,
        rejection_conflict_threshold: float = 0.60,
    ) -> None:
        self._buy_sell_margin = max(0.0, min(float(buy_sell_margin), 0.5))
        self._strong_mtf_threshold = _clip(strong_mtf_threshold)
        self._medium_mtf_threshold = _clip(medium_mtf_threshold)
        self._rejection_conflict_threshold = _clip(rejection_conflict_threshold)

    def evaluate(self, evidence: list[Evidence]) -> ConflictResult:
        """Return conflict severity, penalty, and recommended action."""
        if not evidence:
            return ConflictResult(
                conflict_level=ConflictLevel.NONE,
                conflict_penalty=0.0,
                conflict_reasons=[],
                recommended_action=ConflictAction.CONTINUE,
            )

        reasons: list[str] = []
        max_level = ConflictLevel.NONE
        max_action = ConflictAction.CONTINUE
        penalty = 0.0

        buy_strength = self._directional_strength(evidence, EvidenceDirection.BUY)
        sell_strength = self._directional_strength(evidence, EvidenceDirection.SELL)
        total_directional = buy_strength + sell_strength
        dominant_direction = (
            EvidenceDirection.BUY if buy_strength >= sell_strength else EvidenceDirection.SELL
        )
        entry_direction = self._entry_direction(evidence, fallback=dominant_direction)

        # 1) BUY/SELL evidence close to equal => high ambiguity.
        if total_directional > 0:
            imbalance = abs(buy_strength - sell_strength) / total_directional
            if imbalance <= self._buy_sell_margin:
                severity = 1.0 - imbalance
                penalty += 0.25 + 0.25 * severity
                reasons.append(
                    f"{ConflictType.BUY_SELL_EVIDENCE_CONFLICT.value}: "
                    f"BUY={buy_strength:.3f}, SELL={sell_strength:.3f}, imbalance={imbalance:.3f}"
                )
                max_level = ConflictLevel.HIGH
                max_action = ConflictAction.WAIT

        # 2) MTF conflict against dominant direction.
        mtf_total, mtf_opposed = self._mtf_strength(evidence, entry_direction)
        if mtf_total > 0:
            mtf_severity = mtf_opposed / mtf_total
            if mtf_severity >= self._strong_mtf_threshold:
                penalty += 0.28 + 0.20 * mtf_severity
                reasons.append(
                    f"{ConflictType.MTF_VS_ENTRY_SIGNAL.value}: "
                    f"higher timeframe opposes {entry_direction.value} with severity {mtf_severity:.3f}"
                )
                max_level = _max_level(max_level, ConflictLevel.HIGH)
                max_action = ConflictAction.WAIT
            elif mtf_severity >= self._medium_mtf_threshold:
                penalty += 0.14 + 0.10 * mtf_severity
                reasons.append(
                    f"{ConflictType.MTF_VS_ENTRY_SIGNAL.value}: "
                    f"moderate higher timeframe opposition severity {mtf_severity:.3f}"
                )
                max_level = _max_level(max_level, ConflictLevel.MEDIUM)
                max_action = _max_action(max_action, ConflictAction.REDUCE_SIZE)

        # 3) Breakout with strong rejection wick => fakeout risk.
        breakout_strength = self._keyword_strength(evidence, ("breakout",))
        rejection_strength = self._keyword_strength(evidence, ("rejection", "wick"))
        fakeout_severity = min(breakout_strength, rejection_strength)
        if fakeout_severity >= self._rejection_conflict_threshold:
            penalty += 0.22 + 0.25 * fakeout_severity
            reasons.append(
                f"{ConflictType.BREAKOUT_VS_REJECTION.value}: "
                f"breakout={breakout_strength:.3f}, rejection={rejection_strength:.3f}"
            )
            max_level = _max_level(max_level, ConflictLevel.HIGH)
            max_action = ConflictAction.WAIT

        # 4) Model supports a side while PA/ICT disagree.
        model_direction = self._model_direction(evidence) or dominant_direction
        model_strength = self._source_direction_strength(
            evidence,
            source_tokens=("model", "probability"),
            direction=model_direction,
        )
        pa_ict_same = self._source_direction_strength(
            evidence,
            source_tokens=("price_action", "ict"),
            direction=model_direction,
        )
        pa_ict_opposed = self._source_direction_strength(
            evidence,
            source_tokens=("price_action", "ict"),
            direction=_opposite_direction(model_direction),
        )
        if model_strength > 0.0 and pa_ict_same < model_strength * 0.35 and pa_ict_opposed > 0.0:
            disagreement = _clip((pa_ict_opposed + model_strength - pa_ict_same) / (model_strength + 1e-9))
            penalty += 0.08 + 0.14 * disagreement
            reasons.append(
                f"{ConflictType.MODEL_VS_PRICE_ACTION.value}: "
                f"model={model_strength:.3f}, pa_ict_same={pa_ict_same:.3f}, pa_ict_opp={pa_ict_opposed:.3f}"
            )
            max_level = _max_level(max_level, ConflictLevel.MEDIUM)
            max_action = _max_action(max_action, ConflictAction.REDUCE_SIZE)

        # 5) Risk guard blocks should always force WAIT.
        if self._risk_guard_failed(evidence):
            penalty += 0.50
            reasons.append(
                f"{ConflictType.RISK_VS_SIGNAL.value}: risk guard blocking evidence is present"
            )
            max_level = ConflictLevel.HIGH
            max_action = ConflictAction.WAIT

        if not reasons:
            return ConflictResult(
                conflict_level=ConflictLevel.NONE,
                conflict_penalty=0.0,
                conflict_reasons=[],
                recommended_action=ConflictAction.CONTINUE,
            )

        return ConflictResult(
            conflict_level=max_level,
            conflict_penalty=round(_clip(penalty), 8),
            conflict_reasons=reasons,
            recommended_action=max_action,
        )

    def _directional_strength(self, evidence: list[Evidence], direction: EvidenceDirection) -> float:
        return sum(
            _strength(item)
            for item in evidence
            if item.direction is direction and item.evidence_type is not EvidenceType.WARNING
        )

    def _mtf_strength(
        self,
        evidence: list[Evidence],
        entry_direction: EvidenceDirection,
    ) -> tuple[float, float]:
        mtf_items = [item for item in evidence if _is_mtf(item)]
        if not mtf_items:
            return 0.0, 0.0

        total = sum(_strength(item) for item in mtf_items if item.evidence_type is EvidenceType.SUPPORT)
        opposed = sum(
            _strength(item)
            for item in mtf_items
            if item.evidence_type is EvidenceType.SUPPORT and item.direction is _opposite_direction(entry_direction)
        )
        return total, opposed

    def _entry_direction(
        self,
        evidence: list[Evidence],
        fallback: EvidenceDirection,
    ) -> EvidenceDirection:
        buy = 0.0
        sell = 0.0
        for item in evidence:
            if item.evidence_type is not EvidenceType.SUPPORT:
                continue
            if _is_mtf(item):
                continue
            if item.direction is EvidenceDirection.BUY:
                buy += _strength(item)
            if item.direction is EvidenceDirection.SELL:
                sell += _strength(item)
        if buy == 0.0 and sell == 0.0:
            return fallback
        return EvidenceDirection.BUY if buy >= sell else EvidenceDirection.SELL

    def _model_direction(self, evidence: list[Evidence]) -> EvidenceDirection | None:
        buy = 0.0
        sell = 0.0
        for item in evidence:
            source = item.source.lower().replace("-", "_")
            if not ("model" in source or "probability" in source):
                continue
            if item.evidence_type is not EvidenceType.SUPPORT:
                continue
            if item.direction is EvidenceDirection.BUY:
                buy += _strength(item)
            if item.direction is EvidenceDirection.SELL:
                sell += _strength(item)
        if buy == 0.0 and sell == 0.0:
            return None
        return EvidenceDirection.BUY if buy >= sell else EvidenceDirection.SELL

    def _keyword_strength(self, evidence: list[Evidence], keywords: tuple[str, ...]) -> float:
        score = 0.0
        for item in evidence:
            blob = f"{item.name} {item.source} {item.reason}".lower()
            if any(keyword in blob for keyword in keywords):
                score += _strength(item)
        return _clip(score)

    def _source_direction_strength(
        self,
        evidence: list[Evidence],
        source_tokens: tuple[str, ...],
        direction: EvidenceDirection,
    ) -> float:
        strength = 0.0
        for item in evidence:
            source = item.source.lower().replace("-", "_")
            if any(token in source for token in source_tokens):
                if item.direction is direction and item.evidence_type is EvidenceType.SUPPORT:
                    strength += _strength(item)
                if item.direction is direction and item.evidence_type is EvidenceType.AGAINST:
                    strength -= _strength(item)
        return max(0.0, strength)

    def _risk_guard_failed(self, evidence: list[Evidence]) -> bool:
        for item in evidence:
            source = item.source.lower().replace("-", "_")
            reason = item.reason.lower()
            if "risk" not in source and "risk" not in reason:
                continue
            if (
                item.evidence_type in {EvidenceType.WARNING, EvidenceType.AGAINST}
                and (item.is_critical or "block" in reason or "fail" in reason)
            ):
                return True
        return False


def _strength(item: Evidence) -> float:
    return _clip(item.score) * _clip(item.confidence) * _clip(item.weight)


def _clip(value: float) -> float:
    return max(0.0, min(float(value), 1.0))


def _is_mtf(item: Evidence) -> bool:
    source = item.source.lower().replace("-", "_")
    return (
        "multi_timeframe" in source
        or "mtf" in source
        or "higher_timeframe" in source
    )


def _opposite_direction(direction: EvidenceDirection) -> EvidenceDirection:
    if direction is EvidenceDirection.BUY:
        return EvidenceDirection.SELL
    if direction is EvidenceDirection.SELL:
        return EvidenceDirection.BUY
    return EvidenceDirection.NEUTRAL


def _max_level(current: ConflictLevel, candidate: ConflictLevel) -> ConflictLevel:
    ranks = {
        ConflictLevel.NONE: 0,
        ConflictLevel.LOW: 1,
        ConflictLevel.MEDIUM: 2,
        ConflictLevel.HIGH: 3,
    }
    return candidate if ranks[candidate] > ranks[current] else current


def _max_action(current: ConflictAction, candidate: ConflictAction) -> ConflictAction:
    ranks = {
        ConflictAction.CONTINUE: 0,
        ConflictAction.REDUCE_SIZE: 1,
        ConflictAction.WAIT: 2,
    }
    return candidate if ranks[candidate] > ranks[current] else current
