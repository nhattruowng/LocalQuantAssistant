"""Tests for shared trading reasoning enum types."""

from __future__ import annotations

import json

from domain.trading_types import (
    ConflictLevel,
    EvidenceType,
    RecommendedAction,
    SetupType,
    SignalDirection,
)


def test_trading_types_serialize_to_json_strings() -> None:
    payload = {
        "signal": SignalDirection.BUY,
        "evidence_type": EvidenceType.SUPPORT,
        "setup_type": SetupType.CLEAN_BREAKOUT,
        "conflict_level": ConflictLevel.HIGH,
        "recommended_action": RecommendedAction.REDUCE_SIZE,
    }

    assert json.loads(json.dumps(payload)) == {
        "signal": "BUY",
        "evidence_type": "SUPPORT",
        "setup_type": "CLEAN_BREAKOUT",
        "conflict_level": "HIGH",
        "recommended_action": "REDUCE_SIZE",
    }


def test_legacy_enum_imports_resolve_to_shared_types() -> None:
    from domain.enums import TradingAction
    from reasoning.conflict_resolver import ConflictAction
    from reasoning.conflict_resolver import ConflictLevel as LegacyConflictLevel
    from reasoning.evidence import EvidenceDirection
    from reasoning.evidence import EvidenceType as LegacyEvidenceType
    from reasoning.setup_classifier import SetupType as LegacySetupType
    from signals.models import SignalType

    assert SignalType.BUY is SignalDirection.BUY
    assert TradingAction.WAIT.value == SignalDirection.WAIT.value
    assert EvidenceDirection.NEUTRAL is SignalDirection.NEUTRAL
    assert LegacyEvidenceType.WARNING is EvidenceType.WARNING
    assert LegacySetupType.NO_CLEAR_SETUP is SetupType.NO_CLEAR_SETUP
    assert LegacyConflictLevel.MEDIUM is ConflictLevel.MEDIUM
    assert ConflictAction.CONTINUE is RecommendedAction.CONTINUE
