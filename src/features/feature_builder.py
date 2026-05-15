"""Composable feature builder for OHLCV candles."""

from __future__ import annotations

from typing import Mapping

import pandas as pd

from config.settings import FeatureToggleSettings
from domain.entities import MarketSnapshot
from features.indicators import (
    MOMENTUM_COLUMNS,
    TREND_COLUMNS,
    VOLATILITY_COLUMNS,
    VOLUME_COLUMNS,
    add_momentum_features,
    add_trend_features,
    add_volatility_features,
    add_volume_features,
)
from features.price_action import PRICE_ACTION_COLUMNS, add_price_action_features


REQUIRED_CANDLE_COLUMNS = ["timestamp", "open", "high", "low", "close", "volume"]
ALL_FEATURE_COLUMNS = [
    *PRICE_ACTION_COLUMNS,
    *TREND_COLUMNS,
    *MOMENTUM_COLUMNS,
    *VOLATILITY_COLUMNS,
    *VOLUME_COLUMNS,
]


class FeatureBuilder:
    """Builds ML-ready technical features from candle DataFrames."""

    def __init__(self, toggles: FeatureToggleSettings) -> None:
        self._toggles = toggles

    def build(self, candles: pd.DataFrame, drop_warmup_rows: bool = False) -> pd.DataFrame:
        """Return a new DataFrame with enabled feature groups added."""
        self._validate_input(candles)
        features = candles.copy(deep=True)
        features = features.sort_values("timestamp").reset_index(drop=True)

        if self._toggles.price_action:
            features = add_price_action_features(features)
        if self._toggles.trend:
            features = add_trend_features(features)
        if self._toggles.momentum:
            features = add_momentum_features(features)
        if self._toggles.volatility:
            features = add_volatility_features(features)
        if self._toggles.volume:
            features = add_volume_features(features)

        if drop_warmup_rows:
            enabled_columns = [column for column in ALL_FEATURE_COLUMNS if column in features]
            features = features.dropna(subset=enabled_columns).reset_index(drop=True)
        return features

    def _validate_input(self, candles: pd.DataFrame) -> None:
        """Validate the candle DataFrame shape."""
        missing = [column for column in REQUIRED_CANDLE_COLUMNS if column not in candles]
        if missing:
            raise ValueError(f"Candle DataFrame is missing columns: {missing}.")
        if candles.empty:
            raise ValueError("Candle DataFrame must not be empty.")


def build_basic_features(snapshot: MarketSnapshot) -> Mapping[str, float]:
    """Build a small baseline feature set from a market snapshot."""
    return {"close_price": snapshot.close_price}
