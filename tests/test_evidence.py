"""Tests for market reasoning evidence primitives."""

from __future__ import annotations

import pytest

from reasoning.evidence import (
    Evidence,
    EvidenceDirection,
    EvidenceType,
    against,
    support,
    warning,
)


def test_create_valid_evidence() -> None:
    evidence = Evidence(
        name="Regime Alignment",
        source="regime",
        direction=EvidenceDirection.BUY,
        score=0.8,
        confidence=0.9,
        weight=0.7,
        evidence_type=EvidenceType.SUPPORT,
        reason="Trend regime supports long continuation.",
    )

    assert evidence.direction is EvidenceDirection.BUY
    assert evidence.score == 0.8
    assert evidence.confidence == 0.9
    assert evidence.weight == 0.7
    assert evidence.impact_on_score == 0.0
    assert evidence.is_critical is False


def test_score_outside_unit_range_raises_clear_error() -> None:
    with pytest.raises(ValueError, match="Evidence score must be between 0 and 1"):
        Evidence(
            name="Bad Score",
            source="test",
            direction=EvidenceDirection.NEUTRAL,
            score=1.2,
            confidence=0.9,
            weight=0.7,
            evidence_type=EvidenceType.WARNING,
            reason="Invalid score.",
        )


def test_to_dict_serializes_enum_values() -> None:
    evidence = Evidence(
        name="Volume Confirmation",
        source="volume",
        direction="SELL",
        score=0.5,
        confidence=0.6,
        weight=0.4,
        evidence_type="AGAINST",
        reason="Volume does not confirm the setup.",
        impact_on_score=-0.1,
        is_critical=True,
    )

    assert evidence.to_dict() == {
        "name": "Volume Confirmation",
        "source": "volume",
        "direction": "SELL",
        "score": 0.5,
        "confidence": 0.6,
        "weight": 0.4,
        "evidence_type": "AGAINST",
        "reason": "Volume does not confirm the setup.",
        "impact_on_score": -0.1,
        "is_critical": True,
    }


def test_evidence_helpers_set_evidence_type() -> None:
    support_item = support(
        name="Breakout",
        source="price_action",
        direction=EvidenceDirection.BUY,
        score=0.8,
        confidence=0.8,
        weight=0.9,
        reason="Breakout is confirmed.",
    )
    against_item = against(
        name="HTF Conflict",
        source="multi_timeframe",
        direction="SELL",
        score=0.6,
        confidence=0.7,
        weight=0.8,
        reason="Higher timeframe opposes the entry.",
    )
    warning_item = warning(
        name="Volatility",
        source="risk",
        reason="Volatility is elevated.",
        score=0.4,
        confidence=0.5,
        weight=0.6,
    )

    assert support_item.evidence_type is EvidenceType.SUPPORT
    assert against_item.evidence_type is EvidenceType.AGAINST
    assert warning_item.evidence_type is EvidenceType.WARNING
    assert warning_item.direction is EvidenceDirection.NEUTRAL
