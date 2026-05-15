"""Template-based setup explanation agent."""

from __future__ import annotations

from agents.base import AgentError, BaseAgent
from agents.context import AgentContext


class ExplanationAgent(BaseAgent):
    """Creates a deterministic explanation for the final setup."""

    name = "ExplanationAgent"

    def run(self, context: AgentContext) -> AgentContext:
        """Create a short template-based explanation."""
        self.log_start(context)
        if context.regime is None:
            raise AgentError("Regime is required before explanation.")

        risk_text = "No actionable risk plan."
        if context.risk_plan is not None:
            risk_text = (
                f"Entry {context.risk_plan.entry:.2f}, "
                f"SL {context.risk_plan.stop_loss:.2f}, "
                f"TP {context.risk_plan.take_profit:.2f}, "
                f"R/R {context.risk_plan.risk_reward:.2f}."
            )

        strategy = context.strategy.value if context.strategy else "No strategy"
        context.explanation = (
            f"{context.action.value} setup for {context.symbol}. "
            f"Regime: {context.regime.value}. Strategy: {strategy}. "
            f"Decision confidence: {context.confidence:.2f}. {risk_text} "
            f"Reasons: {' | '.join(context.reasons)}"
        )
        self.log_finish(context)
        return context
