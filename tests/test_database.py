"""Tests for SQLite persistence."""

from __future__ import annotations

from config.settings import DatabaseSettings
from database.connection import create_database
from database.repositories.recommendation_repository import RecommendationRepository
from domain.entities import SetupRecommendation
from domain.enums import TradingAction


def test_recommendation_repository_saves_record(tmp_path):
    database = create_database(DatabaseSettings(driver="sqlite", path=tmp_path / "app.db"))
    database.initialize()
    repository = RecommendationRepository(database)

    repository.save(
        SetupRecommendation(
            symbol="BTCUSDT",
            action=TradingAction.WAIT,
            confidence=0.0,
            rationale="test",
        )
    )

    row = database.execute("SELECT symbol, action FROM setup_recommendations").fetchone()
    database.close()

    assert row["symbol"] == "BTCUSDT"
    assert row["action"] == "WAIT"
