"""Tests for recommendation service."""

from __future__ import annotations

from app.services.recommendation_service import RecommendationService
from domain.entities import MarketSnapshot, SetupRecommendation
from domain.enums import TradingAction


class InMemoryRecommendationRepository:
    """Simple in-memory repository for service tests."""

    def __init__(self) -> None:
        self.saved: list[SetupRecommendation] = []

    def save(self, recommendation: SetupRecommendation) -> None:
        self.saved.append(recommendation)


def test_recommendation_service_defaults_to_wait():
    repository = InMemoryRecommendationRepository()
    service = RecommendationService(repository)

    recommendation = service.recommend(MarketSnapshot(symbol="ETHUSDT", close_price=3200.0))

    assert recommendation.action is TradingAction.WAIT
    assert repository.saved == [recommendation]
