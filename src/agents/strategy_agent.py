"""Strategy selection agent."""

from __future__ import annotations

from agents.base import AgentError, BaseAgent
from agents.context import AgentContext
from domain.enums import MarketRegime, StrategyType


class StrategyAgent(BaseAgent):
    """Selects the strategy family for the detected market regime."""

    name = "StrategyAgent"

    def run(self, context: AgentContext) -> AgentContext:
        """Choose a strategy from market regime."""
        self.log_start(context)
        if context.regime is None:
            raise AgentError("Market regime is required before strategy selection.")

        if context.regime in {MarketRegime.UPTREND, MarketRegime.DOWNTREND}:
            context.strategy = StrategyType.TREND_FOLLOWING
        elif context.regime in {MarketRegime.BREAKOUT_UP, MarketRegime.BREAKOUT_DOWN}:
            context.strategy = StrategyType.BREAKOUT
        else:
            context.strategy = StrategyType.MEAN_REVERSION

        context.add_reason(f"Selected strategy: {context.strategy.value}.")
        self.log_finish(context)
        return context
