"""Tests for confluence scoring engine."""

from __future__ import annotations

import pytest

from reasoning.confluence_engine import ConfluenceEngine
from reasoning.evidence import Evidence, EvidenceDirection, EvidenceType
from signals.decision_trace import DecisionTrace


def test_confluent_buy_evidence_creates_high_score() -> None:
    engine = ConfluenceEngine()
    evidence = [
        _evidence("Regime Alignment", "regime_alignment", EvidenceType.SUPPORT, 0.9, 0.9),
        _evidence("Market Structure", "market_structure", EvidenceType.SUPPORT, 0.9, 0.85),
        _evidence("Price Action", "price_action", EvidenceType.SUPPORT, 0.85, 0.9),
        _evidence("Volume Confirmation", "volume_confirmation", EvidenceType.SUPPORT, 0.8, 0.8),
    ]

    result = engine.evaluate(evidence)

    assert result.normalized_score > 0.7
    assert len(result.evidence_for) == 4
    assert not result.evidence_against


def test_mixed_buy_sell_evidence_still_returns_breakdown() -> None:
    engine = ConfluenceEngine()
    evidence = [
        _evidence("Market Structure", "market_structure", EvidenceType.SUPPORT, 0.85, 0.8),
        _evidence("Model Probability", "model_probability", EvidenceType.AGAINST, 0.7, 0.75),
        _evidence("Volatility Warning", "price_action", EvidenceType.WARNING, 0.65, 0.7),
    ]

    result = engine.evaluate(evidence)

    assert len(result.evidence_for) == 1
    assert len(result.evidence_against) == 1
    assert len(result.warnings) == 1
    assert len(result.score_breakdown) == 3
    assert 0.0 <= result.normalized_score <= 1.0


def test_empty_evidence_returns_configurable_neutral() -> None:
    default_result = ConfluenceEngine().evaluate([])
    neutral_result = ConfluenceEngine(empty_score=0.5).evaluate([])

    assert default_result.normalized_score == pytest.approx(0.0)
    assert neutral_result.normalized_score == pytest.approx(0.5)


def test_missing_sources_are_weight_normalized() -> None:
    engine = ConfluenceEngine()
    result = engine.evaluate(
        [
            _evidence("Regime", "regime_alignment", EvidenceType.SUPPORT, 0.8, 0.9),
            _evidence("Structure", "market_structure", EvidenceType.SUPPORT, 0.8, 0.9),
        ]
    )
    by_source = {item["source_key"]: item for item in result.score_breakdown}

    assert by_source["regime_alignment"]["weight"] == pytest.approx(0.4)
    assert by_source["market_structure"]["weight"] == pytest.approx(0.6)


def test_impact_on_score_matches_score_confidence_weight() -> None:
    engine = ConfluenceEngine()
    result = engine.evaluate(
        [
            _evidence("Structure", "market_structure", EvidenceType.SUPPORT, 0.8, 0.5),
            _evidence("Model", "model_probability", EvidenceType.AGAINST, 0.5, 0.4),
        ]
    )

    for item in result.score_breakdown:
        expected = item["score"] * item["confidence"] * item["weight"]
        if item["evidence_type"] == EvidenceType.SUPPORT.value:
            assert item["impact_on_score"] == pytest.approx(expected)
        else:
            assert item["impact_on_score"] == pytest.approx(-expected)


def test_confluence_adds_decision_trace_step() -> None:
    trace = DecisionTrace(
        symbol="BTC/USDT",
        timeframe="15m",
        final_signal="BUY",
        final_confidence=0.7,
    )
    result = ConfluenceEngine().evaluate(
        [_evidence("Structure", "market_structure", EvidenceType.SUPPORT, 0.8, 0.9)],
        trace=trace,
    )

    assert result.normalized_score > 0.0
    assert trace.steps
    assert trace.steps[-1].step_name == "confluence_score"


def _evidence(
    name: str,
    source: str,
    evidence_type: EvidenceType,
    score: float,
    confidence: float,
) -> Evidence:
    return Evidence(
        name=name,
        source=source,
        direction=EvidenceDirection.BUY,
        score=score,
        confidence=confidence,
        weight=1.0,
        evidence_type=evidence_type,
        reason=f"{name} reason",
        impact_on_score=0.0,
        is_critical=False,
    )

