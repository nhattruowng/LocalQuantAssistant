"""Database connection factory and SQLite implementation."""

from __future__ import annotations

from pathlib import Path
import sqlite3
from typing import Any, Protocol

from config.settings import DatabaseSettings


class Database(Protocol):
    """Minimal database contract used by repositories."""

    def initialize(self) -> None:
        """Prepare required database tables."""

    def execute(self, query: str, parameters: tuple[Any, ...] = ()) -> sqlite3.Cursor:
        """Execute a statement and commit it."""

    def execute_many(
        self,
        query: str,
        parameters: list[tuple[Any, ...]],
    ) -> sqlite3.Cursor:
        """Execute one statement for many parameter sets and commit it."""

    def close(self) -> None:
        """Close the database connection."""


class SQLiteDatabase:
    """SQLite-backed local database connection."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._connection: sqlite3.Connection | None = None

    @property
    def connection(self) -> sqlite3.Connection:
        """Return an open SQLite connection."""
        if self._connection is None:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._connection = sqlite3.connect(self._path)
            self._connection.row_factory = sqlite3.Row
            self._connection.execute("PRAGMA journal_mode=WAL")
            self._connection.execute("PRAGMA synchronous=NORMAL")
        return self._connection

    def initialize(self) -> None:
        """Create local tables if they do not exist."""
        schema_path = Path(__file__).resolve().parent / "schema.sql"
        self.connection.executescript(schema_path.read_text(encoding="utf-8"))
        self._apply_migrations()
        self.connection.commit()

    def execute(self, query: str, parameters: tuple[Any, ...] = ()) -> sqlite3.Cursor:
        """Execute a SQLite statement and commit it."""
        cursor = self.connection.execute(query, parameters)
        self.connection.commit()
        return cursor

    def execute_many(
        self,
        query: str,
        parameters: list[tuple[Any, ...]],
    ) -> sqlite3.Cursor:
        """Execute a SQLite statement for many rows in one transaction."""
        cursor = self.connection.executemany(query, parameters)
        self.connection.commit()
        return cursor

    def close(self) -> None:
        """Close the SQLite connection."""
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def _apply_migrations(self) -> None:
        """Apply lightweight SQLite migrations for existing local databases."""
        _add_column_if_missing(
            self.connection,
            table="paper_trades",
            column="market_regime",
            definition="TEXT DEFAULT 'UNKNOWN'",
        )


def create_database(settings: DatabaseSettings) -> Database:
    """Create a database implementation from settings."""
    if settings.driver == "sqlite":
        return SQLiteDatabase(settings.path)
    if settings.driver == "postgresql":
        raise NotImplementedError("PostgreSQL support can be added via Database protocol.")
    raise ValueError(f"Unsupported database driver: {settings.driver}")


def _add_column_if_missing(
    connection: sqlite3.Connection,
    table: str,
    column: str,
    definition: str,
) -> None:
    """Add a SQLite column when an existing table lacks it."""
    columns = {row["name"] for row in connection.execute(f"PRAGMA table_info({table})")}
    if column not in columns:
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
