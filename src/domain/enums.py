"""Domain enumerations."""

from __future__ import annotations

from enum import Enum

from regime.market_regime import MarketRegime


class TradingAction(str, Enum):
    """Allowed recommendation actions."""

    BUY = "BUY"
    SELL = "SELL"
    WAIT = "WAIT"

class StrategyType(str, Enum):
    """Supported strategy families."""

    TREND_FOLLOWING = "Trend Following"
    BREAKOUT = "Breakout"
    MEAN_REVERSION = "Mean Reversion"
