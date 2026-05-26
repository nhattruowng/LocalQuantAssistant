"""Tests for strict calibration facade and financial model registry."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

sklearn = pytest.importorskip("sklearn")
from sklearn.ensemble import RandomForestClassifier  # noqa: E402

from ml.calibration.calibrator import Calibrator  # noqa: E402
from ml.registry.model_registry import (  # noqa: E402
    ModelRegistry,
    ModelStatus,
    PromotionCriteria,
)


class DummyProbabilityModel:
    """Tiny pickle-friendly model for registry tests."""

    classes_ = ["BUY", "SELL", "WAIT"]

    def predict_proba(self, rows: pd.DataFrame):
        return [[0.7, 0.1, 0.2] for _ in range(len(rows))]


def test_calibrator_fit_predict_proba_sigmoid() -> None:
    model, x_values, y_values = _trained_model()

    calibrator = Calibrator(method="platt", cv="prefit").fit(
        model,
        x_values,
        y_values,
    )
    probabilities = calibrator.predict_proba(x_values.head(6))

    assert calibrator.result.method_requested == "sigmoid"
    assert calibrator.result.method_used == "sigmoid"
    assert probabilities.shape == (6, len(model.classes_))
    assert np.allclose(probabilities.sum(axis=1), 1.0)
    assert "brier_score_after" in calibrator.metrics
    assert "log_loss_after" in calibrator.metrics
    assert "reliability_curve" in calibrator.metrics["after"]


def test_calibrator_isotonic_falls_back_when_dataset_is_small() -> None:
    model, x_values, y_values = _trained_model()

    calibrator = Calibrator(
        method="isotonic",
        cv="prefit",
        isotonic_min_samples=1_000,
    ).fit(model, x_values, y_values)

    assert calibrator.result.method_requested == "isotonic"
    assert calibrator.result.method_used == "sigmoid"


def test_strict_registry_saves_candidate(tmp_path) -> None:
    registry = ModelRegistry(tmp_path)

    record = registry.save_candidate(
        model=DummyProbabilityModel(),
        symbol="BTC/USDT",
        timeframe="15m",
        feature_set_id="features:v1",
        validation_method="walk_forward",
        metrics=_candidate_metrics(),
        calibration_metrics=_candidate_calibration(),
        known_failure_modes=[],
    )
    metadata = registry.load_metadata(record.model_id)

    assert record.status is ModelStatus.CANDIDATE
    assert record.model_version == "v001"
    assert record.model_path.exists()
    assert metadata["status"] == "candidate"
    assert metadata["feature_set_id"] == "features:v1"
    assert metadata["validation_method"] == "walk_forward"
    assert metadata["calibration_metrics"]["brier_score_after"] == 0.18
    assert metadata["known_failure_modes"] == []


def test_strict_registry_promotes_champion_when_rules_pass(tmp_path) -> None:
    registry = ModelRegistry(tmp_path)
    record = registry.save_candidate(
        model=DummyProbabilityModel(),
        symbol="BTC/USDT",
        timeframe="15m",
        feature_set_id="features:v1",
        validation_method="walk_forward",
        metrics=_candidate_metrics(),
        calibration_metrics=_candidate_calibration(),
    )

    decision = registry.promote_if_eligible(
        record.model_id,
        baseline_metrics=_baseline_metrics(),
        baseline_calibration_metrics=_baseline_calibration(),
        criteria=PromotionCriteria(min_trades=30),
    )
    champion = registry.latest_champion("BTC/USDT", "15m")

    assert decision.promoted is True
    assert decision.reasons == ["promotion_criteria_passed"]
    assert champion is not None
    assert champion["model_id"] == record.model_id
    assert champion["status"] == "champion"


def test_strict_registry_does_not_promote_when_financial_metrics_fail(tmp_path) -> None:
    registry = ModelRegistry(tmp_path)
    record = registry.save_candidate(
        model=DummyProbabilityModel(),
        symbol="BTC/USDT",
        timeframe="15m",
        feature_set_id="features:v1",
        validation_method="walk_forward",
        metrics={
            "walk_forward": {
                "accuracy": 0.99,
                "net_profit": 8.0,
                "max_drawdown": 6.0,
                "total_trades": 12,
            }
        },
        calibration_metrics={"brier_score_after": 0.25, "log_loss_after": 0.9},
    )

    decision = registry.promote_if_eligible(
        record.model_id,
        baseline_metrics=_baseline_metrics(),
        baseline_calibration_metrics=_baseline_calibration(),
        criteria=PromotionCriteria(min_trades=30),
    )
    metadata = registry.load_metadata(record.model_id)

    assert decision.promoted is False
    assert "walk_forward_profit_not_better_than_baseline" in decision.reasons
    assert "drawdown_worse_than_baseline" in decision.reasons
    assert "insufficient_trade_count" in decision.reasons
    assert "calibration_worse_than_baseline" in decision.reasons
    assert metadata["status"] == "candidate"


def test_strict_registry_rejects_accuracy_only_promotion(tmp_path) -> None:
    registry = ModelRegistry(tmp_path)
    record = registry.save_candidate(
        model=DummyProbabilityModel(),
        symbol="ETH/USDT",
        timeframe="1h",
        feature_set_id="features:v2",
        validation_method="walk_forward",
        metrics={
            "walk_forward": {
                "accuracy": 0.95,
                "net_profit": 10.0,
                "max_drawdown": 5.0,
                "total_trades": 50,
            }
        },
        calibration_metrics=_candidate_calibration(),
    )

    decision = registry.promote_if_eligible(
        record.model_id,
        baseline_metrics={
            "walk_forward": {
                "accuracy": 0.60,
                "net_profit": 10.0,
                "max_drawdown": 5.0,
                "total_trades": 50,
            }
        },
        baseline_calibration_metrics=_baseline_calibration(),
    )

    assert decision.promoted is False
    assert decision.reasons == ["walk_forward_profit_not_better_than_baseline"]


def _candidate_metrics() -> dict[str, dict[str, float]]:
    return {
        "walk_forward": {
            "accuracy": 0.66,
            "net_profit": 14.0,
            "max_drawdown": 4.0,
            "total_trades": 60,
        }
    }


def _baseline_metrics() -> dict[str, dict[str, float]]:
    return {
        "walk_forward": {
            "accuracy": 0.64,
            "net_profit": 10.0,
            "max_drawdown": 5.0,
            "total_trades": 60,
        }
    }


def _candidate_calibration() -> dict[str, float]:
    return {"brier_score_after": 0.18, "log_loss_after": 0.72}


def _baseline_calibration() -> dict[str, float]:
    return {"brier_score_after": 0.20, "log_loss_after": 0.78}


def _trained_model() -> tuple[RandomForestClassifier, pd.DataFrame, pd.Series]:
    x_values = pd.DataFrame(
        {
            "a": [0.1, 0.2, 0.9, 1.0, 0.4, 0.5] * 10,
            "b": [1.0, 0.9, 0.2, 0.1, 0.5, 0.4] * 10,
        }
    )
    y_values = pd.Series(["BUY", "BUY", "SELL", "SELL", "WAIT", "WAIT"] * 10)
    model = RandomForestClassifier(n_estimators=20, random_state=11)
    model.fit(x_values, y_values)
    return model, x_values, y_values
