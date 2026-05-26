"""Human review record for signal research feedback."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from enum import Enum
import json
from typing import Any, Mapping
from uuid import uuid4


@dataclass(frozen=True)
class SignalReview:
    """Immutable review metadata; overrides never mutate the original signal."""

    signal_id: str
    symbol: str
    timeframe: str
    final_signal: str
    setup_type: str | None = None
    confluence_score: float | None = None
    decision_trace_id: str | None = None
    user_feedback: str | None = None
    user_override: str | None = None
    override_reason: str | None = None
    tags: list[str] = field(default_factory=list)
    review_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def with_feedback(
        self,
        user_feedback: str | None = None,
        user_override: str | None = None,
        override_reason: str | None = None,
        tags: list[str] | None = None,
    ) -> "SignalReview":
        """Return a copy with human feedback while preserving final_signal."""
        merged_tags = list(self.tags)
        if tags:
            for tag in tags:
                if tag not in merged_tags:
                    merged_tags.append(str(tag))
        return replace(
            self,
            user_feedback=user_feedback if user_feedback is not None else self.user_feedback,
            user_override=user_override if user_override is not None else self.user_override,
            override_reason=override_reason if override_reason is not None else self.override_reason,
            tags=merged_tags,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "review_id": self.review_id,
            "signal_id": self.signal_id,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "final_signal": self.final_signal,
            "setup_type": self.setup_type,
            "confluence_score": self.confluence_score,
            "decision_trace_id": self.decision_trace_id,
            "user_feedback": self.user_feedback,
            "user_override": self.user_override,
            "override_reason": self.override_reason,
            "tags": list(self.tags),
            "created_at": self.created_at.isoformat(),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "SignalReview":
        return cls(
            review_id=str(payload.get("review_id") or uuid4()),
            signal_id=str(payload.get("signal_id") or "unknown_signal"),
            symbol=str(payload.get("symbol") or "UNKNOWN"),
            timeframe=str(payload.get("timeframe") or "UNKNOWN"),
            final_signal=_enum_value(payload.get("final_signal") or "UNKNOWN"),
            setup_type=_optional_string(payload.get("setup_type")),
            confluence_score=_optional_float(payload.get("confluence_score")),
            decision_trace_id=_optional_string(payload.get("decision_trace_id")),
            user_feedback=_optional_string(payload.get("user_feedback")),
            user_override=_optional_string(payload.get("user_override")),
            override_reason=_optional_string(payload.get("override_reason")),
            tags=_string_list(payload.get("tags")),
            created_at=_parse_datetime(payload.get("created_at")),
        )


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if value:
        try:
            parsed = datetime.fromisoformat(str(value))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except ValueError:
            pass
    return datetime.now(UTC)


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    try:
        return [str(item) for item in value]
    except TypeError:
        return []


def _enum_value(value: Any) -> str:
    if isinstance(value, Enum):
        return str(value.value)
    return str(value)
