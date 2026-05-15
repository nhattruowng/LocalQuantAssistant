"""Market data collector contracts and validation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
import math
from typing import Protocol

from domain.entities import Candle, MarketSnapshot


class MarketDataSource(Protocol):
    """Contract for exchange, file, or API market data sources."""

    def latest_snapshot(self, symbol: str) -> MarketSnapshot:
        """Return the latest market snapshot for a symbol."""


class CandleValidationError(ValueError):
    """Raised when an OHLCV candle fails validation."""


class BaseMarketDataCollector(ABC):
    """Base interface for market data collectors."""

    @abstractmethod
    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        since: datetime | None = None,
        limit: int | None = None,
    ) -> list[Candle]:
        """Fetch OHLCV candles for a symbol and timeframe."""


def validate_candle(candle: Candle) -> None:
    """Validate one OHLCV candle before persistence."""
    if candle.timestamp is None:
        raise CandleValidationError("Candle timestamp must not be null.")
    if candle.high < candle.low:
        raise CandleValidationError("Candle high must be greater than or equal to low.")
    prices = [candle.open, candle.high, candle.low, candle.close]
    if any(not math.isfinite(price) or price <= 0 for price in prices):
        raise CandleValidationError("Candle open/high/low/close must be positive numbers.")
    if not math.isfinite(candle.volume) or candle.volume < 0:
        raise CandleValidationError("Candle volume must be a non-negative number.")


def validate_candles(candles: list[Candle]) -> None:
    """Validate a batch of OHLCV candles."""
    for candle in candles:
        validate_candle(candle)
