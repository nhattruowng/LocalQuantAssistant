"""Tests for canonical WAIT reason categories."""

from __future__ import annotations

from signals.wait_reason import (
    WAIT_REASON,
    WaitReason,
    infer_wait_reason,
    normalize_wait_reason,
)


def test_wait_reason_alias_serializes_to_string() -> None:
    assert WAIT_REASON.WAIT_LOW_CONFIDENCE is WaitReason.WAIT_LOW_CONFIDENCE
    assert WAIT_REASON.WAIT_LOW_CONFIDENCE.value == "WAIT_LOW_CONFIDENCE"


def test_invalid_wait_reason_falls_back_to_no_clear_setup() -> None:
    assert normalize_wait_reason("unknown") is WaitReason.WAIT_NO_CLEAR_SETUP
    assert normalize_wait_reason(None) is WaitReason.WAIT_NO_CLEAR_SETUP


def test_infer_wait_reason_distinguishes_risk_block() -> None:
    reason = infer_wait_reason(
        ["Risk/reward 1.20 is below 2.00."],
        diagnostics={"blocked_by_risk_guard": True},
    )

    assert reason is WaitReason.WAIT_RISK_BLOCK


def test_infer_wait_reason_distinguishes_safety_filter() -> None:
    reason = infer_wait_reason(
        ["Blocked by safety filter: custom rule triggered."],
        diagnostics={
            "blocked_by_risk_guard": True,
            "blocked_by_safety_filter": True,
            "safety_filters": [{"name": "custom_rule", "blocked": True}],
        },
    )

    assert reason is WaitReason.WAIT_SAFETY_FILTER


def test_infer_wait_reason_distinguishes_strategy_conflict() -> None:
    reason = infer_wait_reason(
        ["Conflicting BUY/SELL opinions conflict with a small score margin."],
        diagnostics={"conflict_result": {"has_conflict": True}},
    )

    assert reason is WaitReason.WAIT_STRATEGY_CONFLICT
