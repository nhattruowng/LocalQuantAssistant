"""Trading pipeline orchestrator agent."""

from __future__ import annotations

from datetime import UTC, datetime
import logging

from agents.base import AgentError, BaseAgent
from agents.context import AgentContext
from agents.explanation_agent import ExplanationAgent
from agents.feature_engineering_agent import FeatureEngineeringAgent
from agents.market_data_agent import MarketDataAgent
from agents.market_regime_agent import MarketRegimeAgent
from agents.prediction_agent import PredictionAgent
from agents.risk_agent import RiskAgent
from agents.signal_decision_agent import SignalDecisionAgent
from agents.strategy_agent import StrategyAgent
from config.settings import Settings
from domain.entities import OHLCVBar, TradeSetup
from domain.enums import TradingAction


class TradingOrchestratorAgent(BaseAgent):
    """Orchestrates market analysis into a complete trade setup."""

    name = "TradingOrchestratorAgent"

    def __init__(
        self,
        settings: Settings,
        logger: logging.Logger | None = None,
        agents: list[BaseAgent] | None = None,
    ) -> None:
        super().__init__(settings=settings, logger=logger)
        self._agents = agents or [
            MarketDataAgent(settings, self.logger),
            FeatureEngineeringAgent(settings, self.logger),
            MarketRegimeAgent(settings, self.logger),
            PredictionAgent(settings, self.logger),
            StrategyAgent(settings, self.logger),
            RiskAgent(settings, self.logger),
            SignalDecisionAgent(settings, self.logger),
            ExplanationAgent(settings, self.logger),
        ]

    def analyze(
        self,
        symbol: str,
        ohlcv: list[OHLCVBar] | None = None,
    ) -> TradeSetup:
        """Run the full trading setup pipeline."""
        context = AgentContext(symbol=symbol, ohlcv=ohlcv or [])
        context = self.run(context)
        if context.trade_setup is None:
            raise AgentError("Orchestrator completed without a trade setup.")
        return context.trade_setup

    def run(self, context: AgentContext) -> AgentContext:
        """Run data -> feature -> regime -> prediction -> strategy -> risk -> signal -> explanation."""
        self.log_start(context)
        try:
            for agent in self._agents:
                context = agent.run(context)

            context.trade_setup = TradeSetup(
                symbol=context.symbol,
                action=context.action,
                confidence=context.confidence,
                regime=context.regime,
                strategy=context.strategy,
                probabilities=context.probabilities,
                risk_plan=context.risk_plan if context.action is not TradingAction.WAIT else None,
                reasons=context.reasons,
                explanation=context.explanation,
                created_at=datetime.now(UTC),
            )
            self.log_finish(context)
            return context
        except AgentError as error:
            self.logger.error("Pipeline stopped: %s", error)
            context.add_reason(f"Pipeline error: {error}")
            context.action = TradingAction.WAIT
            context.confidence = 0.0
            context.explanation = (
                f"WAIT setup for {context.symbol}. Pipeline stopped safely: {error}"
            )
            context.trade_setup = TradeSetup(
                symbol=context.symbol,
                action=TradingAction.WAIT,
                confidence=0.0,
                regime=context.regime,
                strategy=context.strategy,
                probabilities=context.probabilities,
                risk_plan=None,
                reasons=context.reasons,
                explanation=context.explanation,
                created_at=datetime.now(UTC),
            )
            return context
