"""SQLite repository for OHLCV candles."""

from __future__ import annotations

from datetime import UTC, datetime
import sqlite3

from database.connection import Database
from domain.entities import Candle


class CandleRepository:
    """Persists and reads deduplicated OHLCV candles."""

    def __init__(self, database: Database) -> None:
        self._database = database

    def insert_many(self, candles: list[Candle]) -> int:
        """Insert candles and return the number of newly stored rows."""
        inserted = 0
        for candle in candles:
            cursor = self._database.execute(
                """
                INSERT OR IGNORE INTO candles (
                    symbol,
                    timeframe,
                    timestamp,
                    open,
                    high,
                    low,
                    close,
                    volume
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    candle.symbol,
                    candle.timeframe,
                    candle.timestamp.isoformat(),
                    candle.open,
                    candle.high,
                    candle.low,
                    candle.close,
                    candle.volume,
                ),
            )
            inserted += cursor.rowcount
        return inserted

    def get_latest_timestamp(
        self,
        symbol: str,
        timeframe: str,
    ) -> datetime | None:
        """Return the newest stored candle timestamp for a symbol/timeframe."""
        row = self._database.execute(
            """
            SELECT timestamp
            FROM candles
            WHERE symbol = ? AND timeframe = ?
            ORDER BY timestamp DESC
            LIMIT 1
            """,
            (symbol, timeframe),
        ).fetchone()
        if row is None:
            return None
        return _parse_datetime(row["timestamp"])

    def list_candles(
        self,
        symbol: str,
        timeframe: str,
        limit: int | None = None,
    ) -> list[Candle]:
        """Read candles ordered by timestamp ascending."""
        query = """
            SELECT symbol, timeframe, timestamp, open, high, low, close, volume
            FROM candles
            WHERE symbol = ? AND timeframe = ?
            ORDER BY timestamp ASC
        """
        parameters: tuple[object, ...] = (symbol, timeframe)
        if limit is not None:
            query += " LIMIT ?"
            parameters = (symbol, timeframe, limit)

        rows = self._database.execute(query, parameters).fetchall()
        return [_row_to_candle(row) for row in rows]


def _row_to_candle(row: sqlite3.Row) -> Candle:
    """Convert a SQLite row into a Candle."""
    return Candle(
        symbol=row["symbol"],
        timeframe=row["timeframe"],
        timestamp=_parse_datetime(row["timestamp"]),
        open=float(row["open"]),
        high=float(row["high"]),
        low=float(row["low"]),
        close=float(row["close"]),
        volume=float(row["volume"]),
    )


def _parse_datetime(value: str) -> datetime:
    """Parse ISO datetime values from SQLite."""
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed
