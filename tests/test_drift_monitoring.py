"""Tests for drift monitoring components."""

from __future__ import annotations

import pytest

from ml.monitoring.drift_detector import FeatureDriftDetector, ks_test, population_stability_index
from ml.monitoring.model_monitor import DriftAction, DriftLevel, ModelMonitor


def test_psi_detects_feature_drift() -> None:
    baseline = [float(index) for index in range(100)]
    recent = [float(index + 120) for index in range(100)]

    psi = population_stability_index(baseline, recent)

    assert psi > 0.25


def test_ks_detects_drift_when_scipy_available() -> None:
    scipy = pytest.importorskip("scipy")
    assert scipy is not None
    stat, pvalue = ks_test(
        [float(index) for index in range(80)],
        [float(index + 80) for index in range(80)],
    )

    assert stat is not None
    assert pvalue is not None
    assert pvalue < 0.05


def test_prediction_distribution_shift_detected() -> None:
    monitor = ModelMonitor()
    baseline_predictions = [
        {"signal": "BUY", "probabilities": {"BUY": 0.8, "SELL": 0.1, "WAIT": 0.1}}
        for _ in range(50)
    ]
    recent_predictions = [
        {"signal": "WAIT", "probabilities": {"BUY": 0.1, "SELL": 0.1, "WAIT": 0.8}}
        for _ in range(50)
    ]

    report = monitor.build_report(
        train_feature_rows=[],
        recent_feature_rows=[],
        baseline_predictions=baseline_predictions,
        recent_predictions=recent_predictions,
    )

    assert report.prediction_shift["distribution_shift"] > 0.0
    assert report.prediction_shift["score"] > 0.0


def test_drift_high_recommends_disable_model() -> None:
    monitor = ModelMonitor()
    train_rows = [{"x": float(index), "y": float(index)} for index in range(100)]
    recent_rows = [{"x": float(index + 500), "y": float(index - 500)} for index in range(100)]
    baseline_predictions = [
        {"signal": "BUY", "probabilities": {"BUY": 0.9, "SELL": 0.05, "WAIT": 0.05}}
        for _ in range(80)
    ]
    recent_predictions = [
        {"signal": "WAIT", "probabilities": {"BUY": 0.05, "SELL": 0.05, "WAIT": 0.9}}
        for _ in range(80)
    ]

    report = monitor.build_report(
        train_feature_rows=train_rows,
        recent_feature_rows=recent_rows,
        baseline_predictions=baseline_predictions,
        recent_predictions=recent_predictions,
        baseline_regime_counts={"UPTREND": 90, "SIDEWAY": 10},
        recent_regime_counts={"UPTREND": 5, "SIDEWAY": 75, "BREAKOUT_UP": 20},
    )

    assert report.drift_level is DriftLevel.HIGH
    assert report.recommended_action is DriftAction.DISABLE_MODEL
    assert report.drift_score >= 0.75


def test_missing_recent_data_does_not_crash() -> None:
    detector = FeatureDriftDetector()
    monitor = ModelMonitor()

    metrics = detector.detect(train_rows=[{"x": 1.0}], recent_rows=[])
    report = monitor.build_report(
        train_feature_rows=[{"x": 1.0}],
        recent_feature_rows=[],
        baseline_predictions=[],
        recent_predictions=[],
    )

    assert metrics == []
    assert report.drift_level is DriftLevel.NONE
    assert report.recommended_action is DriftAction.CONTINUE
