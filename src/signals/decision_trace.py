"""Decision trace models for step-by-step signal reasoning."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
import json
from typing import Any
from uuid import uuid4


@dataclass
class DecisionStep:
    """One transformation step in the signal decision flow."""

    step_name: str
    input_score: float
    output_score: float
    delta: float | None = None
    passed: bool = True
    details: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        """Derive delta automatically when omitted."""
        if self.delta is None:
            self.delta = round(float(self.output_score) - float(self.input_score), 10)

    def add_warning(self, warning: str) -> None:
        """Append one warning message to the step."""
        self.warnings.append(warning)

    def to_dict(self) -> dict[str, Any]:
        """Serialize step into API-friendly primitive values."""
        return {
            "step_name": self.step_name,
            "input_score": self.input_score,
            "output_score": self.output_score,
            "delta": self.delta,
            "passed": self.passed,
            "details": self.details,
            "warnings": list(self.warnings),
            "timestamp": self.timestamp.isoformat(),
        }

    def to_json(self) -> str:
        """Serialize step as JSON."""
        return json.dumps(self.to_dict())


@dataclass
class DecisionTrace:
    """Complete trace for one final signal decision."""

    symbol: str
    timeframe: str
    final_signal: str = "WAIT"
    final_confidence: float = 0.0
    trace_id: str = field(default_factory=lambda: str(uuid4()))
    model_version: str | None = None
    config_hash: str | None = None
    steps: list[DecisionStep] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    warnings: list[str] = field(default_factory=list)

    def add_step(self, step: DecisionStep | None = None, **step_kwargs: Any) -> DecisionStep:
        """Append a decision step to the trace."""
        if step is None:
            step = DecisionStep(**step_kwargs)
        self.steps.append(step)
        return step

    def add_warning(self, warning: str) -> None:
        """Append one trace-level warning."""
        self.warnings.append(warning)

    def set_final(self, final_signal: str | Enum, final_confidence: float) -> None:
        """Set the final decision without rebuilding the trace."""
        self.final_signal = _enum_value(final_signal)
        self.final_confidence = float(final_confidence)

    def to_dict(self) -> dict[str, Any]:
        """Serialize trace into API-friendly primitive values."""
        return {
            "trace_id": self.trace_id,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "model_version": self.model_version,
            "config_hash": self.config_hash,
            "steps": [step.to_dict() for step in self.steps],
            "final_signal": self.final_signal,
            "final_confidence": self.final_confidence,
            "created_at": self.created_at.isoformat(),
            "warnings": list(self.warnings),
        }

    def to_json(self) -> str:
        """Serialize trace as JSON."""
        return json.dumps(self.to_dict(), default=_json_default)


def _enum_value(value: str | Enum) -> str:
    if isinstance(value, Enum):
        return str(value.value)
    return str(value)


def _json_default(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    return str(value)
