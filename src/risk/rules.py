"""Risk rule primitives."""

from __future__ import annotations

from domain.entities import SetupRecommendation
from domain.enums import TradingAction


def allow_recommendation(recommendation: SetupRecommendation) -> bool:
    """Reject actionable recommendations with invalid confidence."""
    if recommendation.action is TradingAction.WAIT:
        return True
    return 0.0 < recommendation.confidence <= 1.0
