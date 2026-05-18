"""Strategy contracts."""

from __future__ import annotations

from abc import ABC, abstractmethod

from config.settings import SignalSettings
from signals.models import SignalContext, SignalType, StrategyDecision, StrategyType


class Strategy(ABC):
    """Base interface for deterministic setup strategies."""

    strategy_type = StrategyType.NONE

    def __init__(self, settings: SignalSettings) -> None:
        self.settings = settings

    @abstractmethod
    def evaluate(self, context: SignalContext) -> StrategyDecision:
        """Evaluate context and return a candidate strategy decision."""

    def wait(self, reason: str) -> StrategyDecision:
        """Return a WAIT decision from a strategy."""
        return StrategyDecision(
            signal=SignalType.WAIT,
            strategy=self.strategy_type,
            model_probability=0.0,
            trend_score=0.0,
            indicator_score=0.0,
            volume_score=0.0,
            reasons=[reason],
            failed_conditions=[reason],
        )
