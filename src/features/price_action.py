"""Vectorized price action feature engineering."""

from __future__ import annotations

import numpy as np
import pandas as pd


PRICE_ACTION_COLUMNS = [
    "return_1",
    "return_3",
    "return_5",
    "candle_range",
    "body_size",
    "body_ratio",
    "upper_wick",
    "lower_wick",
    "upper_wick_ratio",
    "lower_wick_ratio",
]


def add_price_action_features(candles: pd.DataFrame) -> pd.DataFrame:
    """Add vectorized price action features without mutating the input."""
    df = candles.copy(deep=True)
    candle_range = df["high"] - df["low"]
    safe_range = candle_range.replace(0, np.nan)
    body_size = (df["close"] - df["open"]).abs()
    upper_wick = df["high"] - np.maximum(df["open"], df["close"])
    lower_wick = np.minimum(df["open"], df["close"]) - df["low"]

    df["return_1"] = df["close"].pct_change(1)
    df["return_3"] = df["close"].pct_change(3)
    df["return_5"] = df["close"].pct_change(5)
    df["candle_range"] = candle_range
    df["body_size"] = body_size
    df["body_ratio"] = body_size / safe_range
    df["upper_wick"] = upper_wick.clip(lower=0)
    df["lower_wick"] = lower_wick.clip(lower=0)
    df["upper_wick_ratio"] = df["upper_wick"] / safe_range
    df["lower_wick_ratio"] = df["lower_wick"] / safe_range
    return df
