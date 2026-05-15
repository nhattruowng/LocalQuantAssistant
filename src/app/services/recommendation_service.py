"""Application service for trading setup recommendations."""

from __future__ import annotations

from domain.entities import MarketSnapshot, SetupRecommendation
from domain.enums import TradingAction
from domain.repositories import SetupRecommendationWriter


class RecommendationService:
    """Coordinates setup evaluation and recommendation persistence."""

    def __init__(self, repository: SetupRecommendationWriter) -> None:
        self._repository = repository

    def recommend(self, snapshot: MarketSnapshot) -> SetupRecommendation:
        """Return a conservative setup recommendation for a market snapshot."""
        recommendation = SetupRecommendation(
            symbol=snapshot.symbol,
            action=TradingAction.WAIT,
            confidence=0.0,
            rationale="No trained model or strategy signal is configured yet.",
        )
        self._repository.save(recommendation)
        return recommendation
