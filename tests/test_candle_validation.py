"""Tests for OHLCV candle validation."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from collector.base import CandleValidationError, validate_candle
from domain.entities import Candle


def test_validate_candle_accepts_valid_ohlcv():
    validate_candle(_valid_candle())


def test_validate_candle_rejects_high_below_low():
    candle = replace(_valid_candle(), high=90.0, low=100.0)

    with pytest.raises(CandleValidationError):
        validate_candle(candle)


def test_validate_candle_rejects_non_positive_prices():
    candle = replace(_valid_candle(), close=0.0)

    with pytest.raises(CandleValidationError):
        validate_candle(candle)


def test_validate_candle_rejects_negative_volume():
    candle = replace(_valid_candle(), volume=-1.0)

    with pytest.raises(CandleValidationError):
        validate_candle(candle)


def _valid_candle() -> Candle:
    """Build a valid test candle."""
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
