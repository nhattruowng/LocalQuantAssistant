"""Binance OHLCV collector implemented with ccxt."""

from __future__ import annotations

from datetime import UTC, datetime
import logging
import time
from typing import Any

from collector.base import BaseMarketDataCollector, validate_candles
from domain.entities import Candle


class BinanceCollector(BaseMarketDataCollector):
    """Fetches OHLCV candles from Binance through ccxt."""

    def __init__(
        self,
        retry_attempts: int = 3,
        retry_delay_seconds: float = 1.0,
        logger: logging.Logger | None = None,
        exchange: Any | None = None,
    ) -> None:
        self.retry_attempts = retry_attempts
        self.retry_delay_seconds = retry_delay_seconds
        self.logger = logger or logging.getLogger("localquant.collector")
        self._exchange = exchange

    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        since: datetime | None = None,
        limit: int | None = None,
    ) -> list[Candle]:
        """Fetch and validate OHLCV candles from Binance."""
        self.logger.info(
            "Starting Binance OHLCV download: symbol=%s timeframe=%s limit=%s",
            symbol,
            timeframe,
            limit,
        )
        raw_candles = self._fetch_with_retry(symbol, timeframe, since, limit)
        candles = [
            _raw_ohlcv_to_candle(symbol=symbol, timeframe=timeframe, raw=raw)
            for raw in raw_candles
        ]
        validate_candles(candles)
        self.logger.info(
            "Downloaded %s candles from Binance: symbol=%s timeframe=%s",
            len(candles),
            symbol,
            timeframe,
        )
        return candles

    @property
    def exchange(self) -> Any:
        """Return a lazily initialized ccxt Binance exchange."""
        if self._exchange is None:
            try:
                import ccxt
            except ModuleNotFoundError as error:
                raise RuntimeError(
                    "ccxt is required for BinanceCollector. Run `pip install -r requirements.txt`."
                ) from error
            self._exchange = ccxt.binance({"enableRateLimit": True})
        return self._exchange

    def _fetch_with_retry(
        self,
        symbol: str,
        timeframe: str,
        since: datetime | None,
        limit: int | None,
    ) -> list[list[float]]:
        """Call ccxt fetch_ohlcv with bounded retry."""
        last_error: Exception | None = None
        since_ms = _datetime_to_milliseconds(since) if since else None

        for attempt in range(1, self.retry_attempts + 1):
            try:
                return self.exchange.fetch_ohlcv(
                    symbol,
                    timeframe=timeframe,
                    since=since_ms,
                    limit=limit,
                )
            except Exception as error:  # ccxt raises exchange/network-specific errors
                last_error = error
                self.logger.warning(
                    "Binance OHLCV download failed: symbol=%s timeframe=%s attempt=%s/%s error=%s",
                    symbol,
                    timeframe,
                    attempt,
                    self.retry_attempts,
                    error,
                )
                if attempt < self.retry_attempts:
                    time.sleep(self.retry_delay_seconds)

        message = (
            f"Binance OHLCV download failed after {self.retry_attempts} attempts: "
            f"symbol={symbol} timeframe={timeframe}"
        )
        self.logger.error("%s", message)
        raise RuntimeError(message) from last_error


def _raw_ohlcv_to_candle(
    symbol: str,
    timeframe: str,
    raw: list[float],
) -> Candle:
    """Convert ccxt OHLCV row into a Candle."""
    timestamp_ms, open_price, high, low, close, volume = raw
    return Candle(
        symbol=symbol,
        timeframe=timeframe,
        timestamp=datetime.fromtimestamp(timestamp_ms / 1000, tz=UTC),
        open=float(open_price),
        high=float(high),
        low=float(low),
        close=float(close),
        volume=float(volume),
    )


def _datetime_to_milliseconds(value: datetime) -> int:
    """Convert datetime to exchange timestamp milliseconds."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return int(value.timestamp() * 1000)
