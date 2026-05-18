"""Model selection and probability prediction service."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import pandas as pd

from config.settings import Settings
from ml.calibration.probability_calibrator import probability_payload
from ml.model_registry import GLOBAL_SCOPE, ModelRegistry


@dataclass(frozen=True)
class PredictionResult:
    """Probability prediction plus model selection metadata."""

    probabilities: dict[str, float]
    raw_probabilities: dict[str, float]
    calibrated_probabilities: dict[str, float] | None
    probability_source: str
    model_scope_used: str
    model_version: str | None
    fallback_reason: str | None
    metadata: dict[str, Any]


class PredictionService:
    """Selects regime-specific models with global fallback."""

    def __init__(
        self,
        settings: Settings,
        registry: ModelRegistry | None = None,
    ) -> None:
        self._settings = settings
        self._registry = registry or ModelRegistry(settings.training.model_dir)

    def predict_row(
        self,
        symbol: str,
        timeframe: str,
        row: pd.Series,
    ) -> PredictionResult:
        """Predict probabilities for one feature row."""
        regime = str(row.get("market_regime", "") or "")
        metadata, fallback_reason = self._registry.resolve_for_prediction(
            symbol=symbol,
            timeframe=timeframe,
            regime=regime,
            min_validation_accuracy=(
                self._settings.training.regime_specific.min_validation_accuracy
            ),
        )
        if metadata is None:
            raise ValueError("No registered model found for prediction.")

        feature_columns = list(metadata.get("feature_columns", []))
        if not feature_columns:
            raise ValueError("Model metadata must provide feature_columns.")
        model = joblib.load(Path(str(metadata["model_path"])))
        x_values = pd.DataFrame([row]).loc[:, feature_columns]
        payload = probability_payload(
            model,
            x_values,
            use_calibrated=self._settings.signal.use_calibrated_probability,
        )
        return PredictionResult(
            probabilities=dict(payload["probabilities"]),
            raw_probabilities=dict(payload["raw_probabilities"]),
            calibrated_probabilities=(
                dict(payload["calibrated_probabilities"])
                if payload["calibrated_probabilities"] is not None
                else None
            ),
            probability_source=str(payload["probability_source"]),
            model_scope_used=str(metadata.get("model_scope", GLOBAL_SCOPE)),
            model_version=(
                str(metadata.get("model_version"))
                if metadata.get("model_version") is not None
                else None
            ),
            fallback_reason=fallback_reason,
            metadata=metadata,
        )
