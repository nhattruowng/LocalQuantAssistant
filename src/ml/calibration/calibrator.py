"""Strict probability calibration facade for model research and registry metadata."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence

import numpy as np
import pandas as pd

from ml.calibration.probability_calibrator import (
    CalibratedProbabilityModel,
    ProbabilityCalibrator,
)


@dataclass(frozen=True)
class CalibratorConfig:
    """Configuration for probability calibration."""

    method: str = "sigmoid"
    cv: str | int = "prefit"
    isotonic_min_samples: int = 100
    reliability_bins: int = 10


@dataclass(frozen=True)
class CalibratorResult:
    """Fit result and diagnostics for a calibrator."""

    method_requested: str
    method_used: str
    classes: list[str]
    metrics: dict[str, Any] = field(default_factory=dict)

    @property
    def calibration_metrics(self) -> dict[str, Any]:
        return dict(self.metrics)


class Calibrator:
    """Fit Platt/sigmoid or isotonic calibration and expose calibrated probabilities."""

    def __init__(
        self,
        method: str = "sigmoid",
        cv: str | int = "prefit",
        isotonic_min_samples: int = 100,
        reliability_bins: int = 10,
    ) -> None:
        self._config = CalibratorConfig(
            method=method,
            cv=cv,
            isotonic_min_samples=int(isotonic_min_samples),
            reliability_bins=int(reliability_bins),
        )
        self._model: CalibratedProbabilityModel | None = None
        self._result: CalibratorResult | None = None

    @property
    def classes_(self) -> list[str]:
        if self._model is None:
            return []
        return list(self._model.classes_)

    @property
    def metrics(self) -> dict[str, Any]:
        if self._result is None:
            return {}
        return self._result.calibration_metrics

    @property
    def result(self) -> CalibratorResult:
        if self._result is None:
            raise ValueError("Calibrator has not been fitted.")
        return self._result

    @property
    def model(self) -> CalibratedProbabilityModel:
        if self._model is None:
            raise ValueError("Calibrator has not been fitted.")
        return self._model

    def fit(
        self,
        base_model: Any,
        x_validation: pd.DataFrame,
        y_validation: pd.Series | Sequence[str],
    ) -> "Calibrator":
        """Fit calibration on validation data only."""
        method_requested = _normalize_method(self._config.method)
        method_used = self._resolve_method(method_requested, len(x_validation))
        y_values = pd.Series(y_validation).astype(str).reset_index(drop=True)
        calibration = ProbabilityCalibrator().calibrate(
            base_model=base_model,
            x_validation=x_validation,
            y_validation=y_values,
            method=method_used,
            cv=self._config.cv,
        )
        metrics = dict(calibration.report)
        metrics["method_requested"] = method_requested
        metrics["method_used"] = method_used
        metrics["isotonic_min_samples"] = self._config.isotonic_min_samples
        metrics["reliability_bins"] = self._config.reliability_bins
        self._model = calibration.model
        self._result = CalibratorResult(
            method_requested=method_requested,
            method_used=method_used,
            classes=list(calibration.model.classes_),
            metrics=metrics,
        )
        return self

    def predict_proba(self, x_values: pd.DataFrame) -> np.ndarray:
        """Return calibrated probabilities after fit."""
        return self.model.predict_proba(x_values)

    def predict(self, x_values: pd.DataFrame) -> pd.Series:
        """Return class labels from calibrated probabilities."""
        return self.model.predict(x_values)

    def _resolve_method(self, method: str, sample_count: int) -> str:
        if method == "isotonic" and sample_count < self._config.isotonic_min_samples:
            return "sigmoid"
        return method


def _normalize_method(method: str) -> str:
    normalized = str(method).strip().lower()
    if normalized == "platt":
        return "sigmoid"
    if normalized not in {"none", "sigmoid", "isotonic"}:
        raise ValueError("Calibration method must be none, sigmoid/platt, or isotonic.")
    return normalized
