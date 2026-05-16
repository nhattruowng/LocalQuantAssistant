"""Explainable AI helpers for setup predictions."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import logging
import math
from typing import Any, Mapping

import pandas as pd


@dataclass(frozen=True)
class ExplanationFactor:
    """One feature contribution in an explanation result."""

    feature: str
    impact: float


@dataclass(frozen=True)
class ExplainabilityResult:
    """Structured explanation for one prediction."""

    method: str
    top_positive_factors: list[ExplanationFactor]
    top_negative_factors: list[ExplanationFactor]
    summary: str

    @property
    def top_factors(self) -> list[ExplanationFactor]:
        """Return positive factors first for backward-compatible UI display."""
        return self.top_positive_factors

    def to_dict(self) -> dict[str, object]:
        """Serialize explanation into dashboard/API-friendly values."""
        data = asdict(self)
        data["top_factors"] = [asdict(factor) for factor in self.top_factors]
        return data


class ExplainabilityService:
    """Explains model predictions with SHAP or feature-importance fallback."""

    def __init__(
        self,
        max_factors: int = 5,
        logger: logging.Logger | None = None,
    ) -> None:
        self._max_factors = max_factors
        self._logger = logger or logging.getLogger("localquant.ml.explainability")

    def explain(
        self,
        model: Any,
        feature_row: pd.Series | Mapping[str, Any],
        feature_columns: list[str],
        target_label: str | None = None,
    ) -> ExplainabilityResult:
        """Explain one model prediction without requiring SHAP at runtime."""
        row = _feature_frame(feature_row, feature_columns)
        shap_result = self._explain_with_shap(model, row, feature_columns, target_label)
        if shap_result is not None:
            return shap_result
        return self._explain_with_feature_importance(model, row, feature_columns, target_label)

    def _explain_with_shap(
        self,
        model: Any,
        row: pd.DataFrame,
        feature_columns: list[str],
        target_label: str | None,
    ) -> ExplainabilityResult | None:
        """Return a SHAP explanation when the optional dependency works."""
        try:
            import shap  # type: ignore[import-not-found]
        except ModuleNotFoundError:
            return None

        try:
            explainer = shap.TreeExplainer(_unwrap_model(model))
            shap_values = explainer.shap_values(row)
            impacts = _select_shap_impacts(shap_values, model, row, target_label)
            return _build_result(
                method="shap",
                feature_columns=feature_columns,
                impacts=impacts,
                target_label=target_label,
                max_factors=self._max_factors,
            )
        except Exception as error:
            self._logger.warning("SHAP explanation failed; using fallback: %s", error)
            return None

    def _explain_with_feature_importance(
        self,
        model: Any,
        row: pd.DataFrame,
        feature_columns: list[str],
        target_label: str | None,
    ) -> ExplainabilityResult:
        """Return a stable fallback explanation from model feature importance."""
        importances = _feature_importances(model)
        if importances is None:
            return ExplainabilityResult(
                method="unavailable",
                top_positive_factors=[],
                top_negative_factors=[],
                summary="No SHAP package or model feature importance is available for this prediction.",
            )

        values = row.iloc[0].astype(float)
        impacts = [
            _safe_float(importance) * _direction(values[column])
            for column, importance in zip(feature_columns, importances)
        ]
        return _build_result(
            method="feature_importance_fallback",
            feature_columns=feature_columns,
            impacts=impacts,
            target_label=target_label,
            max_factors=self._max_factors,
        )


def _feature_frame(
    feature_row: pd.Series | Mapping[str, Any],
    feature_columns: list[str],
) -> pd.DataFrame:
    """Build a one-row feature frame in model column order."""
    if isinstance(feature_row, pd.Series):
        values = feature_row
    else:
        values = pd.Series(feature_row)
    return pd.DataFrame([{column: values.get(column, 0.0) for column in feature_columns}])


def _unwrap_model(model: Any) -> Any:
    """Return the underlying estimator when a local adapter wraps it."""
    return getattr(model, "_model", model)


def _select_shap_impacts(
    shap_values: Any,
    model: Any,
    row: pd.DataFrame,
    target_label: str | None,
) -> list[float]:
    """Normalize SHAP output shapes into one impact per feature."""
    output_index = _target_index(model, row, target_label)
    if isinstance(shap_values, list):
        values = shap_values[min(output_index, len(shap_values) - 1)]
        return [float(value) for value in values[0]]

    shape = getattr(shap_values, "shape", ())
    if len(shape) == 3:
        values = shap_values[0, :, min(output_index, shape[2] - 1)]
        return [float(value) for value in values]
    if len(shape) == 2:
        return [float(value) for value in shap_values[0]]
    return [float(value) for value in list(shap_values)]


def _target_index(model: Any, row: pd.DataFrame, target_label: str | None) -> int:
    """Resolve target class index for multiclass explanations."""
    classes = [str(label) for label in getattr(model, "classes_", [])]
    if target_label is not None and target_label in classes:
        return classes.index(target_label)
    try:
        probabilities = model.predict_proba(row)[0]
        return int(max(range(len(probabilities)), key=lambda index: probabilities[index]))
    except Exception:
        return 0


def _feature_importances(model: Any) -> list[float] | None:
    """Read feature importance from a model or wrapped estimator."""
    importances = getattr(model, "feature_importances_", None)
    if importances is None:
        importances = getattr(_unwrap_model(model), "feature_importances_", None)
    if importances is None:
        return None
    return [float(value) for value in importances]


def _build_result(
    method: str,
    feature_columns: list[str],
    impacts: list[float],
    target_label: str | None,
    max_factors: int,
) -> ExplainabilityResult:
    """Build a sorted explanation result from raw impacts."""
    pairs = [
        ExplanationFactor(feature=feature, impact=round(float(impact), 6))
        for feature, impact in zip(feature_columns, impacts)
        if math.isfinite(float(impact))
    ]
    positive = sorted(
        [factor for factor in pairs if factor.impact > 0],
        key=lambda factor: abs(factor.impact),
        reverse=True,
    )[:max_factors]
    negative = sorted(
        [factor for factor in pairs if factor.impact < 0],
        key=lambda factor: abs(factor.impact),
        reverse=True,
    )[:max_factors]
    label_text = f" {target_label}" if target_label else ""
    if method == "shap":
        summary = _summary(label_text, positive, negative, "SHAP contributions")
    elif method == "feature_importance_fallback":
        summary = _summary(label_text, positive, negative, "model feature importance fallback")
    else:
        summary = "No explanation is available for this prediction."
    return ExplainabilityResult(
        method=method,
        top_positive_factors=positive,
        top_negative_factors=negative,
        summary=summary,
    )


def _summary(
    label_text: str,
    positive: list[ExplanationFactor],
    negative: list[ExplanationFactor],
    method_text: str,
) -> str:
    """Create a concise human-readable explanation."""
    if not positive and not negative:
        return f"No strong feature contribution was available for the{label_text} signal."
    positive_text = ", ".join(factor.feature for factor in positive[:3]) or "no clear positive factor"
    negative_text = ", ".join(factor.feature for factor in negative[:3])
    if negative_text:
        return (
            f"The{label_text} signal is mainly supported by {positive_text}; "
            f"main opposing factors are {negative_text}. Method: {method_text}."
        )
    return f"The{label_text} signal is mainly supported by {positive_text}. Method: {method_text}."


def _direction(value: float) -> float:
    """Give fallback importance a simple direction from the current feature value."""
    numeric = _safe_float(value)
    if numeric < 0:
        return -1.0
    return 1.0


def _safe_float(value: Any) -> float:
    """Convert values to finite floats for explanation math."""
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(numeric):
        return 0.0
    return numeric
