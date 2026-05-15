"""Domain enumerations."""

from __future__ import annotations

from enum import Enum


class TradingAction(str, Enum):
    """Allowed recommendation actions."""

    BUY = "BUY"
    SELL = "SELL"
    WAIT = "WAIT"


class MarketRegime(str, Enum):
    """Supported market regimes for strategy selection."""

    UPTREND = "UPTREND"
    DOWNTREND = "DOWNTREND"
    SIDEWAY = "SIDEWAY"
    BREAKOUT_UP = "BREAKOUT_UP"
    BREAKOUT_DOWN = "BREAKOUT_DOWN"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"


class StrategyType(str, Enum):
    """Supported strategy families."""

    TREND_FOLLOWING = "Trend Following"
    BREAKOUT = "Breakout"
    MEAN_REVERSION = "Mean Reversion"
