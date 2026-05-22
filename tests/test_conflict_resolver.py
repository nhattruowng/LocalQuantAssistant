"""Tests for evidence conflict resolution."""

from __future__ import annotations

from reasoning.conflict_resolver import (
    ConflictAction,
    ConflictLevel,
    ConflictResolver,
    ConflictType,
)
from reasoning.evidence import Evidence, EvidenceDirection, EvidenceType


def test_buy_sell_balance_recommends_wait() -> None:
    resolver = ConflictResolver()
    result = resolver.evaluate(
        [
            _evidence("Buy structure", "market_structure", EvidenceDirection.BUY, 0.8, 0.8),
            _evidence("Sell pressure", "price_action", EvidenceDirection.SELL, 0.79, 0.8),
        ]
    )

    assert result.conflict_level is ConflictLevel.HIGH
    assert result.recommended_action is ConflictAction.WAIT
    assert any(ConflictType.BUY_SELL_EVIDENCE_CONFLICT.value in reason for reason in result.conflict_reasons)


def test_breakout_with_rejection_is_high_conflict() -> None:
    resolver = ConflictResolver()
    result = resolver.evaluate(
        [
            _evidence("Breakout confirmed", "price_action", EvidenceDirection.BUY, 0.9, 0.9),
            _evidence(
                "Rejection wick",
                "price_action",
                EvidenceDirection.SELL,
                0.9,
                0.9,
                reason="Large rejection wick after breakout",
            ),
        ]
    )

    assert result.conflict_level is ConflictLevel.HIGH
    assert result.conflict_penalty > 0.2
    assert any(ConflictType.BREAKOUT_VS_REJECTION.value in reason for reason in result.conflict_reasons)


def test_strong_mtf_conflict_reduces_size_or_wait() -> None:
    resolver = ConflictResolver()
    result = resolver.evaluate(
        [
            _evidence("Entry trigger", "price_action", EvidenceDirection.BUY, 0.8, 0.8),
            _evidence("HTF downtrend", "multi_timeframe_alignment", EvidenceDirection.SELL, 0.95, 0.95),
        ]
    )

    assert result.conflict_penalty > 0.0
    assert result.recommended_action in {ConflictAction.REDUCE_SIZE, ConflictAction.WAIT}
    assert any(ConflictType.MTF_VS_ENTRY_SIGNAL.value in reason for reason in result.conflict_reasons)


def test_model_vs_price_action_conflict_has_moderate_penalty() -> None:
    resolver = ConflictResolver()
    result = resolver.evaluate(
        [
            _evidence("Model buy", "model_probability", EvidenceDirection.BUY, 0.9, 0.85),
            _evidence("PA sell", "price_action", EvidenceDirection.SELL, 0.65, 0.75),
            _evidence("ICT sell", "ict_confluence", EvidenceDirection.SELL, 0.6, 0.7),
        ]
    )

    assert result.conflict_penalty > 0.05
    assert result.conflict_level in {ConflictLevel.MEDIUM, ConflictLevel.HIGH}
    assert any(ConflictType.MODEL_VS_PRICE_ACTION.value in reason for reason in result.conflict_reasons)


def test_no_conflict_recommends_continue() -> None:
    resolver = ConflictResolver()
    result = resolver.evaluate(
        [
            _evidence("Regime align", "regime_alignment", EvidenceDirection.BUY, 0.8, 0.9),
            _evidence("PA align", "price_action", EvidenceDirection.BUY, 0.75, 0.85),
            _evidence("Volume confirm", "volume_confirmation", EvidenceDirection.BUY, 0.7, 0.8),
        ]
    )

    assert result.conflict_level is ConflictLevel.NONE
    assert result.conflict_penalty == 0.0
    assert result.recommended_action is ConflictAction.CONTINUE


def test_risk_guard_failure_forces_wait() -> None:
    resolver = ConflictResolver()
    result = resolver.evaluate(
        [
            _evidence("Model buy", "model_probability", EvidenceDirection.BUY, 0.8, 0.8),
            Evidence(
                name="Risk guard blocked",
                source="risk_guard",
                direction=EvidenceDirection.NEUTRAL,
                score=1.0,
                confidence=1.0,
                weight=1.0,
                evidence_type=EvidenceType.WARNING,
                reason="Blocked by risk guard fail",
                impact_on_score=0.0,
                is_critical=True,
            ),
        ]
    )

    assert result.conflict_level is ConflictLevel.HIGH
    assert result.recommended_action is ConflictAction.WAIT
    assert any(ConflictType.RISK_VS_SIGNAL.value in reason for reason in result.conflict_reasons)


def _evidence(
    name: str,
    source: str,
    direction: EvidenceDirection,
    score: float,
    confidence: float,
    reason: str | None = None,
) -> Evidence:
    return Evidence(
        name=name,
        source=source,
        direction=direction,
        score=score,
        confidence=confidence,
        weight=1.0,
        evidence_type=EvidenceType.SUPPORT,
        reason=reason or name,
        impact_on_score=0.0,
        is_critical=False,
    )
