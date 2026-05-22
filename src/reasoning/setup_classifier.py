"""Setup-type classification from confluence evidence."""

from __future__ import annotations

from enum import Enum

from reasoning.conflict_resolver import ConflictLevel, ConflictResult
from reasoning.evidence import Evidence, EvidenceType


class SetupType(str, Enum):
    """High-level setup taxonomy for explanation and analytics."""

    TREND_CONTINUATION_PULLBACK = "TREND_CONTINUATION_PULLBACK"
    TREND_BREAKOUT_CONTINUATION = "TREND_BREAKOUT_CONTINUATION"
    TREND_EXHAUSTION_WARNING = "TREND_EXHAUSTION_WARNING"
    CLEAN_BREAKOUT = "CLEAN_BREAKOUT"
    RANGE_BREAKOUT_PREPARATION = "RANGE_BREAKOUT_PREPARATION"
    FAKEOUT_RISK = "FAKEOUT_RISK"
    LIQUIDITY_SWEEP_REVERSAL = "LIQUIDITY_SWEEP_REVERSAL"
    RANGE_REVERSION = "RANGE_REVERSION"
    MEAN_REVERSION_DANGER = "MEAN_REVERSION_DANGER"
    CONFLICTED = "CONFLICTED"
    NO_CLEAR_SETUP = "NO_CLEAR_SETUP"


class SetupClassifier:
    """Classify setup type from evidence patterns and conflict result."""

    def classify(
        self,
        evidence: list[Evidence],
        conflict: ConflictResult,
        final_score: float,
    ) -> SetupType:
        if conflict.conflict_level is ConflictLevel.HIGH:
            return SetupType.CONFLICTED

        has_breakout = _contains(evidence, ("breakout",), evidence_type=EvidenceType.SUPPORT)
        has_rejection = _contains(evidence, ("rejection", "wick"), evidence_type=None)
        has_choch = _contains(evidence, ("change of character", "choch"), evidence_type=None)
        has_hh_hl = _contains(evidence, ("hh_hl",), evidence_type=None) or _contains(
            evidence,
            ("uptrend",),
            evidence_type=None,
        )
        has_lh_ll = _contains(evidence, ("lh_ll",), evidence_type=None) or _contains(
            evidence,
            ("downtrend",),
            evidence_type=None,
        )
        has_range = _contains(evidence, ("range",), evidence_type=None)
        has_sweep = _contains(evidence, ("sweep", "liquidity"), evidence_type=None)

        if has_breakout and has_rejection:
            return SetupType.FAKEOUT_RISK
        if has_sweep and has_choch:
            return SetupType.LIQUIDITY_SWEEP_REVERSAL
        if has_breakout and final_score >= 0.75:
            return SetupType.CLEAN_BREAKOUT
        if has_breakout and final_score >= 0.60:
            return SetupType.TREND_BREAKOUT_CONTINUATION
        if has_hh_hl and final_score >= 0.60:
            return SetupType.TREND_CONTINUATION_PULLBACK
        if has_lh_ll and has_choch:
            return SetupType.TREND_EXHAUSTION_WARNING
        if has_range and final_score >= 0.58:
            return SetupType.RANGE_REVERSION
        if has_range and final_score >= 0.45:
            return SetupType.RANGE_BREAKOUT_PREPARATION
        if _contains(evidence, ("mean reversion danger",), evidence_type=None):
            return SetupType.MEAN_REVERSION_DANGER
        return SetupType.NO_CLEAR_SETUP


def _contains(
    evidence: list[Evidence],
    keywords: tuple[str, ...],
    evidence_type: EvidenceType | None,
) -> bool:
    for item in evidence:
        if evidence_type is not None and item.evidence_type is not evidence_type:
            continue
        blob = f"{item.name} {item.source} {item.reason}".lower()
        if any(keyword in blob for keyword in keywords):
            return True
    return False

