"""Model prediction contracts."""

from __future__ import annotations

from typing import Mapping, Protocol

from domain.enums import TradingAction


class SetupPredictor(Protocol):
    """Contract for model-backed setup predictors."""

    def predict(self, features: Mapping[str, float]) -> tuple[TradingAction, float]:
        """Return an action and confidence score."""


class WaitPredictor:
    """Safe default predictor used before a trained model is configured."""

    def predict(self, features: Mapping[str, float]) -> tuple[TradingAction, float]:
        """Return WAIT with zero confidence."""
        return TradingAction.WAIT, 0.0
