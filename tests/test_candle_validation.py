"""Tests for OHLCV candle validation."""

from __future__ import annotations

from dataclasses import replace

import pytest

from collector.base import CandleValidationError, validate_candle
from domain.entities import Candle


def test_validate_candle_accepts_valid_ohlcv(valid_candle: Candle):
    validate_candle(valid_candle)


def test_validate_candle_rejects_high_below_low(valid_candle: Candle):
    candle = replace(valid_candle, high=90.0, low=100.0)

    with pytest.raises(CandleValidationError):
        validate_candle(candle)


@pytest.mark.parametrize("field", ["open", "high", "low", "close"])
def test_validate_candle_rejects_non_positive_prices(valid_candle: Candle, field: str):
    candle = replace(valid_candle, **{field: 0.0})

    with pytest.raises(CandleValidationError):
        validate_candle(candle)


def test_validate_candle_rejects_negative_volume(valid_candle: Candle):
    candle = replace(valid_candle, volume=-1.0)

    with pytest.raises(CandleValidationError):
        validate_candle(candle)
