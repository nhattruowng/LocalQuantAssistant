"""Mean reversion strategy rules for sideway markets."""

from __future__ import annotations

from regime.market_regime import MarketRegime
from signal.models import SignalContext, SignalType, StrategyDecision, StrategyType
from strategy.base import Strategy


class MeanReversionStrategy(Strategy):
    """Evaluates sideway-market mean reversion setups."""

    strategy_type = StrategyType.MEAN_REVERSION

    def evaluate(self, context: SignalContext) -> StrategyDecision:
        """Evaluate mean reversion rules."""
        if context.regime_value() != MarketRegime.SIDEWAY.value:
            return self.wait("Mean reversion skipped because regime is not SIDEWAY.")

        buy = self._buy(context)
        sell = self._sell(context)
        if buy.signal is SignalType.BUY:
            return buy
        if sell.signal is SignalType.SELL:
            return sell
        return self.wait("No mean reversion rule matched.")

    def _buy(self, context: SignalContext) -> StrategyDecision:
        """Evaluate mean reversion BUY near support."""
        probability = context.probability(SignalType.BUY)
        close = context.feature("close")
        support = context.feature("rolling_low_20")
        rsi = context.feature("rsi_14")
        near_support = close <= support * (1.0 + self.settings.support_resistance_near_pct)
        if probability < self.settings.mean_reversion_probability_threshold:
            return self.wait("BUY probability is below mean reversion threshold.")
        if not (rsi < self.settings.mean_reversion_buy_rsi_max and near_support):
            return self.wait("Mean reversion BUY requires RSI oversold near support.")
        return StrategyDecision(
            signal=SignalType.BUY,
            strategy=self.strategy_type,
            model_probability=probability,
            trend_score=0.5,
            indicator_score=1.0,
            volume_score=max(0.0, min(context.feature("volume_ratio") / 1.2, 1.0)),
            reasons=[
                "Regime is SIDEWAY.",
                "Model BUY probability passed mean reversion threshold.",
                "RSI is oversold.",
                "Close is near rolling support.",
            ],
        )

    def _sell(self, context: SignalContext) -> StrategyDecision:
        """Evaluate mean reversion SELL near resistance."""
        probability = context.probability(SignalType.SELL)
        close = context.feature("close")
        resistance = context.feature("rolling_high_20")
        rsi = context.feature("rsi_14")
        near_resistance = close >= resistance * (1.0 - self.settings.support_resistance_near_pct)
        if probability < self.settings.mean_reversion_probability_threshold:
            return self.wait("SELL probability is below mean reversion threshold.")
        if not (rsi > self.settings.mean_reversion_sell_rsi_min and near_resistance):
            return self.wait("Mean reversion SELL requires RSI overbought near resistance.")
        return StrategyDecision(
            signal=SignalType.SELL,
            strategy=self.strategy_type,
            model_probability=probability,
            trend_score=0.5,
            indicator_score=1.0,
            volume_score=max(0.0, min(context.feature("volume_ratio") / 1.2, 1.0)),
            reasons=[
                "Regime is SIDEWAY.",
                "Model SELL probability passed mean reversion threshold.",
                "RSI is overbought.",
                "Close is near rolling resistance.",
            ],
        )
