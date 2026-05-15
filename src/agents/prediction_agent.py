"""Prediction agent for model probabilities."""

from __future__ import annotations

from pathlib import Path
import pickle
from typing import Any

from agents.base import AgentError, BaseAgent
from agents.context import AgentContext
from domain.enums import MarketRegime, TradingAction


class PredictionAgent(BaseAgent):
    """Loads a model and returns BUY/SELL/WAIT probabilities."""

    name = "PredictionAgent"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._model: Any | None = None
        self._model_loaded = False

    def run(self, context: AgentContext) -> AgentContext:
        """Generate model probabilities from features."""
        self.log_start(context)
        if not context.features:
            raise AgentError("Features are required before prediction.")

        model = self._load_model()
        if model is None:
            context.probabilities = self._fallback_probabilities(context)
            context.add_reason("No local model configured; fallback probabilities were used.")
        else:
            context.probabilities = self._predict_with_model(model, context.features)
            context.add_reason("Model probabilities were generated from predict_proba.")

        self._validate_probabilities(context.probabilities)
        self.log_finish(context)
        return context

    def _load_model(self) -> Any | None:
        """Load a pickled local model once if a path is configured."""
        if self._model_loaded:
            return self._model

        self._model_loaded = True
        model_path = self.settings.model.path
        if model_path is None:
            return None

        path = Path(model_path)
        if not path.exists():
            raise AgentError(f"Configured model file does not exist: {path}.")

        with path.open("rb") as file:
            self._model = pickle.load(file)
        if not hasattr(self._model, "predict_proba"):
            raise AgentError("Configured model must expose predict_proba.")
        return self._model

    def _predict_with_model(
        self,
        model: Any,
        features: dict[str, float],
    ) -> dict[TradingAction, float]:
        """Call predict_proba and normalize class labels."""
        feature_names = sorted(features)
        feature_vector = [[features[name] for name in feature_names]]
        probabilities = model.predict_proba(feature_vector)[0]
        classes = getattr(model, "classes_", [action.value for action in TradingAction])

        result = {action: 0.0 for action in TradingAction}
        for label, probability in zip(classes, probabilities):
            result[TradingAction(str(label))] = float(probability)
        return result

    def _fallback_probabilities(
        self,
        context: AgentContext,
    ) -> dict[TradingAction, float]:
        """Return deterministic probabilities before a real model exists."""
        action_probability = self.settings.model.fallback_action_probability
        wait_probability = self.settings.model.fallback_wait_probability
        opposite_probability = self.settings.model.fallback_opposite_probability
        regime = context.regime

        if regime in {MarketRegime.UPTREND, MarketRegime.BREAKOUT_UP}:
            return self._normalize(
                {
                    TradingAction.BUY: action_probability,
                    TradingAction.SELL: opposite_probability,
                    TradingAction.WAIT: wait_probability,
                }
            )
        if regime in {MarketRegime.DOWNTREND, MarketRegime.BREAKOUT_DOWN}:
            return self._normalize(
                {
                    TradingAction.BUY: opposite_probability,
                    TradingAction.SELL: action_probability,
                    TradingAction.WAIT: wait_probability,
                }
            )
        return self._normalize(
            {
                TradingAction.BUY: opposite_probability,
                TradingAction.SELL: opposite_probability,
                TradingAction.WAIT: action_probability,
            }
        )

    def _normalize(
        self,
        probabilities: dict[TradingAction, float],
    ) -> dict[TradingAction, float]:
        """Normalize probabilities so they sum to one."""
        total = sum(probabilities.values())
        if total <= 0:
            raise AgentError("Probability total must be positive.")
        return {action: value / total for action, value in probabilities.items()}

    def _validate_probabilities(
        self,
        probabilities: dict[TradingAction, float],
    ) -> None:
        """Validate probability keys and values."""
        missing = set(TradingAction) - set(probabilities)
        if missing:
            raise AgentError(f"Missing probabilities for actions: {missing}.")
        if any(value < 0.0 or value > 1.0 for value in probabilities.values()):
            raise AgentError("Probabilities must be within [0, 1].")
