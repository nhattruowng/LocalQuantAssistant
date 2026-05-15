"""Market regime detection primitives."""

from __future__ import annotations

from regime.market_regime import MarketRegime


def detect_default_regime() -> MarketRegime:
    """Return an unknown regime until detectors are configured."""
    return MarketRegime.UNKNOWN
