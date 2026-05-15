"""Market regime detection agent."""

from __future__ import annotations

from agents.base import AgentError, BaseAgent
from agents.context import AgentContext
from domain.enums import MarketRegime


class MarketRegimeAgent(BaseAgent):
    """Classifies current market regime from engineered features."""

    name = "MarketRegimeAgent"

    def run(self, context: AgentContext) -> AgentContext:
        """Determine the market regime."""
        self.log_start(context)
        if not context.features:
            raise AgentError("Features are required before regime detection.")

        close = context.features["close"]
        sma_fast = context.indicators["sma_fast"]
        sma_slow = context.indicators["sma_slow"]
        volatility = context.indicators["volatility"]
        breakout_high = context.indicators["breakout_high"]
        breakout_low = context.indicators["breakout_low"]
        buffer_pct = self.settings.market_regime.breakout_buffer_pct

        if close > breakout_high * (1.0 + buffer_pct):
            context.regime = MarketRegime.BREAKOUT_UP
        elif close < breakout_low * (1.0 - buffer_pct):
            context.regime = MarketRegime.BREAKOUT_DOWN
        elif volatility >= self.settings.market_regime.high_volatility_threshold:
            context.regime = MarketRegime.HIGH_VOLATILITY
        else:
            trend_strength = (sma_fast - sma_slow) / sma_slow
            if trend_strength >= self.settings.market_regime.trend_strength_threshold:
                context.regime = MarketRegime.UPTREND
            elif trend_strength <= -self.settings.market_regime.trend_strength_threshold:
                context.regime = MarketRegime.DOWNTREND
            else:
                context.regime = MarketRegime.SIDEWAY

        context.add_reason(f"Market regime detected: {context.regime.value}.")
        self.log_finish(context)
        return context
