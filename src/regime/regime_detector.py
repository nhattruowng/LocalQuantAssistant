"""Rule-based market regime detector."""

from __future__ import annotations

import json
import numpy as np
import pandas as pd

from config.settings import MarketRegimeSettings
from regime.market_context_engine import MarketContextEngine
from regime.market_regime import MarketRegime, RegimeDetectionResult


REQUIRED_REGIME_COLUMNS = [
    "close",
    "high",
    "low",
    "ema_20",
    "ema_50",
    "ema_20_slope",
    "bollinger_width",
    "atr_percent",
    "volume_ratio",
]
REGIME_OUTPUT_COLUMNS = [
    "rolling_high_20",
    "rolling_low_20",
    "market_regime",
    "primary_regime",
    "regime_scores",
    "regime_confidence",
    "regime_uncertainty_score",
    "transition_warning",
    "volatility_level",
    "market_transition_warnings",
    "trend_score",
    "volatility_score",
    "breakout_score",
    "regime_reason",
]


class MarketRegimeDetector:
    """Detects market regimes from engineered feature data."""

    def __init__(self, settings: MarketRegimeSettings) -> None:
        self._settings = settings
        self._context_engine = MarketContextEngine(settings)

    def detect(self, features: pd.DataFrame) -> pd.DataFrame:
        """Return a new DataFrame with regime columns added."""
        self._validate_input(features)
        df = features.copy(deep=True)
        window = self._settings.breakout_window

        df["rolling_high_20"] = df["high"].shift(1).rolling(
            window=window,
            min_periods=window,
        ).max()
        df["rolling_low_20"] = df["low"].shift(1).rolling(
            window=window,
            min_periods=window,
        ).min()
        df["trend_score"] = self._trend_score(df)
        df["volatility_score"] = self._volatility_score(df)
        df["breakout_score"] = self._breakout_score(df)
        df["atr_percent_change"] = df["atr_percent"].pct_change().replace(
            [np.inf, -np.inf],
            0.0,
        )
        df["ema_20_slope_change"] = df["ema_20_slope"].diff()

        df["market_regime"], df["regime_reason"] = self._classify(df)
        market_contexts = [self._context_engine.evaluate(row) for _, row in df.iterrows()]
        soft_results = [context.regime for context in market_contexts]
        df["primary_regime"] = [result.primary_regime.value for result in soft_results]
        df["regime_scores"] = [
            json.dumps(result.regime_scores, sort_keys=True) for result in soft_results
        ]
        df["regime_confidence"] = [result.confidence for result in soft_results]
        df["regime_uncertainty_score"] = [
            result.uncertainty_score for result in soft_results
        ]
        df["transition_warning"] = [result.transition_warning for result in soft_results]
        df["volatility_level"] = [
            result.volatility_level.value for result in soft_results
        ]
        df["market_transition_warnings"] = [
            json.dumps(
                [
                    {
                        "warning_type": warning.warning_type,
                        "message": warning.message,
                        "severity": round(warning.severity, 4),
                    }
                    for warning in result.warnings
                ],
                sort_keys=True,
            )
            for result in soft_results
        ]
        df["regime_reason"] = [
            json.dumps(result.reasons) if result.reasons else reason
            for result, reason in zip(soft_results, df["regime_reason"], strict=False)
        ]
        if self._settings.adaptive_strategy_enabled:
            df["market_regime"] = df["primary_regime"]
        return df

    def _validate_input(self, features: pd.DataFrame) -> None:
        """Validate required feature columns."""
        missing = [column for column in REQUIRED_REGIME_COLUMNS if column not in features]
        if missing:
            raise ValueError(f"Feature DataFrame is missing regime columns: {missing}.")
        if features.empty:
            raise ValueError("Feature DataFrame must not be empty.")

    def _trend_score(self, df: pd.DataFrame) -> pd.Series:
        """Score EMA separation and direction."""
        ema_spread = (df["ema_20"] - df["ema_50"]) / df["close"]
        slope_direction = np.sign(df["ema_20_slope"]).fillna(0.0)
        return ema_spread + (slope_direction * self._settings.trend_strength_threshold)

    def _volatility_score(self, df: pd.DataFrame) -> pd.Series:
        """Score ATR percentile over a trailing window."""
        window = self._settings.volatility_percentile_window
        return df["atr_percent"].rolling(window=window, min_periods=1).rank(pct=True)

    def _breakout_score(self, df: pd.DataFrame) -> pd.Series:
        """Score distance beyond rolling support/resistance with volume confirmation."""
        resistance_break = (df["close"] - df["rolling_high_20"]) / df["close"]
        support_break = (df["rolling_low_20"] - df["close"]) / df["close"]
        directional_break = resistance_break.where(
            resistance_break > 0,
            support_break.where(support_break > 0, 0.0),
        )
        volume_boost = (
            df["volume_ratio"] / self._settings.breakout_volume_ratio_threshold
        ).clip(lower=0.0)
        return directional_break.fillna(0.0) * volume_boost.fillna(0.0)

    def _classify(self, df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
        """Classify rows with vectorized rule masks."""
        settings = self._settings
        required = [
            "close",
            "ema_20",
            "ema_50",
            "ema_20_slope",
            "atr_percent",
            "volume_ratio",
            "bollinger_width",
            "rolling_high_20",
            "rolling_low_20",
            "volatility_score",
        ]
        valid = df[required].notna().all(axis=1)
        regime = pd.Series(MarketRegime.UNKNOWN.value, index=df.index, dtype="object")
        reason = pd.Series(
            _reason(["Missing required indicator values."]),
            index=df.index,
            dtype="object",
        )
        reason.loc[valid] = _reason(["No regime rule matched."])

        breakout_up = (
            valid
            & (df["close"] > df["rolling_high_20"] * (1.0 + settings.breakout_buffer_pct))
            & (df["volume_ratio"] > settings.breakout_volume_ratio_threshold)
            & (df["atr_percent"] > settings.breakout_atr_percent_threshold)
        )
        breakout_down = (
            valid
            & (df["close"] < df["rolling_low_20"] * (1.0 - settings.breakout_buffer_pct))
            & (df["volume_ratio"] > settings.breakout_volume_ratio_threshold)
            & (df["atr_percent"] > settings.breakout_atr_percent_threshold)
        )
        high_volatility = valid & (
            df["volatility_score"] >= settings.high_volatility_percentile
        )
        low_volatility = valid & (
            df["volatility_score"] <= settings.low_volatility_percentile
        )
        trend_distance = (df["ema_20"] - df["ema_50"]).abs() / df["close"]
        sideway = (
            valid
            & (trend_distance < settings.sideway_trend_threshold)
            & (df["bollinger_width"] < settings.sideway_bollinger_width_threshold)
            & (df["atr_percent"] <= settings.sideway_atr_percent_threshold)
        )
        uptrend = (
            valid
            & (df["ema_20"] > df["ema_50"])
            & (df["close"] > df["ema_20"])
            & (df["ema_20_slope"] > 0)
        )
        downtrend = (
            valid
            & (df["ema_20"] < df["ema_50"])
            & (df["close"] < df["ema_20"])
            & (df["ema_20_slope"] < 0)
        )

        pending = pd.Series(True, index=df.index)
        self._assign(
            regime,
            reason,
            pending,
            breakout_up,
            MarketRegime.BREAKOUT_UP,
            [
                "Close broke above rolling resistance.",
                "Volume ratio confirmed breakout.",
                "ATR percent confirmed expansion.",
            ],
        )
        self._assign(
            regime,
            reason,
            pending,
            breakout_down,
            MarketRegime.BREAKOUT_DOWN,
            [
                "Close broke below rolling support.",
                "Volume ratio confirmed breakout.",
                "ATR percent confirmed expansion.",
            ],
        )
        self._assign(
            regime,
            reason,
            pending,
            high_volatility,
            MarketRegime.HIGH_VOLATILITY,
            ["ATR percent is in the high trailing percentile."],
        )
        self._assign(
            regime,
            reason,
            pending,
            low_volatility,
            MarketRegime.LOW_VOLATILITY,
            ["ATR percent is in the low trailing percentile."],
        )
        self._assign(
            regime,
            reason,
            pending,
            sideway,
            MarketRegime.SIDEWAY,
            [
                "EMA spread is narrow.",
                "Bollinger width is low.",
                "ATR percent is low or medium.",
            ],
        )
        self._assign(
            regime,
            reason,
            pending,
            uptrend,
            MarketRegime.UPTREND,
            [
                "EMA20 is above EMA50.",
                "Close is above EMA20.",
                "EMA20 slope is positive.",
            ],
        )
        self._assign(
            regime,
            reason,
            pending,
            downtrend,
            MarketRegime.DOWNTREND,
            [
                "EMA20 is below EMA50.",
                "Close is below EMA20.",
                "EMA20 slope is negative.",
            ],
        )
        return regime, reason

    def _soft_result(self, row: pd.Series) -> RegimeDetectionResult:
        """Return soft regime scores for one feature row."""
        return self._context_engine.evaluate(row).regime

    def _soft_scores(self, row: pd.Series) -> dict[str, float]:
        """Calculate bounded soft scores for all supported regimes."""
        close = float(row.get("close", 0.0))
        ema_20 = float(row.get("ema_20", 0.0))
        ema_50 = float(row.get("ema_50", 0.0))
        ema_slope = float(row.get("ema_20_slope", 0.0))
        atr_percent = float(row.get("atr_percent", 0.0))
        bollinger_width = float(row.get("bollinger_width", 1.0))
        volume_ratio = float(row.get("volume_ratio", 0.0))
        volatility_score = _clip(float(row.get("volatility_score", 0.0)))
        breakout_score = _clip(float(row.get("breakout_score", 0.0)) * 100.0)
        trend_value = float(row.get("trend_score", 0.0))
        rolling_high = float(row.get("rolling_high_20", close))
        rolling_low = float(row.get("rolling_low_20", close))
        volume_score = _clip(volume_ratio / max(self._settings.breakout_volume_ratio_threshold, 1e-9))

        ema_up = 1.0 if ema_20 > ema_50 else 0.0
        ema_down = 1.0 if ema_20 < ema_50 else 0.0
        close_above = 1.0 if close > ema_20 else 0.0
        close_below = 1.0 if close < ema_20 else 0.0
        slope_up = 1.0 if ema_slope > 0 else 0.0
        slope_down = 1.0 if ema_slope < 0 else 0.0
        trend_strength = _clip(abs(trend_value) / max(self._settings.trend_strength_threshold * 5.0, 1e-9))
        ema_spread = abs(ema_20 - ema_50) / close if close else 0.0
        sideway_spread = 1.0 - _clip(ema_spread / max(self._settings.sideway_trend_threshold, 1e-9))
        sideway_bollinger = 1.0 - _clip(bollinger_width / max(self._settings.sideway_bollinger_width_threshold, 1e-9))
        sideway_atr = 1.0 - _clip(atr_percent / max(self._settings.sideway_atr_percent_threshold, 1e-9))
        resistance_break = 1.0 if close > rolling_high else 0.0
        support_break = 1.0 if close < rolling_low else 0.0

        scores = {
            MarketRegime.UPTREND.value: _avg([ema_up, close_above, slope_up, trend_strength if trend_value > 0 else 0.0]),
            MarketRegime.DOWNTREND.value: _avg([ema_down, close_below, slope_down, trend_strength if trend_value < 0 else 0.0]),
            MarketRegime.SIDEWAY.value: _avg([sideway_spread, sideway_bollinger, sideway_atr]),
            MarketRegime.BREAKOUT_UP.value: _avg([resistance_break, volume_score, breakout_score]),
            MarketRegime.BREAKOUT_DOWN.value: _avg([support_break, volume_score, breakout_score]),
            MarketRegime.HIGH_VOLATILITY.value: volatility_score,
            MarketRegime.LOW_VOLATILITY.value: 1.0 - volatility_score,
            MarketRegime.UNKNOWN.value: 0.0,
        }
        return {key: _clip(value) for key, value in scores.items()}

    def _soft_reasons(self, primary: str, transition_warning: bool) -> list[str]:
        """Build concise soft regime reasons."""
        reasons = [f"Highest soft regime score is {primary}."]
        if transition_warning:
            reasons.append("Regime scores are close or confidence is low; transition warning enabled.")
        return reasons

    def _assign(
        self,
        regime: pd.Series,
        reason: pd.Series,
        pending: pd.Series,
        mask: pd.Series,
        value: MarketRegime,
        reason_items: list[str],
    ) -> None:
        """Assign a regime to rows that have not matched a higher-priority rule."""
        selected = pending & mask
        regime.loc[selected] = value.value
        reason.loc[selected] = _reason(reason_items)
        pending.loc[selected] = False


def _reason(items: list[str]) -> str:
    """Serialize regime reasons for CSV-friendly output."""
    return json.dumps(items)


def _clip(value: float) -> float:
    """Clamp a value into 0..1."""
    if np.isnan(value):
        return 0.0
    return max(0.0, min(float(value), 1.0))


def _avg(values: list[float]) -> float:
    """Return bounded average score."""
    return _clip(sum(values) / len(values)) if values else 0.0
