"""Soft market context engine for regime scoring and transition warnings."""

from __future__ import annotations

from typing import Mapping

import numpy as np
import pandas as pd

from config.settings import MarketRegimeSettings
from regime.market_regime import (
    MarketContext,
    MarketRegime,
    MarketTransitionWarning,
    RegimeContext,
    VolatilityLevel,
)


class MarketContextEngine:
    """Scores multiple market regimes instead of forcing one hard label."""

    def __init__(self, settings: MarketRegimeSettings) -> None:
        self._settings = settings

    def evaluate(self, row: pd.Series | Mapping[str, object]) -> MarketContext:
        """Build a soft market context for one feature row."""
        payload = row if isinstance(row, Mapping) else row.to_dict()
        if not _has_required(payload):
            warning = MarketTransitionWarning(
                warning_type="MISSING_INDICATORS",
                message="Missing required indicator values; regime falls back to UNKNOWN.",
                severity=1.0,
            )
            context = RegimeContext(
                primary_regime=MarketRegime.UNKNOWN,
                regime_scores={MarketRegime.UNKNOWN.value: 1.0},
                confidence=0.0,
                uncertainty_score=1.0,
                transition_warning=True,
                volatility_level=VolatilityLevel.NORMAL,
                reasons=[warning.message],
                warnings=[warning],
            )
            return MarketContext(
                regime=context,
                transition_warnings=[warning],
                features_used=[],
            )

        scores = self._score_regimes(payload)
        warnings = self._transition_warnings(payload, scores)
        if warnings:
            scores = self._apply_warning_penalties(scores, warnings)
        ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        primary, confidence = ordered[0]
        second = ordered[1][1] if len(ordered) > 1 else 0.0
        uncertainty = _clip(1.0 - confidence)
        close_scores = confidence < 0.55 or (confidence - second) < 0.15
        transition_warning = bool(warnings) or close_scores
        reasons = self._reasons(primary, scores, warnings, close_scores)
        regime = RegimeContext(
            primary_regime=MarketRegime(primary),
            regime_scores={key: round(value, 4) for key, value in scores.items()},
            confidence=round(confidence, 4),
            uncertainty_score=round(uncertainty, 4),
            transition_warning=transition_warning,
            volatility_level=self._volatility_level(payload),
            reasons=reasons,
            warnings=warnings,
        )
        return MarketContext(
            regime=regime,
            transition_warnings=warnings,
            features_used=[
                "ema_20",
                "ema_50",
                "ema_20_slope",
                "atr_percent",
                "bollinger_width",
                "rolling_high_20",
                "rolling_low_20",
                "volume_ratio",
                "body_strength",
                "close_range_position",
                "wick_rejection",
            ],
        )

    def _score_regimes(self, payload: Mapping[str, object]) -> dict[str, float]:
        """Calculate bounded soft scores for all supported regimes."""
        close = _value(payload, "close")
        open_price = _value(payload, "open", close)
        high = _value(payload, "high", close)
        low = _value(payload, "low", close)
        ema_20 = _value(payload, "ema_20")
        ema_50 = _value(payload, "ema_50")
        ema_slope = _value(payload, "ema_20_slope")
        atr_percent = _value(payload, "atr_percent")
        bollinger_width = _value(payload, "bollinger_width")
        volume_ratio = _value(payload, "volume_ratio")
        rolling_high = _value(payload, "rolling_high_20", close)
        rolling_low = _value(payload, "rolling_low_20", close)
        volatility_score = _clip(_value(payload, "volatility_score", 0.5))
        breakout_score = _clip(_value(payload, "breakout_score", 0.0) * 100.0)
        trend_score = _value(payload, "trend_score", 0.0)

        ema_spread = abs(ema_20 - ema_50) / close if close else 0.0
        body_strength = _body_strength(open_price, close, high, low)
        close_position = _close_range_position(close, high, low)
        upper_rejection = _upper_wick_rejection(open_price, close, high, low)
        lower_rejection = _lower_wick_rejection(open_price, close, high, low)
        near_high = _near_level(close, rolling_high, close)
        near_low = _near_level(close, rolling_low, close)
        volume_score = _clip(
            volume_ratio / max(self._settings.breakout_volume_ratio_threshold, 1e-9)
        )
        trend_strength = _clip(
            abs(trend_score)
            / max(self._settings.trend_strength_threshold * 5.0, 1e-9)
        )
        slope_strength = _clip(
            abs(ema_slope)
            / max(self._settings.trend_strength_threshold * close, 1e-9)
        )

        ema_up = 1.0 if ema_20 > ema_50 else 0.0
        ema_down = 1.0 if ema_20 < ema_50 else 0.0
        close_above = 1.0 if close > ema_20 else 0.0
        close_below = 1.0 if close < ema_20 else 0.0
        slope_up = slope_strength if ema_slope > 0 else 0.0
        slope_down = slope_strength if ema_slope < 0 else 0.0
        sideway_spread = 1.0 - _clip(
            ema_spread / max(self._settings.sideway_trend_threshold, 1e-9)
        )
        sideway_bollinger = 1.0 - _clip(
            bollinger_width / max(self._settings.sideway_bollinger_width_threshold, 1e-9)
        )
        sideway_atr = 1.0 - _clip(
            atr_percent / max(self._settings.sideway_atr_percent_threshold, 1e-9)
        )
        resistance_break = _clip(
            (close - rolling_high * (1.0 + self._settings.breakout_buffer_pct))
            / max(close, 1e-9)
            * 100.0
        )
        support_break = _clip(
            (rolling_low * (1.0 - self._settings.breakout_buffer_pct) - close)
            / max(close, 1e-9)
            * 100.0
        )

        return {
            MarketRegime.UPTREND.value: _avg(
                [
                    ema_up,
                    close_above,
                    slope_up,
                    trend_strength if trend_score >= 0 else 0.0,
                    body_strength if close_position >= 0.5 else 0.0,
                    1.0 - upper_rejection,
                ]
            ),
            MarketRegime.DOWNTREND.value: _avg(
                [
                    ema_down,
                    close_below,
                    slope_down,
                    trend_strength if trend_score <= 0 else 0.0,
                    body_strength if close_position <= 0.5 else 0.0,
                    1.0 - lower_rejection,
                ]
            ),
            MarketRegime.SIDEWAY.value: _avg(
                [
                    sideway_spread,
                    sideway_bollinger,
                    sideway_atr,
                    1.0 - body_strength,
                    1.0 - max(near_high, near_low),
                ]
            ),
            MarketRegime.BREAKOUT_UP.value: _avg(
                [
                    resistance_break,
                    volume_score,
                    breakout_score,
                    body_strength,
                    close_position,
                    1.0 - upper_rejection,
                ]
            ),
            MarketRegime.BREAKOUT_DOWN.value: _avg(
                [
                    support_break,
                    volume_score,
                    breakout_score,
                    body_strength,
                    1.0 - close_position,
                    1.0 - lower_rejection,
                ]
            ),
            MarketRegime.HIGH_VOLATILITY.value: _clip(
                max(
                    (atr_percent - self._settings.sideway_atr_percent_threshold)
                    / max(
                        self._settings.high_volatility_threshold
                        - self._settings.sideway_atr_percent_threshold,
                        1e-9,
                    ),
                    volatility_score - self._settings.high_volatility_percentile,
                )
            ),
            MarketRegime.LOW_VOLATILITY.value: _clip(
                (self._settings.sideway_atr_percent_threshold - atr_percent)
                / max(self._settings.sideway_atr_percent_threshold, 1e-9)
            ),
            MarketRegime.UNKNOWN.value: 0.0,
        }

    def _transition_warnings(
        self,
        payload: Mapping[str, object],
        scores: Mapping[str, float],
    ) -> list[MarketTransitionWarning]:
        """Detect conditions that make the regime unstable."""
        warnings: list[MarketTransitionWarning] = []
        primary = max(scores.items(), key=lambda item: item[1])[0]
        close = _value(payload, "close")
        open_price = _value(payload, "open", close)
        high = _value(payload, "high", close)
        low = _value(payload, "low", close)
        atr_percent = _value(payload, "atr_percent")
        atr_change = _value(payload, "atr_percent_change", 0.0)
        volume_ratio = _value(payload, "volume_ratio")
        rolling_high = _value(payload, "rolling_high_20", close)
        rolling_low = _value(payload, "rolling_low_20", close)
        ema_slope = _value(payload, "ema_20_slope")
        ema_slope_change = _value(payload, "ema_20_slope_change", 0.0)
        upper_rejection = _upper_wick_rejection(open_price, close, high, low)
        lower_rejection = _lower_wick_rejection(open_price, close, high, low)
        near_high = _near_level(close, rolling_high, close)
        near_low = _near_level(close, rolling_low, close)

        if scores.get(MarketRegime.SIDEWAY.value, 0.0) >= 0.45 and (
            atr_change > 0.25
            or atr_percent > self._settings.sideway_atr_percent_threshold
        ):
            warnings.append(
                MarketTransitionWarning(
                    "SIDEWAY_ATR_EXPANSION",
                    "SIDEWAY context but ATR is expanding quickly.",
                    _clip(max(atr_change, atr_percent)),
                )
            )
        if scores.get(MarketRegime.SIDEWAY.value, 0.0) >= 0.45 and volume_ratio >= (
            self._settings.breakout_volume_ratio_threshold * 1.2
        ):
            warnings.append(
                MarketTransitionWarning(
                    "SIDEWAY_VOLUME_EXPANSION",
                    "SIDEWAY context but volume ratio is unusually high.",
                    _clip(volume_ratio / 3.0),
                )
            )
        if max(near_high, near_low) > 0.8:
            warnings.append(
                MarketTransitionWarning(
                    "RANGE_EDGE_PRESSURE",
                    "Close is repeatedly near rolling high/low area.",
                    max(near_high, near_low),
                )
            )
        if primary == MarketRegime.UPTREND.value and (
            ema_slope <= 0
            or ema_slope_change < 0
            or scores.get(MarketRegime.UPTREND.value, 0.0) < 0.65
        ):
            warnings.append(
                MarketTransitionWarning(
                    "UPTREND_SLOPE_WEAKENING",
                    "UPTREND context but EMA slope is weakening.",
                    _clip(abs(ema_slope_change) + (0.65 - scores.get(MarketRegime.UPTREND.value, 0.0))),
                )
            )
        breakout_up_score = scores.get(MarketRegime.BREAKOUT_UP.value, 0.0)
        breakout_down_score = scores.get(MarketRegime.BREAKOUT_DOWN.value, 0.0)
        if breakout_up_score >= 0.4 and upper_rejection >= 0.45:
            warnings.append(
                MarketTransitionWarning(
                    "BREAKOUT_REJECTION_WICK",
                    "BREAKOUT context has a large rejection wick.",
                    upper_rejection,
                )
            )
        if breakout_down_score >= 0.4 and lower_rejection >= 0.45:
            warnings.append(
                MarketTransitionWarning(
                    "BREAKOUT_REJECTION_WICK",
                    "BREAKOUT context has a large rejection wick.",
                    lower_rejection,
                )
            )
        return warnings

    def _apply_warning_penalties(
        self,
        scores: dict[str, float],
        warnings: list[MarketTransitionWarning],
    ) -> dict[str, float]:
        """Reduce confidence for regimes invalidated by warning evidence."""
        adjusted = dict(scores)
        for warning in warnings:
            penalty = min(0.25, warning.severity * 0.25)
            if warning.warning_type == "BREAKOUT_REJECTION_WICK":
                adjusted[MarketRegime.BREAKOUT_UP.value] = _clip(
                    adjusted.get(MarketRegime.BREAKOUT_UP.value, 0.0) - penalty
                )
                adjusted[MarketRegime.BREAKOUT_DOWN.value] = _clip(
                    adjusted.get(MarketRegime.BREAKOUT_DOWN.value, 0.0) - penalty
                )
            elif warning.warning_type.startswith("SIDEWAY_"):
                adjusted[MarketRegime.SIDEWAY.value] = _clip(
                    adjusted.get(MarketRegime.SIDEWAY.value, 0.0) - penalty
                )
        return adjusted

    def _volatility_level(self, payload: Mapping[str, object]) -> VolatilityLevel:
        """Bucket ATR percent into a stable volatility level."""
        atr_percent = _value(payload, "atr_percent", 0.0)
        if atr_percent <= self._settings.sideway_atr_percent_threshold * 0.5:
            return VolatilityLevel.LOW
        if atr_percent <= self._settings.sideway_atr_percent_threshold:
            return VolatilityLevel.NORMAL
        if atr_percent <= self._settings.high_volatility_threshold:
            return VolatilityLevel.HIGH
        return VolatilityLevel.EXTREME

    def _reasons(
        self,
        primary: str,
        scores: Mapping[str, float],
        warnings: list[MarketTransitionWarning],
        close_scores: bool,
    ) -> list[str]:
        """Build concise market context reasons."""
        ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        reasons = [
            f"Primary regime is {primary} with score {ordered[0][1]:.2f}.",
        ]
        if len(ordered) > 1:
            reasons.append(f"Second regime candidate is {ordered[1][0]} with score {ordered[1][1]:.2f}.")
        if close_scores:
            reasons.append("Top regime scores are close or confidence is low.")
        reasons.extend(warning.message for warning in warnings)
        return reasons


def _has_required(payload: Mapping[str, object]) -> bool:
    """Return True when the row has enough inputs for context scoring."""
    required = ["close", "ema_20", "ema_50", "atr_percent", "bollinger_width"]
    return all(_is_number(payload.get(key)) for key in required)


def _value(payload: Mapping[str, object], key: str, default: float = 0.0) -> float:
    """Read a numeric feature value safely."""
    value = payload.get(key, default)
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if np.isnan(parsed):
        return default
    return parsed


def _is_number(value: object) -> bool:
    """Return True for finite numeric values."""
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return False
    return not np.isnan(parsed)


def _body_strength(open_price: float, close: float, high: float, low: float) -> float:
    """Return candle body share of total range."""
    candle_range = max(high - low, 1e-9)
    return _clip(abs(close - open_price) / candle_range)


def _close_range_position(close: float, high: float, low: float) -> float:
    """Return close position inside the candle range."""
    return _clip((close - low) / max(high - low, 1e-9))


def _upper_wick_rejection(open_price: float, close: float, high: float, low: float) -> float:
    """Return upper wick share of total range."""
    candle_range = max(high - low, 1e-9)
    body_top = max(open_price, close)
    return _clip((high - body_top) / candle_range)


def _lower_wick_rejection(open_price: float, close: float, high: float, low: float) -> float:
    """Return lower wick share of total range."""
    candle_range = max(high - low, 1e-9)
    body_bottom = min(open_price, close)
    return _clip((body_bottom - low) / candle_range)


def _near_level(close: float, level: float, denominator: float) -> float:
    """Score how close price is to a rolling level."""
    distance = abs(close - level) / max(abs(denominator), 1e-9)
    return 1.0 - _clip(distance / 0.01)


def _clip(value: float) -> float:
    """Clamp a value into 0..1."""
    if np.isnan(value):
        return 0.0
    return max(0.0, min(float(value), 1.0))


def _avg(values: list[float]) -> float:
    """Return bounded average score."""
    return _clip(sum(values) / len(values)) if values else 0.0
