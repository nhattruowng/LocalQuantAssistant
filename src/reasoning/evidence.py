"""Evidence model for explainable market reasoning."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import json
from typing import Any


class EvidenceDirection(str, Enum):
    """Directional bias represented by one evidence item."""

    BUY = "BUY"
    SELL = "SELL"
    NEUTRAL = "NEUTRAL"


class EvidenceType(str, Enum):
    """How evidence contributes to a decision."""

    SUPPORT = "SUPPORT"
    AGAINST = "AGAINST"
    WARNING = "WARNING"


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
    impact_on_score: float
    is_critical: bool = False

    def __post_init__(self) -> None:
        """Normalize enum-like string inputs."""
        if isinstance(self.direction, str):
            object.__setattr__(self, "direction", EvidenceDirection(self.direction.upper()))
        if isinstance(self.evidence_type, str):
            object.__setattr__(self, "evidence_type", EvidenceType(self.evidence_type.upper()))

    def to_dict(self) -> dict[str, Any]:
        """Serialize evidence into API-friendly primitive values."""
        data = asdict(self)
        data["direction"] = self.direction.value
        data["evidence_type"] = self.evidence_type.value
        return data

    def to_json(self) -> str:
        """Serialize evidence as JSON."""
        return json.dumps(self.to_dict())

