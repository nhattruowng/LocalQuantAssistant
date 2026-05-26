"""Safe JSON-only decision trace summarization."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import re
from typing import Any, Mapping


FORBIDDEN_ACTIONS_CHECKED = {
    "no_trade_signal_generated": True,
    "no_riskguard_override": True,
    "no_live_config_change": True,
}
ASSISTANT_SCHEMA_KEYS = {
    "summary",
    "conflicts",
    "hypotheses",
    "recommended_backtests",
    "forbidden_actions_checked",
}
_FORBIDDEN_VERBS = (
    "override riskguard",
    "riskguard override",
    "change live config",
    "promote model",
    "auto trade",
)
_SIGNAL_WORD_RE = re.compile(r"\b(BUY|SELL|WAIT)\b", flags=re.IGNORECASE)


@dataclass(frozen=True)
class ResearchAssistantResponse:
    """Strict JSON schema for the research assistant output."""

    summary: str = ""
    conflicts: list[str] = field(default_factory=list)
    hypotheses: list[str] = field(default_factory=list)
    recommended_backtests: list[str] = field(default_factory=list)
    forbidden_actions_checked: dict[str, bool] = field(default_factory=lambda: dict(FORBIDDEN_ACTIONS_CHECKED))

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": _sanitize_text(self.summary),
            "conflicts": [_sanitize_text(item) for item in self.conflicts],
            "hypotheses": [_sanitize_text(item) for item in self.hypotheses],
            "recommended_backtests": [_sanitize_text(item) for item in self.recommended_backtests],
            "forbidden_actions_checked": dict(FORBIDDEN_ACTIONS_CHECKED),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)


class TraceSummarizer:
    """Summarize decision traces for research without generating trade decisions."""

    def summarize(
        self,
        decision_trace: Mapping[str, Any] | None,
        review: Mapping[str, Any] | None = None,
    ) -> ResearchAssistantResponse:
        trace = dict(decision_trace or {})
        steps = [step for step in trace.get("steps", []) if isinstance(step, Mapping)]
        failed_steps = [str(step.get("step_name", "unnamed_step")) for step in steps if not bool(step.get("passed", True))]
        warnings = _collect_warnings(trace, steps)
        summary = (
            f"Reviewed {len(steps)} causal decision steps with "
            f"{len(failed_steps)} failed checks and {len(warnings)} warnings."
        )
        conflicts = [
            f"Conflict or failed check at {name}."
            for name in failed_steps[:5]
        ]
        conflicts.extend(warnings[:5])
        hypotheses = _hypotheses_from_review(review)
        recommended_backtests = [
            "Run offline ablation around the highest-impact evidence group.",
            "Run walk-forward validation for the reviewed setup bucket.",
        ]
        return ResearchAssistantResponse(
            summary=summary,
            conflicts=conflicts,
            hypotheses=hypotheses,
            recommended_backtests=recommended_backtests,
        )


def validate_assistant_output(payload: Mapping[str, Any]) -> bool:
    """Validate the assistant schema and safety flags."""
    if set(payload.keys()) != ASSISTANT_SCHEMA_KEYS:
        return False
    if not isinstance(payload.get("summary"), str):
        return False
    for key in ("conflicts", "hypotheses", "recommended_backtests"):
        if not isinstance(payload.get(key), list):
            return False
        if any(not isinstance(item, str) for item in payload[key]):
            return False
    return payload.get("forbidden_actions_checked") == FORBIDDEN_ACTIONS_CHECKED


def _collect_warnings(trace: Mapping[str, Any], steps: list[Mapping[str, Any]]) -> list[str]:
    warnings: list[str] = []
    raw_trace_warnings = trace.get("warnings", [])
    if isinstance(raw_trace_warnings, list):
        warnings.extend(str(item) for item in raw_trace_warnings)
    for step in steps:
        raw = step.get("warnings", [])
        if isinstance(raw, list):
            warnings.extend(str(item) for item in raw)
    return [_sanitize_text(item) for item in warnings if item]


def _hypotheses_from_review(review: Mapping[str, Any] | None) -> list[str]:
    if not review:
        return ["Investigate whether low-scoring evidence groups explain weak outcomes."]
    tags = review.get("tags")
    if isinstance(tags, list) and tags:
        joined = ", ".join(str(tag) for tag in tags[:5])
        return [f"Review tags suggest researching these buckets: {joined}."]
    if review.get("user_feedback"):
        return ["Human feedback suggests testing the same setup bucket under stricter filters."]
    return ["Human review available; compare against nearby historical setups."]


def _sanitize_text(value: Any) -> str:
    text = str(value)
    text = _SIGNAL_WORD_RE.sub("directional-decision", text)
    lowered = text.lower()
    for phrase in _FORBIDDEN_VERBS:
        if phrase in lowered:
            text = text.replace(phrase, "forbidden action")
            text = text.replace(phrase.title(), "forbidden action")
    return text
