"""Strategy contracts."""

from __future__ import annotations

from typing import Protocol

from domain.entities import MarketSnapshot, SetupRecommendation


class TradingSetupStrategy(Protocol):
    """Contract for a strategy that evaluates a market snapshot."""

    def evaluate(self, snapshot: MarketSnapshot) -> SetupRecommendation:
        """Evaluate a snapshot and return a recommendation."""
