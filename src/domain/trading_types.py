"""Shared string enums for trading reasoning and signal payloads."""

from __future__ import annotations

from enum import Enum


class SignalDirection(str, Enum):
    """Directional signal values that serialize cleanly to API strings."""

    BUY = "BUY"
    SELL = "SELL"
    WAIT = "WAIT"
    NEUTRAL = "NEUTRAL"


class EvidenceType(str, Enum):
    """How one evidence item contributes to a reasoning decision."""

    SUPPORT = "SUPPORT"
    AGAINST = "AGAINST"
    WARNING = "WARNING"


class SetupType(str, Enum):
    """High-level setup taxonomy for reasoning, dashboards, and analytics."""

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


class ConflictLevel(str, Enum):
    """Severity buckets for evidence conflicts."""

    NONE = "NONE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class RecommendedAction(str, Enum):
    """Recommended risk action after reasoning conflict analysis."""

    CONTINUE = "CONTINUE"
    REDUCE_SIZE = "REDUCE_SIZE"
    WAIT = "WAIT"
