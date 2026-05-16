"""Tests for model explainability fallback behavior."""

from __future__ import annotations

import pandas as pd

from ml.explainability import ExplainabilityService


class ImportanceModel:
    """Small sklearn-like model exposing feature importances."""

    classes_ = ["BUY", "SELL", "WAIT"]
    feature_importances_ = [0.10, 0.30, 0.20]

    def predict_proba(self, values: pd.DataFrame):
        """Return deterministic probabilities."""
        return [[0.70, 0.20, 0.10] for _ in range(len(values))]


class NoImportanceModel:
    """Model without SHAP-compatible structure or feature importance."""

    classes_ = ["BUY", "SELL", "WAIT"]


def test_explainability_service_uses_feature_importance_fallback():
    service = ExplainabilityService(max_factors=3)

    result = service.explain(
        model=ImportanceModel(),
        feature_row={"ema_20_slope": 1.0, "volume_ratio": 2.0, "rsi_14": -1.0},
        feature_columns=["ema_20_slope", "volume_ratio", "rsi_14"],
        target_label="BUY",
    )

    assert result.method == "feature_importance_fallback"
    assert result.top_positive_factors[0].feature == "volume_ratio"
    assert result.top_negative_factors[0].feature == "rsi_14"
    assert "BUY" in result.summary


def test_explainability_service_returns_unavailable_without_importance():
    service = ExplainabilityService()

    result = service.explain(
        model=NoImportanceModel(),
        feature_row={"ema_20_slope": 1.0},
        feature_columns=["ema_20_slope"],
        target_label="WAIT",
    )

    assert result.method == "unavailable"
    assert result.top_positive_factors == []
    assert result.top_negative_factors == []
