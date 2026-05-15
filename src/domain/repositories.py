"""Domain repository contracts."""

from __future__ import annotations

from typing import Protocol

from domain.entities import SetupRecommendation


class SetupRecommendationWriter(Protocol):
    """Contract for persisting setup recommendations."""

    def save(self, recommendation: SetupRecommendation) -> None:
        """Persist a setup recommendation."""
