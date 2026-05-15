"""Vectorized technical indicator features."""

from __future__ import annotations

import numpy as np
import pandas as pd


TREND_COLUMNS = [
    "ema_20",
    "ema_50",
    "ema_200",
    "ema_20_slope",
    "ema_50_slope",
    "close_above_ema20",
    "close_above_ema50",
]
MOMENTUM_COLUMNS = ["rsi_14", "macd", "macd_signal", "macd_hist"]
VOLATILITY_COLUMNS = [
    "atr_14",
    "atr_percent",
    "bollinger_upper",
    "bollinger_lower",
    "bollinger_width",
]
VOLUME_COLUMNS = ["volume_sma_20", "volume_ratio", "volume_change"]


def add_trend_features(candles: pd.DataFrame) -> pd.DataFrame:
    """Add EMA-based trend features without future data."""
    df = candles.copy(deep=True)
    df["ema_20"] = ema(df["close"], 20)
    df["ema_50"] = ema(df["close"], 50)
    df["ema_200"] = ema(df["close"], 200)
    df["ema_20_slope"] = df["ema_20"].diff()
    df["ema_50_slope"] = df["ema_50"].diff()
    df["close_above_ema20"] = _boolean_feature(df["close"] > df["ema_20"], df["ema_20"])
    df["close_above_ema50"] = _boolean_feature(df["close"] > df["ema_50"], df["ema_50"])
    return df


def add_momentum_features(candles: pd.DataFrame) -> pd.DataFrame:
    """Add RSI and MACD momentum features."""
    df = candles.copy(deep=True)
    df["rsi_14"] = rsi(df["close"], 14)
    macd_line, signal_line, histogram = macd(df["close"])
    df["macd"] = macd_line
    df["macd_signal"] = signal_line
    df["macd_hist"] = histogram
    return df


def add_volatility_features(candles: pd.DataFrame) -> pd.DataFrame:
    """Add ATR and Bollinger volatility features."""
    df = candles.copy(deep=True)
    df["atr_14"] = atr(df["high"], df["low"], df["close"], 14)
    df["atr_percent"] = df["atr_14"] / df["close"]
    middle = df["close"].rolling(window=20, min_periods=20).mean()
    std = df["close"].rolling(window=20, min_periods=20).std(ddof=0)
    df["bollinger_upper"] = middle + (2.0 * std)
    df["bollinger_lower"] = middle - (2.0 * std)
    df["bollinger_width"] = (df["bollinger_upper"] - df["bollinger_lower"]) / middle
    return df


def add_volume_features(candles: pd.DataFrame) -> pd.DataFrame:
    """Add volume trend and change features."""
    df = candles.copy(deep=True)
    df["volume_sma_20"] = df["volume"].rolling(window=20, min_periods=20).mean()
    df["volume_ratio"] = df["volume"] / df["volume_sma_20"].replace(0, np.nan)
    df["volume_change"] = df["volume"].pct_change(1)
    return df


def ema(series: pd.Series, period: int) -> pd.Series:
    """Calculate an exponential moving average."""
    return series.ewm(span=period, adjust=False, min_periods=period).mean()


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Calculate Wilder RSI using only current and past data."""
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    average_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    average_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    relative_strength = average_gain / average_loss.replace(0, np.nan)
    value = 100.0 - (100.0 / (1.0 + relative_strength))
    return value.mask((average_loss == 0) & (average_gain > 0), 100.0)


def macd(
    close: pd.Series,
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Calculate MACD line, signal line, and histogram."""
    fast = ema(close, fast_period)
    slow = ema(close, slow_period)
    macd_line = fast - slow
    signal_line = macd_line.ewm(
        span=signal_period,
        adjust=False,
        min_periods=signal_period,
    ).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def atr(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14,
) -> pd.Series:
    """Calculate Average True Range."""
    previous_close = close.shift(1)
    true_range = pd.concat(
        [
            high - low,
            (high - previous_close).abs(),
            (low - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return true_range.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def _boolean_feature(condition: pd.Series, valid_when: pd.Series) -> pd.Series:
    """Represent boolean features as 1/0 while preserving warmup NaNs."""
    return pd.Series(
        np.where(valid_when.notna(), condition.astype(int), np.nan),
        index=condition.index,
    )
