"""Probability calibration wrapper for sklearn-like classifiers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV

from ml.calibration.calibration_metrics import calibration_report


@dataclass
class CalibrationResult:
    """Result of fitting a probability calibrator."""

    model: "CalibratedProbabilityModel"
    report: dict[str, Any]


class CalibratedProbabilityModel:
    """Pickle-friendly wrapper exposing raw and calibrated probabilities."""

    def __init__(
        self,
        base_model: Any,
        calibrator: Any | None = None,
        method: str = "none",
        classes: Sequence[str] | None = None,
    ) -> None:
        self.base_model = base_model
        self.calibrator = calibrator
        self.calibration_method = method
        self.classes_ = list(classes or getattr(base_model, "classes_", ["BUY", "SELL", "WAIT"]))

    @property
    def feature_importances_(self) -> Any:
        """Expose base model feature importances when available."""
        return getattr(self.base_model, "feature_importances_", None)

    @property
    def is_calibrated(self) -> bool:
        """Return True when a fitted calibrator is available."""
        return self.calibrator is not None and self.calibration_method != "none"

    def predict(self, x_values: pd.DataFrame) -> pd.Series:
        """Predict labels from the selected probability source."""
        probabilities = self.predict_proba(x_values)
        labels = [self.classes_[int(index)] for index in probabilities.argmax(axis=1)]
        return pd.Series(labels, index=x_values.index)

    def predict_proba(self, x_values: pd.DataFrame) -> np.ndarray:
        """Return calibrated probabilities when available, otherwise raw probabilities."""
        if self.is_calibrated:
            return self.calibrated_predict_proba(x_values)
        return self.raw_predict_proba(x_values)

    def raw_predict_proba(self, x_values: pd.DataFrame) -> np.ndarray:
        """Return base-model probabilities aligned to wrapper class order."""
        probabilities = np.asarray(self.base_model.predict_proba(x_values), dtype=float)
        return _align_probability_columns(
            probabilities,
            source_classes=getattr(self.base_model, "classes_", self.classes_),
            target_classes=self.classes_,
        )

    def calibrated_predict_proba(self, x_values: pd.DataFrame) -> np.ndarray:
        """Return calibrated probabilities aligned to wrapper class order."""
        if self.calibrator is None:
            return self.raw_predict_proba(x_values)
        probabilities = np.asarray(self.calibrator.predict_proba(x_values), dtype=float)
        return _align_probability_columns(
            probabilities,
            source_classes=getattr(self.calibrator, "classes_", self.classes_),
            target_classes=self.classes_,
        )


class ProbabilityCalibrator:
    """Fits Platt scaling or isotonic calibration on a validation set."""

    def calibrate(
        self,
        base_model: Any,
        x_validation: pd.DataFrame,
        y_validation: pd.Series,
        method: str,
        cv: str | int = "prefit",
    ) -> CalibrationResult:
        """Return a calibrated model wrapper and before/after metrics."""
        normalized_method = method.lower()
        classes = [str(label) for label in getattr(base_model, "classes_", ["BUY", "SELL", "WAIT"])]
        raw_probabilities = _align_probability_columns(
            np.asarray(base_model.predict_proba(x_validation), dtype=float),
            source_classes=getattr(base_model, "classes_", classes),
            target_classes=classes,
        )
        before = calibration_report(y_validation, classes, raw_probabilities)
        if normalized_method == "none":
            model = CalibratedProbabilityModel(
                base_model=base_model,
                calibrator=None,
                method="none",
                classes=classes,
            )
            return CalibrationResult(
                model=model,
                report=_combined_report(False, "none", classes, before, before),
            )

        calibrator = _build_calibrated_classifier(
            base_model=base_model,
            method=normalized_method,
            cv=cv,
        )
        calibrator.fit(x_validation, y_validation)
        model = CalibratedProbabilityModel(
            base_model=base_model,
            calibrator=calibrator,
            method=normalized_method,
            classes=classes,
        )
        calibrated_probabilities = model.calibrated_predict_proba(x_validation)
        after = calibration_report(y_validation, classes, calibrated_probabilities)
        return CalibrationResult(
            model=model,
            report=_combined_report(True, normalized_method, classes, before, after),
        )


def probability_payload(
    model: Any,
    x_values: pd.DataFrame,
    use_calibrated: bool,
) -> dict[str, Any]:
    """Return raw/calibrated probabilities and the selected source for one row."""
    if hasattr(model, "raw_predict_proba"):
        raw_array = model.raw_predict_proba(x_values)
    else:
        raw_array = np.asarray(model.predict_proba(x_values), dtype=float)
    classes = [str(label) for label in getattr(model, "classes_", ["BUY", "SELL", "WAIT"])]
    raw = _probability_dict(classes, raw_array[0])

    calibrated: dict[str, float] | None = None
    if use_calibrated and getattr(model, "is_calibrated", False):
        calibrated_array = model.calibrated_predict_proba(x_values)
        calibrated = _probability_dict(classes, calibrated_array[0])
        source = "calibrated"
        selected = calibrated
    else:
        source = "raw"
        selected = raw

    return {
        "probabilities": selected,
        "raw_probabilities": raw,
        "calibrated_probabilities": calibrated,
        "probability_source": source,
    }


def _build_calibrated_classifier(
    base_model: Any,
    method: str,
    cv: str | int,
) -> CalibratedClassifierCV:
    """Create CalibratedClassifierCV across sklearn versions."""
    if method not in {"sigmoid", "isotonic"}:
        raise ValueError("Calibration method must be none, sigmoid, or isotonic.")
    if cv == "prefit":
        try:
            from sklearn.frozen import FrozenEstimator

            return CalibratedClassifierCV(
                estimator=FrozenEstimator(base_model),
                method=method,
            )
        except ModuleNotFoundError:  # pragma: no cover - older sklearn compatibility
            pass
    try:
        return CalibratedClassifierCV(estimator=base_model, method=method, cv=cv)
    except TypeError:  # pragma: no cover - older sklearn compatibility
        return CalibratedClassifierCV(base_estimator=base_model, method=method, cv=cv)


def _combined_report(
    enabled: bool,
    method: str,
    classes: Sequence[str],
    before: dict[str, Any],
    after: dict[str, Any],
) -> dict[str, Any]:
    """Build model metadata for calibration diagnostics."""
    return {
        "calibration_enabled": enabled,
        "calibration_method": method,
        "enabled": enabled,
        "method": method,
        "classes": list(classes),
        "before": before,
        "after": after,
        "brier_score_before": before["brier_score"],
        "brier_score_after": after["brier_score"],
        "log_loss_before": before["log_loss"],
        "log_loss_after": after["log_loss"],
    }


def _align_probability_columns(
    probabilities: np.ndarray,
    source_classes: Sequence[Any],
    target_classes: Sequence[str],
) -> np.ndarray:
    """Align probability columns from source class order to target class order."""
    source_labels = [str(label) for label in source_classes]
    target_labels = [str(label) for label in target_classes]
    aligned = np.zeros((probabilities.shape[0], len(target_labels)), dtype=float)
    for target_index, label in enumerate(target_labels):
        if label in source_labels:
            aligned[:, target_index] = probabilities[:, source_labels.index(label)]
    row_sums = aligned.sum(axis=1, keepdims=True)
    with np.errstate(divide="ignore", invalid="ignore"):
        normalized = np.divide(
            aligned,
            row_sums,
            out=np.zeros_like(aligned),
            where=row_sums > 0,
        )
    empty_rows = row_sums.ravel() <= 0
    if empty_rows.any():
        normalized[empty_rows] = 1.0 / max(len(target_labels), 1)
    return normalized


def _probability_dict(classes: Sequence[str], probabilities: np.ndarray) -> dict[str, float]:
    """Convert a probability row into a class-keyed dictionary."""
    return {str(label): float(value) for label, value in zip(classes, probabilities)}
