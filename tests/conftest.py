"""Test configuration."""

from __future__ import annotations

from pathlib import Path
import sys
from datetime import UTC, datetime

import pytest


ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from config.loader import load_settings  # noqa: E402
from config.settings import Settings  # noqa: E402
from domain.entities import Candle  # noqa: E402


@pytest.fixture
def settings() -> Settings:
    """Return project settings for business-logic tests."""
    return load_settings()


@pytest.fixture
def valid_candle() -> Candle:
    """Return a valid reusable OHLCV candle."""
    return Candle(
        symbol="BTC/USDT",
        timeframe="1h",
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        open=100.0,
        high=110.0,
        low=95.0,
        close=105.0,
        volume=10.0,
    )


@pytest.fixture
def trend_buy_features() -> dict[str, float]:
    """Return a compact feature row for a trend-following BUY setup."""
    return {
        "close": 101.0,
        "atr_14": 10.0,
        "ema_20": 100.0,
        "ema_50": 95.0,
        "rsi_14": 55.0,
        "volume_ratio": 1.3,
        "rolling_high_20": 120.0,
        "rolling_low_20": 80.0,
        "trend_score": 1.0,
    }
