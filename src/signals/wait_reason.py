"""WAIT reason categorization for signal decisions."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from enum import Enum


class WaitReason(str, Enum):
    """Canonical WAIT reason categories used by analytics and UI."""

    WAIT_LOW_CONFIDENCE = "WAIT_LOW_CONFIDENCE"
    WAIT_STRATEGY_CONFLICT = "WAIT_STRATEGY_CONFLICT"
    WAIT_MTF_CONFLICT = "WAIT_MTF_CONFLICT"
    WAIT_RISK_BLOCK = "WAIT_RISK_BLOCK"
    WAIT_SAFETY_FILTER = "WAIT_SAFETY_FILTER"
    WAIT_DATA_QUALITY = "WAIT_DATA_QUALITY"
    WAIT_MODEL_UNCERTAIN = "WAIT_MODEL_UNCERTAIN"
    WAIT_HIGH_VOLATILITY = "WAIT_HIGH_VOLATILITY"
    WAIT_TRANSITION_WARNING = "WAIT_TRANSITION_WARNING"
    WAIT_INDUCEMENT_RISK = "WAIT_INDUCEMENT_RISK"
    WAIT_NO_CLEAR_SETUP = "WAIT_NO_CLEAR_SETUP"


WAIT_REASON = WaitReason


def normalize_wait_reason(value: object) -> WaitReason:
    """Return a valid wait reason or fallback to WAIT_NO_CLEAR_SETUP."""
    if isinstance(value, WaitReason):
        return value
    if isinstance(value, str):
        try:
            return WaitReason(value.strip().upper())
        except ValueError:
            return WaitReason.WAIT_NO_CLEAR_SETUP
    return WaitReason.WAIT_NO_CLEAR_SETUP


def infer_wait_reason(
    reasons: Sequence[str],
    diagnostics: Mapping[str, object] | None = None,
    volatility_level: str | None = None,
    transition_warning: bool = False,
) -> WaitReason:
    """Infer WAIT category from reason text and diagnostics."""
    if diagnostics and "wait_reason" in diagnostics:
        return normalize_wait_reason(diagnostics.get("wait_reason"))

    text = " ".join(str(reason).lower() for reason in reasons)
    diagnostics = diagnostics or {}

    if (
        "multi-timeframe conflict" in text
        or "higher timeframe conflict" in text
        or bool(_nested_bool(diagnostics, "multi_timeframe", "conflict"))
        or bool(_nested_bool(diagnostics, "multi_timeframe", "blocked"))
    ):
        return WaitReason.WAIT_MTF_CONFLICT

    if (
        "fakeout" in text
        or "mean reversion danger" in text
        or "inducement" in text
    ):
        return WaitReason.WAIT_INDUCEMENT_RISK

    if (
        "volatility is extreme" in text
        or "extreme volatility" in text
        or str(volatility_level or "").upper() == "EXTREME"
    ):
        return WaitReason.WAIT_HIGH_VOLATILITY

    if (
        "blocked by safety filter" in text
        or bool(diagnostics.get("blocked_by_safety_filter", False))
        or _has_blocked_filter(diagnostics)
    ):
        return WaitReason.WAIT_SAFETY_FILTER

    if (
        "risk plan failed" in text
        or "no risk plan was built" in text
        or "data quality" in text
        or bool(diagnostics.get("blocked_by_data_quality", False))
    ):
        return WaitReason.WAIT_DATA_QUALITY

    if (
        "risk guard" in text
        or "circuit breaker" in text
        or bool(diagnostics.get("blocked_by_risk_guard", False))
        or diagnostics.get("risk_guard_state") is not None
    ):
        return WaitReason.WAIT_RISK_BLOCK

    if (
        "conflict with a small score margin" in text
        or "conflicting buy/sell opinions" in text
        or "buy/sell opinions conflict" in text
        or bool(_nested_bool(diagnostics, "conflict_result", "has_conflict"))
    ):
        return WaitReason.WAIT_STRATEGY_CONFLICT

    if (
        "below trend threshold" in text
        or "below breakout threshold" in text
        or "below mean reversion threshold" in text
        or "below adaptive threshold" in text
        or "min_opinion_score" in text
        or "no strategy candidate passed ensemble threshold" in text
    ):
        return WaitReason.WAIT_LOW_CONFIDENCE

    if (
        "uncertainty is high" in text
        or "calibrated probability is required but unavailable" in text
        or "regime confidence is low; threshold increased" in text
    ):
        return WaitReason.WAIT_MODEL_UNCERTAIN

    if transition_warning or "transition warning" in text or "regime is unstable" in text:
        return WaitReason.WAIT_TRANSITION_WARNING

    return WaitReason.WAIT_NO_CLEAR_SETUP


def _nested_bool(payload: Mapping[str, object], key: str, nested_key: str) -> bool:
    node = payload.get(key)
    return isinstance(node, Mapping) and bool(node.get(nested_key, False))


def _has_blocked_filter(diagnostics: Mapping[str, object]) -> bool:
    filters = diagnostics.get("safety_filters", [])
    return isinstance(filters, list) and any(
        isinstance(item, Mapping) and bool(item.get("blocked", False))
        for item in filters
    )


__all__ = [
    "WAIT_REASON",
    "WaitReason",
    "infer_wait_reason",
    "normalize_wait_reason",
]
