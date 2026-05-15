"""Market regime detection primitives."""

from __future__ import annotations

from domain.enums import MarketRegime


def detect_default_regime() -> MarketRegime:
    """Return an unknown regime until detectors are configured."""
    return MarketRegime.SIDEWAY
