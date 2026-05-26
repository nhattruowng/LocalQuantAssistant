"""Tests for drift facade, feature metadata, and experiment tracking."""

from __future__ import annotations

import json

from experiments.experiment_tracker import ExperimentRecord, ExperimentTracker
from features.feature_store import FeatureSetMetadata, FeatureStore
from ml.monitoring.drift_detector import DriftDetector, population_stability_index


def test_psi_detect_drift() -> None:
    baseline = [float(index) for index in range(100)]
    recent = [float(index + 200) for index in range(100)]

    assert population_stability_index(baseline, recent) > 0.25


def test_drift_detector_reports_prediction_calibration_and_regime_shift() -> None:
    detector = DriftDetector()
    baseline_predictions = [
        {"signal": "BUY", "probabilities": {"BUY": 0.85, "SELL": 0.05, "WAIT": 0.10}}
        for _ in range(40)
    ]
    recent_predictions = [
        {"signal": "WAIT", "probabilities": {"BUY": 0.10, "SELL": 0.10, "WAIT": 0.80}}
        for _ in range(40)
    ]
    baseline_calibration = [
        {"label": "BUY", "probabilities": {"BUY": 0.80, "SELL": 0.10, "WAIT": 0.10}}
        for _ in range(20)
    ]
    recent_calibration = [
        {"label": "BUY", "probabilities": {"BUY": 0.20, "SELL": 0.30, "WAIT": 0.50}}
        for _ in range(20)
    ]

    report = detector.detect(
        baseline_predictions=baseline_predictions,
        recent_predictions=recent_predictions,
        baseline_calibration=baseline_calibration,
        recent_calibration=recent_calibration,
        baseline_regimes={"TREND": 80, "RANGE": 20},
        recent_regimes={"TREND": 10, "RANGE": 90},
    )

    assert report.drifted is True
    assert report.prediction_distribution_shift["score"] > 0.0
    assert report.calibration_drift["score"] > 0.0
    assert report.regime_drift["score"] > 0.0


def test_feature_store_save_and_load_metadata(tmp_path) -> None:
    store = FeatureStore(tmp_path)
    metadata = FeatureSetMetadata(
        feature_set_id="reasoning_features",
        feature_version="v2",
        feature_names=["atr", "ema_distance"],
        source_modules=["price_action.candle_analyzer"],
        causal_check_passed=True,
        config_hash="abc123",
    )

    store.save_metadata(metadata)
    loaded = store.load_metadata("reasoning_features", "v2")

    assert loaded.feature_set_id == "reasoning_features"
    assert loaded.feature_version == "v2"
    assert loaded.feature_names == ["atr", "ema_distance"]
    assert loaded.causal_check_passed is True


def test_feature_store_missing_optional_fields_does_not_crash(tmp_path) -> None:
    store = FeatureStore(tmp_path)
    path = tmp_path / "minimal" / "v1" / "metadata.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"feature_set_id": "minimal"}), encoding="utf-8")

    loaded = store.load_metadata("minimal", "v1")

    assert loaded.feature_set_id == "minimal"
    assert loaded.feature_version == "v1"
    assert loaded.feature_names == []
    assert loaded.causal_check_passed is False


def test_experiment_tracker_save_and_load(tmp_path) -> None:
    tracker = ExperimentTracker(tmp_path)
    record = ExperimentRecord(
        experiment_id="exp_001",
        model_version="model-2026-05",
        config_hash="cfg001",
        feature_set_id="reasoning_features",
        evidence_weights={"market_structure": 0.18},
        backtest_metrics={"net_profit": 125.0, "max_drawdown": -12.0},
        ablation_result={"price_action": {"delta": 10.0}},
    )

    tracker.save(record)
    loaded = tracker.load("exp_001")

    assert loaded.experiment_id == "exp_001"
    assert loaded.model_version == "model-2026-05"
    assert loaded.evidence_weights["market_structure"] == 0.18
    assert loaded.backtest_metrics["net_profit"] == 125.0


def test_experiment_tracker_compare_two_experiments(tmp_path) -> None:
    tracker = ExperimentTracker(tmp_path)
    baseline = ExperimentRecord(
        experiment_id="baseline",
        backtest_metrics={"net_profit": 100.0, "expectancy": 0.2, "max_drawdown": -8.0},
    )
    candidate = ExperimentRecord(
        experiment_id="candidate",
        backtest_metrics={"net_profit": 150.0, "expectancy": 0.35, "max_drawdown": -7.0},
    )
    tracker.save(baseline)
    tracker.save(candidate)

    comparison = tracker.compare("baseline", "candidate")

    assert comparison.metric_deltas["net_profit"] == 50.0
    assert comparison.metric_deltas["expectancy"] == 0.15
    assert comparison.winner == "candidate"


def test_experiment_missing_optional_fields_does_not_crash(tmp_path) -> None:
    tracker = ExperimentTracker(tmp_path)
    path = tmp_path / "minimal.json"
    path.write_text(json.dumps({"experiment_id": "minimal"}), encoding="utf-8")

    loaded = tracker.load("minimal")

    assert loaded.experiment_id == "minimal"
    assert loaded.evidence_weights == {}
    assert loaded.backtest_metrics == {}
    assert loaded.ablation_result == {}
