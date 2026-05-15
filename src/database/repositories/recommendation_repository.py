"""Repository for setup recommendations."""

from __future__ import annotations

from database.connection import Database
from domain.entities import SetupRecommendation


class RecommendationRepository:
    """Persists recommendation records."""

    def __init__(self, database: Database) -> None:
        self._database = database

    def save(self, recommendation: SetupRecommendation) -> None:
        """Persist a recommendation."""
        self._database.execute(
            """
            INSERT INTO setup_recommendations (
                symbol,
                action,
                confidence,
                rationale,
                created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                recommendation.symbol,
                recommendation.action.value,
                recommendation.confidence,
                recommendation.rationale,
                recommendation.created_at.isoformat(),
            ),
        )
