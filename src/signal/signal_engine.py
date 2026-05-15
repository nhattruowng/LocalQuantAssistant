"""Signal engine that converts model probabilities into trade setups."""

from __future__ import annotations

import logging
from typing import Mapping

from config.settings import Settings
from regime.market_regime import MarketRegime
from risk.risk_manager import RiskManager
from signal.models import (
    RiskPlan,
    SignalContext,
    SignalType,
    StrategyDecision,
    StrategyType,
    TradeSetup,
)
from strategy.base import Strategy
from strategy.breakout import BreakoutStrategy
from strategy.mean_reversion import MeanReversionStrategy
from strategy.trend_following import TrendFollowingStrategy


class SignalEngine:
    """Builds conservative BUY/SELL/WAIT setups from model and market context."""

    def __init__(
        self,
        settings: Settings,
        risk_manager: RiskManager | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._settings = settings
        self._risk_manager = risk_manager or RiskManager(settings.risk)
        self._logger = logger or logging.getLogger("localquant.signal")
        self._strategies: dict[str, Strategy] = {
            MarketRegime.UPTREND.value: TrendFollowingStrategy(settings.signal),
            MarketRegime.DOWNTREND.value: TrendFollowingStrategy(settings.signal),
            MarketRegime.BREAKOUT_UP.value: BreakoutStrategy(settings.signal),
            MarketRegime.BREAKOUT_DOWN.value: BreakoutStrategy(settings.signal),
            MarketRegime.SIDEWAY.value: MeanReversionStrategy(settings.signal),
        }

    def generate(
        self,
        symbol: str,
        timeframe: str,
        timestamp,
        market_regime: MarketRegime | str,
        features: Mapping[str, float],
        probabilities: Mapping[str | SignalType, float],
    ) -> TradeSetup:
        """Generate a complete trade setup recommendation."""
        context = SignalContext(
            symbol=symbol,
            timeframe=timeframe,
            timestamp=timestamp,
            market_regime=market_regime,
            features=features,
            probabilities=probabilities,
        )
        strategy = self._strategy_for(context)
        if strategy is None:
            return self._wait(context, [f"No strategy for regime {context.regime_value()}."])

        decision = strategy.evaluate(context)
        if decision.signal is SignalType.WAIT:
            return self._wait(context, decision.reasons, decision.strategy)

        risk_plan = self._risk_plan_for(context, decision, features)
        if isinstance(risk_plan, TradeSetup):
            return risk_plan
        if not self._is_risk_acceptable(risk_plan):
            return self._wait(
                context,
                [
                    *decision.reasons,
                    (
                        f"Risk/reward {risk_plan.risk_reward:.2f} is below "
                        f"{self._settings.signal.min_risk_reward:.2f}."
                    ),
                ],
                decision.strategy,
                risk_plan,
            )

        return self._approved_setup(context, decision, risk_plan)

    def _strategy_for(self, context: SignalContext) -> Strategy | None:
        """Return the strategy for the current market regime."""
        return self._strategies.get(context.regime_value())

    def _risk_plan_for(
        self,
        context: SignalContext,
        decision: StrategyDecision,
        features: Mapping[str, float],
    ) -> RiskPlan | TradeSetup:
        """Build a risk plan or a WAIT setup when risk planning fails."""
        try:
            risk_plan = self._risk_manager.build_plan(decision.signal, features)
        except (KeyError, ValueError) as error:
            return self._wait(
                context,
                [*decision.reasons, f"Risk plan failed: {error}."],
                decision.strategy,
            )

        if risk_plan is None:
            return self._wait(context, [*decision.reasons, "No risk plan was built."], decision.strategy)
        return risk_plan

    def _is_risk_acceptable(self, risk_plan: RiskPlan) -> bool:
        """Return True when risk/reward passes the configured gate."""
        return risk_plan.risk_reward >= self._settings.signal.min_risk_reward

    def _approved_setup(
        self,
        context: SignalContext,
        decision: StrategyDecision,
        risk_plan: RiskPlan,
    ) -> TradeSetup:
        """Create an actionable setup after strategy and risk checks pass."""
        confidence = self._score(decision, risk_plan)
        self._logger.info(
            "Signal generated: symbol=%s timeframe=%s signal=%s strategy=%s confidence=%.4f",
            context.symbol,
            context.timeframe,
            decision.signal.value,
            decision.strategy.value,
            confidence,
        )
        return TradeSetup(
            symbol=context.symbol,
            timeframe=context.timeframe,
            timestamp=context.timestamp,
            market_regime=context.regime_value(),
            signal=decision.signal,
            strategy=decision.strategy,
            confidence=confidence,
            entry=risk_plan.entry,
            stop_loss=risk_plan.stop_loss,
            take_profit_1=risk_plan.take_profit_1,
            take_profit_2=risk_plan.take_profit_2,
            risk_reward=risk_plan.risk_reward,
            position_size=risk_plan.position_size,
            reasons=decision.reasons,
            risk_notes=risk_plan.risk_notes,
        )

    def _score(self, decision: StrategyDecision, risk_plan: RiskPlan) -> float:
        """Calculate weighted confidence score."""
        rr_score = max(0.0, min(risk_plan.risk_reward / self._settings.signal.min_risk_reward, 1.0))
        score = (
            decision.model_probability * self._settings.signal.model_score_weight
            + decision.trend_score * self._settings.signal.trend_score_weight
            + decision.indicator_score * self._settings.signal.indicator_score_weight
            + decision.volume_score * self._settings.signal.volume_score_weight
            + rr_score * self._settings.signal.risk_reward_score_weight
        )
        return round(max(0.0, min(score, 1.0)), 4)

    def _wait(
        self,
        context: SignalContext,
        reasons: list[str],
        strategy: StrategyType = StrategyType.NONE,
        risk_plan: RiskPlan | None = None,
    ) -> TradeSetup:
        """Return a non-actionable WAIT setup."""
        return TradeSetup(
            symbol=context.symbol,
            timeframe=context.timeframe,
            timestamp=context.timestamp,
            market_regime=context.regime_value(),
            signal=SignalType.WAIT,
            strategy=strategy,
            confidence=context.probability(SignalType.WAIT),
            entry=risk_plan.entry if risk_plan else None,
            stop_loss=risk_plan.stop_loss if risk_plan else None,
            take_profit_1=risk_plan.take_profit_1 if risk_plan else None,
            take_profit_2=risk_plan.take_profit_2 if risk_plan else None,
            risk_reward=risk_plan.risk_reward if risk_plan else None,
            position_size=risk_plan.position_size if risk_plan else None,
            reasons=reasons,
            risk_notes=risk_plan.risk_notes if risk_plan else [],
        )
