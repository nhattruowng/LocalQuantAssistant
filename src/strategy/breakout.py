"""Breakout confirmation strategy rules."""

from __future__ import annotations

from regime.market_regime import MarketRegime
from signal.models import SignalContext, SignalType, StrategyDecision, StrategyType
from strategy.base import Strategy


class BreakoutStrategy(Strategy):
    """Evaluates breakout confirmation setups."""

    strategy_type = StrategyType.BREAKOUT_CONFIRMATION

    def evaluate(self, context: SignalContext) -> StrategyDecision:
        """Evaluate breakout rules."""
        regime = context.regime_value()
        if regime == MarketRegime.BREAKOUT_UP.value:
            return self._buy(context)
        if regime == MarketRegime.BREAKOUT_DOWN.value:
            return self._sell(context)
        return self.wait("Breakout skipped because regime is not breakout.")

    def _buy(self, context: SignalContext) -> StrategyDecision:
        """Evaluate breakout BUY."""
        probability = context.probability(SignalType.BUY)
        close = context.feature("close")
        rolling_high = context.feature("rolling_high_20")
        volume_ratio = context.feature("volume_ratio")
        if probability < self.settings.breakout_probability_threshold:
            return self.wait("BUY probability is below breakout threshold.")
        if volume_ratio <= self.settings.breakout_volume_ratio_threshold:
            return self.wait("Breakout BUY volume confirmation failed.")
        if close <= rolling_high:
            return self.wait("Close has not broken rolling resistance.")
        return StrategyDecision(
            signal=SignalType.BUY,
            strategy=self.strategy_type,
            model_probability=probability,
            trend_score=max(0.0, min(context.feature("trend_score"), 1.0)),
            indicator_score=1.0,
            volume_score=max(0.0, min(volume_ratio / 2.0, 1.0)),
            reasons=[
                "Regime is BREAKOUT_UP.",
                "Model BUY probability passed threshold.",
                "Volume ratio confirmed breakout.",
                "Close broke rolling_high_20.",
            ],
        )

    def _sell(self, context: SignalContext) -> StrategyDecision:
        """Evaluate breakout SELL."""
        probability = context.probability(SignalType.SELL)
        close = context.feature("close")
        rolling_low = context.feature("rolling_low_20")
        volume_ratio = context.feature("volume_ratio")
        if probability < self.settings.breakout_probability_threshold:
            return self.wait("SELL probability is below breakout threshold.")
        if volume_ratio <= self.settings.breakout_volume_ratio_threshold:
            return self.wait("Breakout SELL volume confirmation failed.")
        if close >= rolling_low:
            return self.wait("Close has not broken rolling support.")
        return StrategyDecision(
            signal=SignalType.SELL,
            strategy=self.strategy_type,
            model_probability=probability,
            trend_score=max(0.0, min(abs(context.feature("trend_score")), 1.0)),
            indicator_score=1.0,
            volume_score=max(0.0, min(volume_ratio / 2.0, 1.0)),
            reasons=[
                "Regime is BREAKOUT_DOWN.",
                "Model SELL probability passed threshold.",
                "Volume ratio confirmed breakout.",
                "Close broke rolling_low_20.",
            ],
        )
