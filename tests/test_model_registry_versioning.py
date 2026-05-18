"""Tests for versioned model registry and regime-specific selection."""

from __future__ import annotations

from dataclasses import replace

import pandas as pd

from config.settings import Settings
from ml.model_registry import GLOBAL_SCOPE, REGIME_SCOPE, ModelRegistry
from ml.model_trainer import ModelTrainer
from ml.prediction_service import PredictionService


class DummyProbabilityModel:
    """Tiny pickle-friendly model for registry prediction tests."""

    classes_ = ["BUY", "SELL", "WAIT"]

    def predict_proba(self, rows: pd.DataFrame):
        return [[0.7, 0.1, 0.2] for _ in range(len(rows))]


def test_model_version_increments_and_metadata_loads(tmp_path):
    registry = ModelRegistry(tmp_path)

    first = registry.save(
        model=DummyProbabilityModel(),
        symbol="BTC/USDT",
        timeframe="15m",
        feature_columns=["f1"],
        metrics={"validation": {"accuracy": 0.6}},
        model_type="Dummy",
        auto_promote_champion=True,
    )
    second = registry.save(
        model=DummyProbabilityModel(),
        symbol="BTC/USDT",
        timeframe="15m",
        feature_columns=["f1"],
        metrics={"validation": {"accuracy": 0.7}},
        model_type="Dummy",
        auto_promote_champion=True,
    )

    latest = registry.latest_metadata("BTC/USDT", "15m")
    records = registry.list_models("BTC/USDT", "15m")

    assert first[1].name == "metadata.json"
    assert second[1].parent.name == "v002"
    assert latest is not None
    assert latest["model_version"] == "v002"
    assert latest["status"] == "champion"
    assert sorted(record["status"] for record in records) == ["archived", "champion"]


def test_registry_saves_required_metadata_and_layout(tmp_path):
    registry = ModelRegistry(tmp_path)

    model_path, metadata_path = registry.save(
        model=DummyProbabilityModel(),
        symbol="BTC/USDT",
        timeframe="15m",
        feature_columns=["f1"],
        metrics={
            "validation": {"accuracy": 0.75},
            "calibration": {"calibration_method": "none"},
        },
        model_type="Dummy",
        model_scope=REGIME_SCOPE,
        regime="UPTREND",
        extra_metadata={
            "dataset_start": "2026-01-01T00:00:00+00:00",
            "dataset_end": "2026-01-02T00:00:00+00:00",
            "label_distribution": {"BUY": 10, "SELL": 8, "WAIT": 12},
        },
        auto_promote_champion=True,
    )
    metadata = registry.load_metadata("BTC_USDT_15m_regime_UPTREND_v001")

    assert model_path.name == "model.joblib"
    assert metadata_path.parent.parts[-4:] == ("15m", "regime", "UPTREND", "v001")
    assert metadata["model_id"] == "BTC_USDT_15m_regime_UPTREND_v001"
    assert metadata["model_scope"] == REGIME_SCOPE
    assert metadata["regime"] == "UPTREND"
    assert metadata["status"] == "champion"
    assert metadata["validation_metrics"]["accuracy"] == 0.75
    assert metadata["calibration_metrics"]["calibration_method"] == "none"
    assert metadata["label_distribution"]["BUY"] == 10


def test_promote_and_archive_update_champion_status(tmp_path):
    registry = ModelRegistry(tmp_path)
    registry.save(
        model=DummyProbabilityModel(),
        symbol="BTC/USDT",
        timeframe="15m",
        feature_columns=["f1"],
        metrics={"validation": {"accuracy": 0.6}},
        model_type="Dummy",
        status="candidate",
    )
    registry.save(
        model=DummyProbabilityModel(),
        symbol="BTC/USDT",
        timeframe="15m",
        feature_columns=["f1"],
        metrics={"validation": {"accuracy": 0.7}},
        model_type="Dummy",
        status="candidate",
    )
    candidate = registry.latest_metadata("BTC/USDT", "15m", prefer_champion=False)

    promoted = registry.promote(str(candidate["model_id"]))
    archived = registry.archive(str(candidate["model_id"]))

    assert promoted["status"] == "champion"
    assert archived["status"] == "archived"


def test_prediction_service_falls_back_to_global_when_regime_model_missing(
    tmp_path,
    settings: Settings,
):
    registry = ModelRegistry(tmp_path)
    registry.save(
        model=DummyProbabilityModel(),
        symbol="BTC/USDT",
        timeframe="15m",
        feature_columns=["f1"],
        metrics={"validation": {"accuracy": 0.8}},
        model_type="Dummy",
        model_scope=GLOBAL_SCOPE,
        auto_promote_champion=True,
    )
    service = PredictionService(
        settings=replace(settings, training=replace(settings.training, model_dir=tmp_path)),
        registry=registry,
    )

    result = service.predict_row(
        symbol="BTC/USDT",
        timeframe="15m",
        row=pd.Series({"f1": 1.0, "market_regime": "UPTREND"}),
    )

    assert result.model_scope_used == GLOBAL_SCOPE
    assert result.fallback_reason == "no_regime_specific_model"
    assert result.probabilities["BUY"] == 0.7


def test_prediction_service_uses_regime_champion_when_available(
    tmp_path,
    settings: Settings,
):
    registry = ModelRegistry(tmp_path)
    registry.save(
        model=DummyProbabilityModel(),
        symbol="BTC/USDT",
        timeframe="15m",
        feature_columns=["f1"],
        metrics={"validation": {"accuracy": 0.8}},
        model_type="Dummy",
        model_scope=REGIME_SCOPE,
        regime="UPTREND",
        auto_promote_champion=True,
    )
    service = PredictionService(
        settings=replace(settings, training=replace(settings.training, model_dir=tmp_path)),
        registry=registry,
    )

    result = service.predict_row(
        symbol="BTC/USDT",
        timeframe="15m",
        row=pd.Series({"f1": 1.0, "market_regime": "UPTREND"}),
    )

    assert result.model_scope_used == REGIME_SCOPE
    assert result.fallback_reason is None
    assert result.model_version == "v001"


def test_prediction_service_falls_back_when_regime_quality_is_low(
    tmp_path,
    settings: Settings,
):
    registry = ModelRegistry(tmp_path)
    registry.save(
        model=DummyProbabilityModel(),
        symbol="BTC/USDT",
        timeframe="15m",
        feature_columns=["f1"],
        metrics={"validation": {"accuracy": 0.8}},
        model_type="Dummy",
        model_scope=GLOBAL_SCOPE,
        auto_promote_champion=True,
    )
    registry.save(
        model=DummyProbabilityModel(),
        symbol="BTC/USDT",
        timeframe="15m",
        feature_columns=["f1"],
        metrics={"validation": {"accuracy": 0.4}},
        model_type="Dummy",
        model_scope=REGIME_SCOPE,
        regime="UPTREND",
        auto_promote_champion=True,
    )
    strict_settings = replace(
        settings,
        training=replace(
            settings.training,
            model_dir=tmp_path,
            regime_specific=replace(
                settings.training.regime_specific,
                min_validation_accuracy=0.7,
            ),
        ),
    )
    service = PredictionService(settings=strict_settings, registry=registry)

    result = service.predict_row(
        symbol="BTC/USDT",
        timeframe="15m",
        row=pd.Series({"f1": 1.0, "market_regime": "UPTREND"}),
    )

    assert result.model_scope_used == GLOBAL_SCOPE
    assert result.fallback_reason == "regime_model_below_quality_threshold"


def test_trainer_skips_regime_with_too_few_samples(tmp_path, settings: Settings):
    strict_settings = replace(
        settings,
        training=replace(
            settings.training,
            model_dir=tmp_path,
            regime_specific=replace(
                settings.training.regime_specific,
                enabled=True,
                min_samples_per_regime=50,
                allowed_regimes=("UPTREND",),
            ),
        ),
    )
    trainer = ModelTrainer(settings=strict_settings, registry=ModelRegistry(tmp_path))
    prepared = pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-01-01", periods=12, freq="h"),
            "f1": range(12),
            "market_regime": ["UPTREND"] * 12,
            "label": ["BUY", "SELL", "WAIT"] * 4,
        }
    )

    report = trainer._train_regime_models(  # noqa: SLF001 - focused unit coverage.
        prepared=prepared,
        feature_columns=["f1"],
        symbol="BTC/USDT",
        timeframe="15m",
        global_metrics={"test": {"accuracy": 0.5}},
    )

    assert report["models"] == []
    assert report["skipped"][0]["regime"] == "UPTREND"
    assert report["skipped"][0]["reason"] == "insufficient_samples"
