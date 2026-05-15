"""Final signal decision agent."""

from __future__ import annotations

from agents.base import AgentError, BaseAgent
from agents.context import AgentContext
from domain.enums import TradingAction


class SignalDecisionAgent(BaseAgent):
    """Combines prediction, regime, strategy, and risk into BUY/SELL/WAIT."""

    name = "SignalDecisionAgent"

    def run(self, context: AgentContext) -> AgentContext:
        """Decide whether the setup is actionable."""
        self.log_start(context)
        if not context.probabilities:
            raise AgentError("Prediction probabilities are required before signal decision.")

        candidate_action = max(context.probabilities, key=context.probabilities.get)
        confidence = context.probabilities[candidate_action]

        if candidate_action is TradingAction.WAIT:
            context.action = TradingAction.WAIT
            context.confidence = confidence
            context.add_reason("WAIT selected because it has the highest probability.")
        elif confidence < self.settings.signal.min_confidence:
            context.action = TradingAction.WAIT
            context.confidence = confidence
            context.add_reason("Action blocked because model confidence is below threshold.")
        elif context.risk_plan is None:
            context.action = TradingAction.WAIT
            context.confidence = confidence
            context.add_reason("Action blocked because no risk plan is available.")
        elif context.risk_plan.risk_reward < self.settings.signal.min_risk_reward:
            context.action = TradingAction.WAIT
            context.confidence = confidence
            context.add_reason("Action blocked because risk/reward is below threshold.")
        else:
            context.action = candidate_action
            context.confidence = confidence
            context.add_reason(f"Final action approved: {context.action.value}.")

        self.log_finish(context)
        return context
