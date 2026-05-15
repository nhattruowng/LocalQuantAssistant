"""Risk calculation agent."""

from __future__ import annotations

from agents.base import AgentError, BaseAgent
from agents.context import AgentContext
from domain.entities import RiskPlan
from domain.enums import TradingAction


class RiskAgent(BaseAgent):
    """Calculates entry, stop loss, take profit, and position size."""

    name = "RiskAgent"

    def run(self, context: AgentContext) -> AgentContext:
        """Build a risk plan for the strongest actionable prediction."""
        self.log_start(context)
        if not context.probabilities:
            raise AgentError("Prediction probabilities are required before risk calculation.")

        candidate_action = self._candidate_action(context)
        if candidate_action is TradingAction.WAIT:
            context.risk_plan = None
            context.add_reason("Risk plan skipped because WAIT has the highest probability.")
            self.log_finish(context)
            return context

        entry = context.features["close"]
        stop_pct = self.settings.risk.stop_loss_pct
        take_pct = self.settings.risk.take_profit_pct
        risk_amount = (
            self.settings.risk.account_balance * self.settings.risk.risk_per_trade_pct
        )

        if candidate_action is TradingAction.BUY:
            stop_loss = entry * (1.0 - stop_pct)
            take_profit = entry * (1.0 + take_pct)
        else:
            stop_loss = entry * (1.0 + stop_pct)
            take_profit = entry * (1.0 - take_pct)

        per_unit_risk = abs(entry - stop_loss)
        per_unit_reward = abs(take_profit - entry)
        if per_unit_risk <= 0:
            raise AgentError("Stop loss produces zero per-unit risk.")

        context.risk_plan = RiskPlan(
            action=candidate_action,
            entry=entry,
            stop_loss=stop_loss,
            take_profit=take_profit,
            risk_reward=per_unit_reward / per_unit_risk,
            position_size=risk_amount / per_unit_risk,
        )
        context.add_reason(
            f"Risk plan built with R/R={context.risk_plan.risk_reward:.2f}."
        )
        self.log_finish(context)
        return context

    def _candidate_action(self, context: AgentContext) -> TradingAction:
        """Return the highest-probability action."""
        return max(context.probabilities, key=context.probabilities.get)
