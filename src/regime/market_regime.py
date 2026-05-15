"""Market regime enum used by strategy and signal filters."""

from __future__ import annotations

from enum import Enum


class MarketRegime(str, Enum):
    """Supported market regimes for filtering model signals."""

    UPTREND = "UPTREND"
    DOWNTREND = "DOWNTREND"
    SIDEWAY = "SIDEWAY"
    BREAKOUT_UP = "BREAKOUT_UP"
    BREAKOUT_DOWN = "BREAKOUT_DOWN"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    LOW_VOLATILITY = "LOW_VOLATILITY"
    UNKNOWN = "UNKNOWN"
