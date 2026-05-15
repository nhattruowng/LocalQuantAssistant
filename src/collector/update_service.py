"""Service for updating local candle storage."""

from __future__ import annotations

from datetime import timedelta
import logging

from collector.base import BaseMarketDataCollector
from config.settings import CollectorSettings
from database.candle_repository import CandleRepository


class MarketDataUpdateService:
    """Coordinates collector downloads and candle persistence."""

    def __init__(
        self,
        collector: BaseMarketDataCollector,
        repository: CandleRepository,
        settings: CollectorSettings,
        logger: logging.Logger | None = None,
    ) -> None:
        self._collector = collector
        self._repository = repository
        self._settings = settings
        self._logger = logger or logging.getLogger("localquant.collector")

    def update_latest(
        self,
        symbols: tuple[str, ...] | None = None,
        timeframes: tuple[str, ...] | None = None,
    ) -> int:
        """Update configured symbol/timeframe candles and return inserted rows."""
        selected_symbols = symbols or self._settings.symbols
        selected_timeframes = timeframes or self._settings.timeframes
        total_inserted = 0

        for symbol in selected_symbols:
            for timeframe in selected_timeframes:
                latest_timestamp = self._repository.get_latest_timestamp(symbol, timeframe)
                since = latest_timestamp + timedelta(milliseconds=1) if latest_timestamp else None
                candles = self._collector.fetch_ohlcv(
                    symbol=symbol,
                    timeframe=timeframe,
                    since=since,
                    limit=self._settings.candles_limit,
                )
                inserted = self._repository.insert_many(candles)
                total_inserted += inserted
                self._logger.info(
                    "Saved %s new candles: symbol=%s timeframe=%s",
                    inserted,
                    symbol,
                    timeframe,
                )

        self._logger.info("Market data update completed: total_inserted=%s", total_inserted)
        return total_inserted
