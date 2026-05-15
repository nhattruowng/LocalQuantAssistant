"""Market data source contracts."""

from __future__ import annotations

from typing import Protocol

from domain.entities import MarketSnapshot


class MarketDataSource(Protocol):
    """Contract for exchange, file, or API market data sources."""

    def latest_snapshot(self, symbol: str) -> MarketSnapshot:
        """Return the latest market snapshot for a symbol."""
