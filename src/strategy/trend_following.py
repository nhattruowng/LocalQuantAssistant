"""Trend following strategy rules."""

from __future__ import annotations

from regime.market_regime import MarketRegime
from signals.models import SignalContext, SignalType, StrategyDecision, StrategyType
from strategy.base import Strategy


class TrendFollowingStrategy(Strategy):
    """Evaluates trend-following BUY/SELL setups."""

    strategy_type = StrategyType.TREND_FOLLOWING

    def evaluate(self, context: SignalContext) -> StrategyDecision:
        """Evaluate trend-following rules."""
        regime = context.regime_value()
        if regime == MarketRegime.UPTREND.value:
            return self._buy(context)
        if regime == MarketRegime.DOWNTREND.value:
            return self._sell(context)
        return self.wait("Trend following skipped because regime is not directional.")

    def _buy(self, context: SignalContext) -> StrategyDecision:
        """Evaluate trend-following BUY."""
        probability = context.probability(SignalType.BUY)
        close = context.feature("close")
        ema_20 = context.feature("ema_20")
        ema_50 = context.feature("ema_50")
        rsi = context.feature("rsi_14")
        near_or_above_ema20 = close >= ema_20 * (1.0 - self.settings.ema_near_pct)
        reasons: list[str] = []
        if probability < self.settings.trend_probability_threshold:
            return self.wait("BUY probability is below trend threshold.")
        if not (ema_20 > ema_50 and near_or_above_ema20):
            return self.wait("Trend BUY EMA conditions are not satisfied.")
        if not (self.settings.trend_buy_rsi_min <= rsi <= self.settings.trend_buy_rsi_max):
            return self.wait("Trend BUY RSI is outside the configured range.")
        reasons.extend(
            [
                "Regime is UPTREND.",
                "Model BUY probability passed threshold.",
                "EMA20 is above EMA50 and close is near/above EMA20.",
                "RSI is in trend BUY range.",
            ]
        )
        return StrategyDecision(
            signal=SignalType.BUY,
            strategy=self.strategy_type,
            model_probability=probability,
            trend_score=1.0,
            indicator_score=1.0,
            volume_score=_volume_score(context.feature("volume_ratio")),
            reasons=reasons,
        )

    def _sell(self, context: SignalContext) -> StrategyDecision:
        """Evaluate trend-following SELL."""
        probability = context.probability(SignalType.SELL)
        close = context.feature("close")
        ema_20 = context.feature("ema_20")
        ema_50 = context.feature("ema_50")
        rsi = context.feature("rsi_14")
        near_or_below_ema20 = close <= ema_20 * (1.0 + self.settings.ema_near_pct)
        if probability < self.settings.trend_probability_threshold:
            return self.wait("SELL probability is below trend threshold.")
        if not (ema_20 < ema_50 and near_or_below_ema20):
            return self.wait("Trend SELL EMA conditions are not satisfied.")
        if not (self.settings.trend_sell_rsi_min <= rsi <= self.settings.trend_sell_rsi_max):
            return self.wait("Trend SELL RSI is outside the configured range.")
        return StrategyDecision(
            signal=SignalType.SELL,
            strategy=self.strategy_type,
            model_probability=probability,
            trend_score=1.0,
            indicator_score=1.0,
            volume_score=_volume_score(context.feature("volume_ratio")),
            reasons=[
                "Regime is DOWNTREND.",
                "Model SELL probability passed threshold.",
                "EMA20 is below EMA50 and close is near/below EMA20.",
                "RSI is in trend SELL range.",
            ],
        )


def _volume_score(volume_ratio: float) -> float:
    """Convert volume ratio into a bounded score."""
    return max(0.0, min(volume_ratio / 1.5, 1.0))
