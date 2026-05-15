"""Tests for candle repository persistence."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from config.settings import DatabaseSettings
from database.candle_repository import CandleRepository
from database.connection import create_database
from domain.entities import Candle


def test_candle_repository_insert_many_deduplicates_unique_key(tmp_path):
    database = create_database(DatabaseSettings(driver="sqlite", path=tmp_path / "app.db"))
    database.initialize()
    repository = CandleRepository(database)
    candle = _candle(datetime(2026, 1, 1, tzinfo=UTC))

    first_inserted = repository.insert_many([candle])
    second_inserted = repository.insert_many([candle])
    candles = repository.list_candles("BTC/USDT", "1h")
    database.close()

    assert first_inserted == 1
    assert second_inserted == 0
    assert len(candles) == 1
    assert candles[0] == candle


def test_candle_repository_returns_latest_timestamp(tmp_path):
    database = create_database(DatabaseSettings(driver="sqlite", path=tmp_path / "app.db"))
    database.initialize()
    repository = CandleRepository(database)
    first_timestamp = datetime(2026, 1, 1, tzinfo=UTC)
    second_timestamp = first_timestamp + timedelta(hours=1)

    repository.insert_many([_candle(first_timestamp), _candle(second_timestamp)])
    latest = repository.get_latest_timestamp("BTC/USDT", "1h")
    database.close()

    assert latest == second_timestamp


def _candle(timestamp: datetime) -> Candle:
    """Build a test candle for repository tests."""
    return Candle(
        symbol="BTC/USDT",
        timeframe="1h",
        timestamp=timestamp,
        open=100.0,
        high=110.0,
        low=95.0,
        close=105.0,
        volume=10.0,
    )
