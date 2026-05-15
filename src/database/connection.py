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
        return self._connection

    def initialize(self) -> None:
        """Create local tables if they do not exist."""
        self.execute(
            """
            CREATE TABLE IF NOT EXISTS setup_recommendations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                action TEXT NOT NULL,
                confidence REAL NOT NULL,
                rationale TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )

    def execute(self, query: str, parameters: tuple[Any, ...] = ()) -> sqlite3.Cursor:
        """Execute a SQLite statement and commit it."""
        cursor = self.connection.execute(query, parameters)
        self.connection.commit()
        return cursor

    def close(self) -> None:
        """Close the SQLite connection."""
        if self._connection is not None:
            self._connection.close()
            self._connection = None


def create_database(settings: DatabaseSettings) -> Database:
    """Create a database implementation from settings."""
    if settings.driver == "sqlite":
        return SQLiteDatabase(settings.path)
    if settings.driver == "postgresql":
        raise NotImplementedError("PostgreSQL support can be added via Database protocol.")
    raise ValueError(f"Unsupported database driver: {settings.driver}")
