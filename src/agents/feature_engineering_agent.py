"""Feature engineering agent."""

from __future__ import annotations

import math
from statistics import fmean, pstdev

from agents.base import AgentError, BaseAgent
from agents.context import AgentContext


class FeatureEngineeringAgent(BaseAgent):
    """Builds technical indicators and price action features."""

    name = "FeatureEngineeringAgent"

    def run(self, context: AgentContext) -> AgentContext:
        """Create indicators and validate the generated feature vector."""
        self.log_start(context)
        closes = [bar.close for bar in context.ohlcv]
        highs = [bar.high for bar in context.ohlcv]
        lows = [bar.low for bar in context.ohlcv]
        volumes = [bar.volume for bar in context.ohlcv]

        fast_window = self.settings.features.fast_ma_window
        slow_window = self.settings.features.slow_ma_window
        volatility_window = self.settings.features.volatility_window
        breakout_lookback = self.settings.features.breakout_lookback

        if len(closes) < max(fast_window, slow_window, volatility_window, breakout_lookback):
            raise AgentError("Not enough bars to build configured features.")

        returns = [
            (current - previous) / previous
            for previous, current in zip(closes[-volatility_window - 1 : -1], closes[-volatility_window:])
            if previous > 0
        ]
        volatility = pstdev(returns) if len(returns) > 1 else 0.0
        last_close = closes[-1]
        previous_close = closes[-2]

        context.indicators = {
            "sma_fast": fmean(closes[-fast_window:]),
            "sma_slow": fmean(closes[-slow_window:]),
            "volatility": volatility,
            "last_return": (last_close - previous_close) / previous_close,
            "range_pct": (highs[-1] - lows[-1]) / last_close,
            "breakout_high": max(highs[-breakout_lookback - 1 : -1]),
            "breakout_low": min(lows[-breakout_lookback - 1 : -1]),
        }
        context.features = {
            **context.indicators,
            "close": last_close,
            "volume": volumes[-1],
        }

        self._validate_features(context.features)
        context.add_reason("Technical indicators and price action features were generated.")
        self.log_finish(context)
        return context

    def _validate_features(self, features: dict[str, float]) -> None:
        """Reject NaN or infinite feature values."""
        invalid_keys = [
            key for key, value in features.items() if not math.isfinite(value)
        ]
        if invalid_keys:
            raise AgentError(f"Feature vector contains invalid values: {invalid_keys}.")
