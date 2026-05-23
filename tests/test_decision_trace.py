"""Tests for evidence and decision trace models."""

from __future__ import annotations

import json

from reasoning.evidence import Evidence, EvidenceDirection, EvidenceType
from signals.decision_trace import DecisionStep, DecisionTrace


def test_create_evidence() -> None:
    evidence = Evidence(
        name="RSI Momentum",
        source="indicators",
        direction=EvidenceDirection.BUY,
        score=0.78,
        confidence=0.82,
        weight=1.1,
        evidence_type=EvidenceType.SUPPORT,
        reason="RSI crossed above 50 with trend alignment.",
        impact_on_score=0.09,
        is_critical=False,
    )

    assert evidence.direction is EvidenceDirection.BUY
    assert evidence.evidence_type is EvidenceType.SUPPORT
    assert evidence.to_dict()["name"] == "RSI Momentum"


def test_create_decision_trace() -> None:
    trace = DecisionTrace(
        symbol="BTC/USDT",
        timeframe="15m",
        final_signal="BUY",
        final_confidence=0.74,
        model_version="v021",
        config_hash="abc123",
    )

    assert trace.symbol == "BTC/USDT"
    assert trace.trace_id
    assert trace.steps == []


def test_append_step() -> None:
    trace = DecisionTrace(
        symbol="ETH/USDT",
        timeframe="1h",
        final_signal="SELL",
        final_confidence=0.68,
    )

    step = trace.add_step(
        step_name="AdaptiveThresholdGate",
        input_score=0.71,
        output_score=0.66,
        passed=False,
        details={"threshold": 0.70},
    )
    step.add_warning("Score dropped below adaptive threshold.")
    trace.add_warning("Signal quality degraded after risk checks.")

    assert len(trace.steps) == 1
    assert isinstance(trace.steps[0], DecisionStep)
    assert step.delta == -0.05
    assert step.warnings == ["Score dropped below adaptive threshold."]
    assert trace.warnings == ["Signal quality degraded after risk checks."]


def test_trace_to_json_serialization() -> None:
    trace = DecisionTrace(
        symbol="SOL/USDT",
        timeframe="4h",
        final_signal="WAIT",
        final_confidence=0.35,
    )
    trace.add_step(
        DecisionStep(
            step_name="RiskGuard",
            input_score=0.62,
            output_score=0.35,
            passed=False,
            details={"volatility_level": "EXTREME"},
        )
    )

    payload = json.loads(trace.to_json())
    assert payload["symbol"] == "SOL/USDT"
    assert payload["steps"][0]["step_name"] == "RiskGuard"
    assert payload["created_at"]


def test_nullable_model_version_and_config_hash_do_not_crash() -> None:
    trace = DecisionTrace(
        symbol="XRP/USDT",
        timeframe="30m",
        final_signal="NEUTRAL",
        final_confidence=0.5,
        model_version=None,
        config_hash=None,
    )
    trace.add_step(
        step_name="BaseScore",
        input_score=0.5,
        output_score=0.5,
        passed=True,
    )

    payload = json.loads(trace.to_json())
    assert payload["model_version"] is None
    assert payload["config_hash"] is None
    assert payload["steps"][0]["delta"] == 0.0

