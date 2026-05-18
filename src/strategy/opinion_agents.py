"""Soft strategy opinion agents for adaptive strategy selection."""

from __future__ import annotations

from typing import Mapping

from config.settings import SignalSettings
from regime.market_regime import MarketRegime
from signals.models import (
    SetupGrade,
    SignalContext,
    SignalType,
    StrategyOpinion,
    StrategyType,
)


class StrategyOpinionAgent:
    """Base class for strategy opinion agents."""

    strategy_type = StrategyType.NONE

    def __init__(self, settings: SignalSettings) -> None:
        self.settings = settings

    def evaluate(self, context: SignalContext) -> StrategyOpinion:
        """Return a soft opinion for the current context."""
        raise NotImplementedError

    def _wait(
        self,
        score: float,
        reasons: list[str],
        warnings: list[str] | None = None,
        failed: list[str] | None = None,
    ) -> StrategyOpinion:
        """Return a WAIT opinion."""
        return StrategyOpinion(
            strategy_type=self.strategy_type,
            suggested_signal=SignalType.WAIT,
            score=round(_clip(score), 4),
            confidence=round(_clip(score), 4),
            setup_grade=_grade(score),
            reasons=reasons,
            warnings=warnings or [],
            passed_conditions=[],
            failed_conditions=failed or reasons,
            suggested_size_multiplier=_size_multiplier(score, warnings or []),
        )


class TrendFollowingOpinionAgent(StrategyOpinionAgent):
    """Scores trend-following setups without hard-failing minor defects."""

    strategy_type = StrategyType.TREND_FOLLOWING

    def evaluate(self, context: SignalContext) -> StrategyOpinion:
        """Return a trend-following opinion."""
        regime_scores = context.soft_regime_scores()
        buy_probability = context.probability(SignalType.BUY)
        sell_probability = context.probability(SignalType.SELL)
        signal = SignalType.BUY if buy_probability >= sell_probability else SignalType.SELL
        probability = max(buy_probability, sell_probability)
        regime_fit = _regime_fit(
            regime_scores,
            [MarketRegime.UPTREND.value if signal is SignalType.BUY else MarketRegime.DOWNTREND.value],
            context.regime_value(),
        )
        ema_alignment = _trend_ema_alignment(context, signal)
        rsi_quality = _trend_rsi_quality(context, signal, self.settings)
        ema_distance = _ema_distance_quality(context)
        mtf_alignment = _multi_timeframe_alignment(context, signal)
        volume_quality = _volume_quality(context.feature("volume_ratio", 1.0))
        risk_reward_quality = _risk_reward_quality(context)
        indicator_alignment = _avg([ema_alignment, rsi_quality, ema_distance])
        score = _strategy_score(
            regime_fit,
            probability,
            indicator_alignment,
            mtf_alignment,
            volume_quality,
            risk_reward_quality,
        )
        warnings: list[str] = []
        failed: list[str] = []
        passed: list[str] = []
        if ema_alignment >= 0.6:
            passed.append("EMA alignment supports trend direction.")
        else:
            failed.append("EMA alignment is weak for trend direction.")
        if rsi_quality >= 0.6:
            passed.append("RSI quality supports trend entry.")
        else:
            failed.append("RSI quality is outside ideal trend range.")
        if ema_distance < 0.65:
            warnings.append("Price is slightly extended from EMA20.")
        if mtf_alignment < 0.5:
            warnings.append("Higher timeframe alignment is weak for trend following.")
        if score < 0.35 or (probability < 0.35 and regime_fit < 0.25):
            return self._wait(
                score,
                ["Trend-following setup score is too weak."],
                warnings=warnings,
                failed=failed,
            )
        return StrategyOpinion(
            strategy_type=self.strategy_type,
            suggested_signal=signal,
            score=round(score, 4),
            confidence=round(_clip(probability * 0.7 + score * 0.3), 4),
            setup_grade=_grade(score),
            reasons=[
                f"Trend-following opinion favors {signal.value}.",
                f"Regime fit score is {regime_fit:.2f}.",
            ],
            warnings=warnings,
            passed_conditions=passed,
            failed_conditions=failed,
            suggested_size_multiplier=_size_multiplier(score, warnings),
        )


class BreakoutOpinionAgent(StrategyOpinionAgent):
    """Scores breakout setups and warns on fakeout evidence."""

    strategy_type = StrategyType.BREAKOUT_CONFIRMATION

    def evaluate(self, context: SignalContext) -> StrategyOpinion:
        """Return a breakout opinion."""
        close = context.feature("close")
        rolling_high = context.feature("rolling_high_20", close)
        rolling_low = context.feature("rolling_low_20", close)
        buy_probability = context.probability(SignalType.BUY)
        sell_probability = context.probability(SignalType.SELL)
        broke_high = close > rolling_high
        broke_low = close < rolling_low
        signal = SignalType.BUY if buy_probability >= sell_probability else SignalType.SELL
        if broke_high:
            signal = SignalType.BUY
        elif broke_low:
            signal = SignalType.SELL
        probability = context.probability(signal)
        regime_scores = context.soft_regime_scores()
        regime_fit = _regime_fit(
            regime_scores,
            [
                MarketRegime.BREAKOUT_UP.value if signal is SignalType.BUY else MarketRegime.BREAKOUT_DOWN.value,
            ],
            context.regime_value(),
        )
        breakout_alignment = 1.0 if (signal is SignalType.BUY and broke_high) or (signal is SignalType.SELL and broke_low) else 0.25
        candle_body = _body_strength(context.features)
        mtf_alignment = _multi_timeframe_alignment(context, signal)
        volume_ratio = context.feature("volume_ratio", 1.0)
        volume_quality = _volume_quality(
            volume_ratio,
            threshold=self.settings.breakout_volume_ratio_threshold,
        )
        risk_reward_quality = _risk_reward_quality(context)
        score = _strategy_score(
            regime_fit,
            probability,
            _avg([breakout_alignment, candle_body]),
            mtf_alignment,
            volume_quality,
            risk_reward_quality,
        )
        warnings: list[str] = []
        failed: list[str] = []
        passed: list[str] = []
        rejection = _rejection_wick(context.features, signal)
        atr_percent = context.feature("atr_percent", 0.0)
        if breakout_alignment >= 0.8:
            passed.append("Price broke the relevant rolling level.")
        else:
            failed.append("Price has not clearly broken the relevant rolling level.")
        if volume_ratio > self.settings.breakout_volume_ratio_threshold:
            passed.append("Volume confirms breakout attempt.")
        else:
            warnings.append("Volume does not confirm breakout.")
        if rejection >= 0.45:
            warnings.append("Breakout candle has a large rejection wick.")
        if candle_body < 0.35:
            warnings.append("Breakout candle body is weak.")
        if atr_percent >= 0.05:
            warnings.append("ATR is very high; fakeout risk is elevated.")
        if score < 0.35:
            return self._wait(
                score,
                ["Breakout setup score is too weak."],
                warnings=warnings,
                failed=failed,
            )
        return StrategyOpinion(
            strategy_type=self.strategy_type,
            suggested_signal=signal,
            score=round(score, 4),
            confidence=round(_clip(probability * 0.65 + score * 0.35), 4),
            setup_grade=_grade(score),
            reasons=[
                f"Breakout opinion favors {signal.value}.",
                f"Breakout alignment score is {breakout_alignment:.2f}.",
            ],
            warnings=warnings,
            passed_conditions=passed,
            failed_conditions=failed,
            suggested_size_multiplier=_size_multiplier(score, warnings),
        )


class MeanReversionOpinionAgent(StrategyOpinionAgent):
    """Scores mean-reversion setups and warns on breakout danger."""

    strategy_type = StrategyType.MEAN_REVERSION

    def evaluate(self, context: SignalContext) -> StrategyOpinion:
        """Return a mean-reversion opinion."""
        close = context.feature("close")
        support = context.feature("rolling_low_20", close)
        resistance = context.feature("rolling_high_20", close)
        buy_probability = context.probability(SignalType.BUY)
        sell_probability = context.probability(SignalType.SELL)
        near_support = close <= support * (1.0 + self.settings.support_resistance_near_pct)
        near_resistance = close >= resistance * (1.0 - self.settings.support_resistance_near_pct)
        signal = SignalType.BUY if near_support and buy_probability >= sell_probability else SignalType.SELL
        if near_resistance and sell_probability >= buy_probability:
            signal = SignalType.SELL
        probability = context.probability(signal)
        regime_scores = context.soft_regime_scores()
        regime_fit = _regime_fit(regime_scores, [MarketRegime.SIDEWAY.value], context.regime_value())
        rsi_quality = _mean_reversion_rsi_quality(context, signal, self.settings)
        range_location = 1.0 if (signal is SignalType.BUY and near_support) or (signal is SignalType.SELL and near_resistance) else 0.35
        mtf_alignment = 1.0 - _higher_timeframe_trend_strength(context, signal)
        volume_quality = 1.0 - _clip(context.feature("volume_ratio", 1.0) / 3.0)
        risk_reward_quality = _risk_reward_quality(context)
        indicator_alignment = _avg([rsi_quality, range_location])
        score = _strategy_score(
            regime_fit,
            probability,
            indicator_alignment,
            mtf_alignment,
            volume_quality,
            risk_reward_quality,
        )
        warnings = _mean_reversion_warnings(context, signal, self.settings)
        passed: list[str] = []
        failed: list[str] = []
        if rsi_quality >= 0.6:
            passed.append("RSI supports mean reversion.")
        else:
            failed.append("RSI does not strongly support mean reversion.")
        if range_location >= 0.8:
            passed.append("Price is near range edge.")
        else:
            failed.append("Price is not near support/resistance.")
        if score < 0.35:
            return self._wait(
                score,
                ["Mean-reversion setup score is too weak."],
                warnings=warnings,
                failed=failed,
            )
        return StrategyOpinion(
            strategy_type=self.strategy_type,
            suggested_signal=signal,
            score=round(score, 4),
            confidence=round(_clip(probability * 0.65 + score * 0.35), 4),
            setup_grade=_grade(score),
            reasons=[
                f"Mean-reversion opinion favors {signal.value}.",
                f"Sideway regime fit score is {regime_fit:.2f}.",
            ],
            warnings=warnings,
            passed_conditions=passed,
            failed_conditions=failed,
            suggested_size_multiplier=_size_multiplier(score, warnings),
        )


def opinion_to_dict(opinion: StrategyOpinion) -> dict[str, object]:
    """Serialize an opinion for diagnostics and API payloads."""
    return {
        "strategy_type": opinion.strategy_type.value,
        "suggested_signal": opinion.suggested_signal.value,
        "score": opinion.score,
        "confidence": opinion.confidence,
        "setup_grade": opinion.setup_grade.value,
        "reasons": opinion.reasons,
        "warnings": opinion.warnings,
        "passed_conditions": opinion.passed_conditions,
        "failed_conditions": opinion.failed_conditions,
        "suggested_size_multiplier": opinion.suggested_size_multiplier,
    }


def _strategy_score(
    regime_fit_score: float,
    model_probability: float,
    indicator_alignment: float,
    multi_timeframe_alignment: float,
    volume_quality: float,
    risk_reward_score: float,
) -> float:
    """Calculate the shared soft strategy score."""
    return _clip(
        regime_fit_score * 0.25
        + model_probability * 0.25
        + indicator_alignment * 0.20
        + multi_timeframe_alignment * 0.15
        + volume_quality * 0.10
        + risk_reward_score * 0.05
    )


def _regime_fit(
    scores: Mapping[str, float],
    preferred: list[str],
    hard_regime: str,
) -> float:
    """Return fit against preferred soft or hard regimes."""
    if scores:
        return max(float(scores.get(regime, 0.0)) for regime in preferred)
    return 1.0 if hard_regime in preferred else 0.0


def _trend_ema_alignment(context: SignalContext, signal: SignalType) -> float:
    """Score EMA alignment for directional strategies."""
    close = context.feature("close")
    ema_20 = context.feature("ema_20")
    ema_50 = context.feature("ema_50")
    slope = context.feature("ema_20_slope", 0.0)
    if signal is SignalType.BUY:
        return _avg([1.0 if ema_20 > ema_50 else 0.0, 1.0 if close >= ema_20 else 0.0, 1.0 if slope > 0 else 0.0])
    return _avg([1.0 if ema_20 < ema_50 else 0.0, 1.0 if close <= ema_20 else 0.0, 1.0 if slope < 0 else 0.0])


def _trend_rsi_quality(
    context: SignalContext,
    signal: SignalType,
    settings: SignalSettings,
) -> float:
    """Score RSI quality for trend entries."""
    rsi = context.feature("rsi_14", 50.0)
    if signal is SignalType.BUY:
        return _range_quality(rsi, settings.trend_buy_rsi_min, settings.trend_buy_rsi_max)
    return _range_quality(rsi, settings.trend_sell_rsi_min, settings.trend_sell_rsi_max)


def _mean_reversion_rsi_quality(
    context: SignalContext,
    signal: SignalType,
    settings: SignalSettings,
) -> float:
    """Score RSI quality for mean-reversion entries."""
    rsi = context.feature("rsi_14", 50.0)
    if signal is SignalType.BUY:
        return _clip((settings.mean_reversion_buy_rsi_max - rsi + 10.0) / 10.0)
    return _clip((rsi - settings.mean_reversion_sell_rsi_min + 10.0) / 10.0)


def _range_quality(value: float, lower: float, upper: float) -> float:
    """Return 1 inside range, tapering outside by 20 RSI points."""
    if lower <= value <= upper:
        return 1.0
    if value < lower:
        return _clip(1.0 - (lower - value) / 20.0)
    return _clip(1.0 - (value - upper) / 20.0)


def _ema_distance_quality(context: SignalContext) -> float:
    """Score distance from EMA20, penalizing extended entries softly."""
    close = context.feature("close")
    ema_20 = context.feature("ema_20", close)
    distance = abs(close - ema_20) / max(abs(ema_20), 1e-9)
    return 1.0 - _clip(distance / max(context.explanation_context.get("ema_near_pct", 0.03), 0.03))


def _multi_timeframe_alignment(context: SignalContext, signal: SignalType) -> float:
    """Score directional agreement from higher timeframe regimes."""
    if not context.higher_timeframe_regimes:
        return 0.75
    aligned = 0
    conflicts = 0
    for regime in context.higher_timeframe_regimes.values():
        value = regime.value if hasattr(regime, "value") else str(regime)
        if signal is SignalType.BUY and value in {MarketRegime.UPTREND.value, MarketRegime.BREAKOUT_UP.value}:
            aligned += 1
        elif signal is SignalType.SELL and value in {MarketRegime.DOWNTREND.value, MarketRegime.BREAKOUT_DOWN.value}:
            aligned += 1
        elif signal is SignalType.BUY and value in {MarketRegime.DOWNTREND.value, MarketRegime.BREAKOUT_DOWN.value}:
            conflicts += 1
        elif signal is SignalType.SELL and value in {MarketRegime.UPTREND.value, MarketRegime.BREAKOUT_UP.value}:
            conflicts += 1
    total = max(len(context.higher_timeframe_regimes), 1)
    return _clip(0.75 + aligned / total * 0.25 - conflicts / total * 0.75)


def _higher_timeframe_trend_strength(context: SignalContext, signal: SignalType) -> float:
    """Return how much higher timeframe trend opposes mean reversion."""
    return 1.0 - _multi_timeframe_alignment(context, signal)


def _volume_quality(volume_ratio: float, threshold: float = 1.2) -> float:
    """Score volume confirmation."""
    return _clip(volume_ratio / max(threshold, 1e-9))


def _risk_reward_quality(context: SignalContext) -> float:
    """Read risk/reward quality when available, otherwise return neutral quality."""
    try:
        risk_reward = float(context.explanation_context.get("risk_reward", 2.0))
    except (TypeError, ValueError):
        risk_reward = 2.0
    return _clip(risk_reward / 2.0)


def _mean_reversion_warnings(
    context: SignalContext,
    signal: SignalType,
    settings: SignalSettings,
) -> list[str]:
    """Return warnings that make mean reversion riskier."""
    warnings: list[str] = []
    if context.feature("atr_percent_change", 0.0) > 0.25:
        warnings.append("ATR is expanding quickly; mean reversion has breakout danger.")
    if context.feature("volume_ratio", 1.0) >= settings.breakout_volume_ratio_threshold * 1.2:
        warnings.append("Volume ratio is unusually high for mean reversion.")
    close = context.feature("close")
    high = context.feature("rolling_high_20", close)
    low = context.feature("rolling_low_20", close)
    if _near_level(close, high) > 0.8 or _near_level(close, low) > 0.8:
        warnings.append("Price is closing near range high/low.")
    if _higher_timeframe_trend_strength(context, signal) > 0.5:
        warnings.append("Higher timeframe is trending strongly against mean reversion.")
    return warnings


def _body_strength(features: Mapping[str, object]) -> float:
    """Return candle body share of range."""
    open_price = _float(features.get("open"), 0.0)
    close = _float(features.get("close"), open_price)
    high = _float(features.get("high"), max(open_price, close))
    low = _float(features.get("low"), min(open_price, close))
    return _clip(abs(close - open_price) / max(high - low, 1e-9))


def _rejection_wick(features: Mapping[str, object], signal: SignalType) -> float:
    """Return wick rejection score for breakout direction."""
    open_price = _float(features.get("open"), 0.0)
    close = _float(features.get("close"), open_price)
    high = _float(features.get("high"), max(open_price, close))
    low = _float(features.get("low"), min(open_price, close))
    candle_range = max(high - low, 1e-9)
    if signal is SignalType.BUY:
        return _clip((high - max(open_price, close)) / candle_range)
    return _clip((min(open_price, close) - low) / candle_range)


def _near_level(close: float, level: float) -> float:
    """Return closeness to a support/resistance level."""
    distance = abs(close - level) / max(abs(close), 1e-9)
    return 1.0 - _clip(distance / 0.01)


def _size_multiplier(score: float, warnings: list[str]) -> float:
    """Suggest conservative size when opinion quality is weaker."""
    if score >= 0.8 and not warnings:
        return 1.0
    if score >= 0.65:
        return 0.8 if warnings else 0.9
    if score >= 0.5:
        return 0.6
    return 0.0 if score < 0.35 else 0.4


def _grade(score: float) -> SetupGrade:
    """Convert numeric score into setup grade."""
    if score >= 0.9:
        return SetupGrade.A_PLUS
    if score >= 0.8:
        return SetupGrade.A
    if score >= 0.65:
        return SetupGrade.B
    if score >= 0.5:
        return SetupGrade.C
    return SetupGrade.D


def _float(value: object, default: float) -> float:
    """Parse a float safely."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clip(value: float) -> float:
    """Clamp to 0..1."""
    return max(0.0, min(float(value), 1.0))


def _avg(values: list[float]) -> float:
    """Return bounded average."""
    return _clip(sum(values) / len(values)) if values else 0.0

