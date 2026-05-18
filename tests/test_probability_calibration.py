"""Tests for probability calibration and signal probability source plumbing."""

from __future__ import annotations

from datetime import UTC, datetime
import json

import numpy as np
import pandas as pd
import pytest

sklearn = pytest.importorskip("sklearn")
from sklearn.ensemble import RandomForestClassifier  # noqa: E402

from config.loader import load_settings  # noqa: E402
from ml.calibration.probability_calibrator import (  # noqa: E402
    CalibratedProbabilityModel,
    ProbabilityCalibrator,
    probability_payload,
)
from ml.model_registry import ModelRegistry  # noqa: E402
from regime.market_regime import MarketRegime  # noqa: E402
from signals.models import SignalType  # noqa: E402
from signals.signal_engine import SignalEngine  # noqa: E402


def test_calibration_preserves_class_order():
    model, x_values, y_values = _trained_model()

    result = ProbabilityCalibrator().calibrate(
        base_model=model,
        x_validation=x_values,
        y_validation=y_values,
        method="sigmoid",
        cv="prefit",
    )

    assert result.model.classes_ == list(model.classes_)


def test_calibrated_probability_rows_sum_to_one():
    model, x_values, y_values = _trained_model()
    result = ProbabilityCalibrator().calibrate(
        base_model=model,
        x_validation=x_values,
        y_validation=y_values,
        method="sigmoid",
        cv="prefit",
    )

    probabilities = result.model.predict_proba(x_values.head(5))

    assert np.allclose(probabilities.sum(axis=1), 1.0)


def test_probability_payload_falls_back_to_raw_when_calibrator_missing():
    model, x_values, _ = _trained_model()
    wrapper = CalibratedProbabilityModel(
        base_model=model,
        calibrator=None,
        method="sigmoid",
        classes=list(model.classes_),
    )

    payload = probability_payload(wrapper, x_values.head(1), use_calibrated=True)

    assert payload["probability_source"] == "raw"
    assert payload["calibrated_probabilities"] is None
    assert set(payload["raw_probabilities"]) == set(model.classes_)


def test_model_registry_writes_calibration_metadata(tmp_path):
    model, _, _ = _trained_model()
    registry = ModelRegistry(tmp_path)

    _, metadata_path = registry.save(
        model=model,
        symbol="BTC/USDT",
        timeframe="15m",
        feature_columns=["a", "b"],
        metrics={"calibration": {"brier_score_before": 0.2}},
        model_type="RandomForestClassifier",
        extra_metadata={
            "calibration_enabled": True,
            "calibration_method": "sigmoid",
            "brier_score_before": 0.2,
            "brier_score_after": 0.18,
            "log_loss_before": 1.1,
            "log_loss_after": 0.9,
        },
    )

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

    assert metadata["calibration_enabled"] is True
    assert metadata["calibration_method"] == "sigmoid"
    assert metadata["brier_score_after"] == 0.18


def test_signal_engine_returns_probability_source():
    engine = SignalEngine(load_settings())

    setup = engine.generate(
        symbol="BTC/USDT",
        timeframe="15m",
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        market_regime=MarketRegime.UPTREND,
        features={
            "close": 101.0,
            "atr_14": 10.0,
            "ema_20": 100.0,
            "ema_50": 95.0,
            "rsi_14": 55.0,
            "volume_ratio": 1.3,
            "rolling_high_20": 120.0,
            "rolling_low_20": 80.0,
            "trend_score": 1.0,
        },
        probabilities={"BUY": 0.70, "SELL": 0.10, "WAIT": 0.20},
        raw_probabilities={"BUY": 0.62, "SELL": 0.13, "WAIT": 0.25},
        calibrated_probabilities={"BUY": 0.70, "SELL": 0.10, "WAIT": 0.20},
        probability_source="calibrated",
    )

    assert setup.signal is SignalType.BUY
    assert setup.probability_source == "calibrated"
    assert setup.raw_probabilities == {"BUY": 0.62, "SELL": 0.13, "WAIT": 0.25}
    assert setup.calibrated_probabilities == {"BUY": 0.70, "SELL": 0.10, "WAIT": 0.20}


def _trained_model() -> tuple[RandomForestClassifier, pd.DataFrame, pd.Series]:
    """Return a tiny fitted multiclass model for calibration tests."""
    x_values = pd.DataFrame(
        {
            "a": [0.1, 0.2, 0.9, 1.0, 0.4, 0.5] * 8,
            "b": [1.0, 0.9, 0.2, 0.1, 0.5, 0.4] * 8,
        }
    )
    y_values = pd.Series(["BUY", "BUY", "SELL", "SELL", "WAIT", "WAIT"] * 8)
    model = RandomForestClassifier(n_estimators=20, random_state=7)
    model.fit(x_values, y_values)
    return model, x_values, y_values
