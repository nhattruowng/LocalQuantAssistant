"""Evidence model for explainable market reasoning."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from typing import Any

from domain.trading_types import EvidenceType, SignalDirection


EvidenceDirection = SignalDirection
_VALID_EVIDENCE_DIRECTIONS = {
    EvidenceDirection.BUY,
    EvidenceDirection.SELL,
    EvidenceDirection.NEUTRAL,
}


@dataclass(frozen=True)
class Evidence:
    """Single explainable evidence item for decision reasoning."""

    name: str
    source: str
    direction: EvidenceDirection
    score: float
    confidence: float
    weight: float
    evidence_type: EvidenceType
    reason: str
    impact_on_score: float = 0.0
    is_critical: bool = False

    def __post_init__(self) -> None:
        """Normalize enum-like inputs and validate bounded scores."""
        if isinstance(self.direction, str):
            object.__setattr__(self, "direction", EvidenceDirection(self.direction.upper()))
        if isinstance(self.evidence_type, str):
            object.__setattr__(self, "evidence_type", EvidenceType(self.evidence_type.upper()))
        if self.direction not in _VALID_EVIDENCE_DIRECTIONS:
            raise ValueError("Evidence direction must be BUY, SELL, or NEUTRAL.")
        object.__setattr__(self, "score", _unit_float(self.score, "score"))
        object.__setattr__(self, "confidence", _unit_float(self.confidence, "confidence"))
        object.__setattr__(self, "weight", _unit_float(self.weight, "weight"))
        object.__setattr__(self, "impact_on_score", _float(self.impact_on_score, "impact_on_score"))

    def to_dict(self) -> dict[str, Any]:
        """Serialize evidence into API-friendly primitive values."""
        data = asdict(self)
        data["direction"] = self.direction.value
        data["evidence_type"] = self.evidence_type.value
        return data

    def to_json(self) -> str:
        """Serialize evidence as JSON."""
        return json.dumps(self.to_dict())


def support(
    name: str,
    source: str,
    direction: EvidenceDirection | str,
    score: float,
    confidence: float,
    weight: float,
    reason: str,
    impact_on_score: float = 0.0,
    is_critical: bool = False,
) -> Evidence:
    """Build SUPPORT evidence without coupling to signal generation."""
    return _evidence(
        name=name,
        source=source,
        direction=direction,
        score=score,
        confidence=confidence,
        weight=weight,
        evidence_type=EvidenceType.SUPPORT,
        reason=reason,
        impact_on_score=impact_on_score,
        is_critical=is_critical,
    )


def against(
    name: str,
    source: str,
    direction: EvidenceDirection | str,
    score: float,
    confidence: float,
    weight: float,
    reason: str,
    impact_on_score: float = 0.0,
    is_critical: bool = False,
) -> Evidence:
    """Build AGAINST evidence without coupling to signal generation."""
    return _evidence(
        name=name,
        source=source,
        direction=direction,
        score=score,
        confidence=confidence,
        weight=weight,
        evidence_type=EvidenceType.AGAINST,
        reason=reason,
        impact_on_score=impact_on_score,
        is_critical=is_critical,
    )


def warning(
    name: str,
    source: str,
    reason: str,
    score: float,
    confidence: float,
    weight: float,
    direction: EvidenceDirection | str = EvidenceDirection.NEUTRAL,
    impact_on_score: float = 0.0,
    is_critical: bool = False,
) -> Evidence:
    """Build WARNING evidence, defaulting to neutral directional bias."""
    return _evidence(
        name=name,
        source=source,
        direction=direction,
        score=score,
        confidence=confidence,
        weight=weight,
        evidence_type=EvidenceType.WARNING,
        reason=reason,
        impact_on_score=impact_on_score,
        is_critical=is_critical,
    )


def _evidence(
    name: str,
    source: str,
    direction: EvidenceDirection | str,
    score: float,
    confidence: float,
    weight: float,
    evidence_type: EvidenceType,
    reason: str,
    impact_on_score: float,
    is_critical: bool,
) -> Evidence:
    return Evidence(
        name=name,
        source=source,
        direction=direction,
        score=score,
        confidence=confidence,
        weight=weight,
        evidence_type=evidence_type,
        reason=reason,
        impact_on_score=impact_on_score,
        is_critical=is_critical,
    )


def _unit_float(value: object, field_name: str) -> float:
    parsed = _float(value, field_name)
    if parsed < 0.0 or parsed > 1.0:
        raise ValueError(f"Evidence {field_name} must be between 0 and 1.")
    return parsed


def _float(value: object, field_name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"Evidence {field_name} must be numeric.")
    try:
        return float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"Evidence {field_name} must be numeric.") from error
