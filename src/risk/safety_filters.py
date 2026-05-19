"""Safety filters for fragile strategy setups."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from config.settings import SafetyFilterSettings
from regime.market_regime import MarketRegime
from signals.models import SignalContext, SignalType, StrategyDecision, StrategyType


@dataclass(frozen=True)
class SafetyFilterDecision:
    """Safety filter verdict attached to a signal decision."""

    blocked: bool
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    filters: list[dict[str, object]] = field(default_factory=list)
    mean_reversion_danger_score: float | None = None
    breakout_fakeout_score: float | None = None


class SafetyFilterEngine:
    """Evaluates risk-aware strategy filters before position sizing."""

    def __init__(self, settings: SafetyFilterSettings) -> None:
        self._settings = settings

    def evaluate(
        self,
        context: SignalContext,
        decision: StrategyDecision,
    ) -> SafetyFilterDecision:
        """Return blocking and warning filters for a candidate setup."""
        reasons: list[str] = []
        warnings: list[str] = []
        filters: list[dict[str, object]] = []
        blocked = False

        volatility_level = str((context.primary_features or context.features).get("volatility_level", "NORMAL"))
        if self._settings.extreme_volatility_block and volatility_level == "EXTREME":
            blocked = True
            reasons.append("Blocked by safety filter: volatility is EXTREME.")
            filters.append(_filter("extreme_volatility", 1.0, True, "Volatility level is EXTREME."))

        if self._settings.higher_timeframe_conflict_block and bool(
            context.explanation_context.get("multi_timeframe_enabled", False)
        ):
            conflict_score = _higher_timeframe_conflict_score(context, decision.signal)
            if conflict_score >= 0.75:
                blocked = True
                reasons.append("Blocked by safety filter: strong higher timeframe conflict.")
            if conflict_score > 0:
                filters.append(
                    _filter(
                        "higher_timeframe_conflict",
                        conflict_score,
                        conflict_score >= 0.75,
                        "Higher timeframe opposes the primary signal.",
                    )
                )

        mean_reversion_danger: float | None = None
        if (
            self._settings.mean_reversion_danger_enabled
            and decision.strategy is StrategyType.MEAN_REVERSION
        ):
            mean_reversion_danger = _mean_reversion_danger_score(context, decision.signal)
            is_blocked = mean_reversion_danger >= self._settings.mean_reversion_danger_threshold
            filters.append(
                _filter(
                    "mean_reversion_danger",
                    mean_reversion_danger,
                    is_blocked,
                    "Mean reversion setup shows breakout transition danger.",
                )
            )
            if is_blocked:
                blocked = True
                reasons.append("Blocked by safety filter: mean reversion breakout danger is high.")
            elif mean_reversion_danger >= 0.5:
                warnings.append("Mean reversion danger is elevated; reduce conviction.")

        breakout_fakeout: float | None = None
        if (
            self._settings.breakout_fakeout_defense_enabled
            and decision.strategy is StrategyType.BREAKOUT_CONFIRMATION
        ):
            breakout_fakeout = _breakout_fakeout_score(context, decision.signal)
            is_blocked = breakout_fakeout >= self._settings.breakout_fakeout_threshold
            filters.append(
                _filter(
                    "breakout_fakeout_defense",
                    breakout_fakeout,
                    is_blocked,
                    "Breakout setup has fakeout risk from weak body, poor close, or rejection wick.",
                )
            )
            if is_blocked:
                blocked = True
                reasons.append("Blocked by safety filter: breakout fakeout risk is high.")
            elif breakout_fakeout >= 0.35:
                warnings.append("Breakout fakeout risk is elevated.")

        return SafetyFilterDecision(
            blocked=blocked,
            reasons=reasons,
            warnings=warnings,
            filters=filters,
            mean_reversion_danger_score=mean_reversion_danger,
            breakout_fakeout_score=breakout_fakeout,
        )


def _mean_reversion_danger_score(context: SignalContext, signal: SignalType) -> float:
    """Score danger that a sideway mean-reversion setup is becoming breakout."""
    features = context.primary_features or context.features
    atr_expansion = _clip(_feature_float(features, "atr_percent_change", 0.0) / 0.35)
    volume_danger = _clip((_feature_float(features, "volume_ratio", 1.0) - 1.0) / 1.5)
    breakout_score = _clip(_feature_float(features, "breakout_score", 0.0))
    close_edge = max(
        _near_level_score(features, "rolling_high_20"),
        _near_level_score(features, "rolling_low_20"),
    )
    htf_trend = _higher_timeframe_conflict_score(context, signal)
    range_tests = _clip(_feature_float(features, "range_test_count", 0.0) / 5.0)
    return round(
        _clip(
            atr_expansion * 0.20
            + volume_danger * 0.20
            + close_edge * 0.15
            + breakout_score * 0.20
            + htf_trend * 0.15
            + range_tests * 0.10
        ),
        4,
    )


def _breakout_fakeout_score(context: SignalContext, signal: SignalType) -> float:
    """Score fakeout risk for a breakout setup."""
    features = context.primary_features or context.features
    has_ohlc = all(key in features for key in ("open", "high", "low", "close"))
    body_strength = _feature_float(
        features,
        "candle_body_strength",
        _body_strength(features) if has_ohlc else 0.75,
    )
    close_location = _feature_float(
        features,
        "close_location_score",
        _close_location_score(features, signal) if has_ohlc else 0.75,
    )
    volume_expansion = _clip(_feature_float(features, "volume_ratio", 1.0) / 2.0)
    atr_expansion = _clip(_feature_float(features, "atr_expansion_score", _feature_float(features, "atr_percent_change", 0.0) / 0.3))
    rejection = _feature_float(
        features,
        "rejection_wick_penalty",
        _rejection_wick(features, signal) if has_ohlc else 0.0,
    )
    htf_alignment = 1.0 - _higher_timeframe_conflict_score(context, signal)
    retest = _feature_float(features, "retest_confirmation", 0.5)
    quality = _clip(
        body_strength * 0.20
        + close_location * 0.20
        + volume_expansion * 0.20
        + atr_expansion * 0.10
        + htf_alignment * 0.20
        + retest * 0.10
        - rejection * 0.25
    )
    return round(_clip(1.0 - quality + rejection * 0.35), 4)


def _higher_timeframe_conflict_score(context: SignalContext, signal: SignalType) -> float:
    """Return share of strong higher timeframe regimes opposing the signal."""
    if not context.higher_timeframe_regimes:
        return 0.0
    conflicts = 0
    total = 0
    for timeframe, regime in context.higher_timeframe_regimes.items():
        value = regime.value if hasattr(regime, "value") else str(regime)
        payload = context.higher_timeframe_features.get(timeframe, {})
        strength = max(
            _feature_float(payload, "regime_confidence", 0.75),
            max(_regime_scores(payload).values(), default=0.0),
        )
        if strength < 0.65:
            continue
        total += 1
        if signal is SignalType.BUY and value in {MarketRegime.DOWNTREND.value, MarketRegime.BREAKOUT_DOWN.value}:
            conflicts += 1
        if signal is SignalType.SELL and value in {MarketRegime.UPTREND.value, MarketRegime.BREAKOUT_UP.value}:
            conflicts += 1
    return round(conflicts / total, 4) if total else 0.0


def _near_level_score(features: Mapping[str, object], key: str) -> float:
    close = _feature_float(features, "close", 0.0)
    level = _feature_float(features, key, close)
    if close <= 0:
        return 0.0
    return _clip(1.0 - abs(close - level) / max(abs(close) * 0.01, 1e-9))


def _body_strength(features: Mapping[str, object]) -> float:
    open_price = _feature_float(features, "open", _feature_float(features, "close", 0.0))
    close = _feature_float(features, "close", open_price)
    high = _feature_float(features, "high", max(open_price, close))
    low = _feature_float(features, "low", min(open_price, close))
    return _clip(abs(close - open_price) / max(high - low, 1e-9))


def _close_location_score(features: Mapping[str, object], signal: SignalType) -> float:
    close = _feature_float(features, "close", 0.0)
    high = _feature_float(features, "high", close)
    low = _feature_float(features, "low", close)
    candle_range = max(high - low, 1e-9)
    if signal is SignalType.BUY:
        return _clip((close - low) / candle_range)
    return _clip((high - close) / candle_range)


def _rejection_wick(features: Mapping[str, object], signal: SignalType) -> float:
    open_price = _feature_float(features, "open", 0.0)
    close = _feature_float(features, "close", open_price)
    high = _feature_float(features, "high", max(open_price, close))
    low = _feature_float(features, "low", min(open_price, close))
    candle_range = max(high - low, 1e-9)
    if signal is SignalType.BUY:
        return _clip((high - max(open_price, close)) / candle_range)
    return _clip((min(open_price, close) - low) / candle_range)


def _regime_scores(payload: Mapping[str, object]) -> dict[str, float]:
    raw = payload.get("regime_scores")
    if isinstance(raw, dict):
        return {str(key): _clip(float(value)) for key, value in raw.items()}
    return {}


def _filter(name: str, score: float, blocked: bool, reason: str) -> dict[str, object]:
    return {
        "name": name,
        "score": round(score, 4),
        "blocked": blocked,
        "reason": reason,
    }


def _feature_float(payload: Mapping[str, object], key: str, default: float) -> float:
    try:
        return float(payload.get(key, default))
    except (TypeError, ValueError):
        return default


def _clip(value: float) -> float:
    return max(0.0, min(float(value), 1.0))
