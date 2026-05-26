"""Strict model registry with financial promotion gates."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
import json
from typing import Any, Mapping

import joblib


class ModelStatus(str, Enum):
    """Lifecycle status for registered model versions."""

    CANDIDATE = "candidate"
    CHAMPION = "champion"
    ARCHIVED = "archived"


@dataclass(frozen=True)
class PromotionCriteria:
    """Financial promotion rules for candidate models."""

    min_trades: int = 30
    required_validation_method: str = "walk_forward"
    profit_metric: str = "net_profit"
    drawdown_metric: str = "max_drawdown"
    calibration_metric: str = "brier_score_after"
    allow_equal_drawdown: bool = True
    allow_equal_calibration: bool = True


@dataclass(frozen=True)
class RegisteredModel:
    """Registered model metadata."""

    model_id: str
    model_version: str
    status: ModelStatus
    symbol: str
    timeframe: str
    feature_set_id: str
    validation_method: str
    model_path: Path
    metadata_path: Path
    metrics: dict[str, Any] = field(default_factory=dict)
    calibration_metrics: dict[str, Any] = field(default_factory=dict)
    known_failure_modes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "model_version": self.model_version,
            "status": self.status.value,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "feature_set_id": self.feature_set_id,
            "validation_method": self.validation_method,
            "model_path": str(self.model_path),
            "metadata_path": str(self.metadata_path),
            "metrics": dict(self.metrics),
            "calibration_metrics": dict(self.calibration_metrics),
            "known_failure_modes": list(self.known_failure_modes),
        }


@dataclass(frozen=True)
class PromotionDecision:
    """Promotion decision with explicit pass/fail reasons."""

    promoted: bool
    model_id: str
    reasons: list[str]
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "promoted": self.promoted,
            "model_id": self.model_id,
            "reasons": list(self.reasons),
            "metadata": dict(self.metadata),
        }


class ModelRegistry:
    """Persist candidate/champion/archive model versions and enforce promotion rules."""

    def __init__(self, model_dir: Path) -> None:
        self._model_dir = Path(model_dir)

    def save_candidate(
        self,
        model: Any,
        symbol: str,
        timeframe: str,
        feature_set_id: str,
        validation_method: str,
        metrics: Mapping[str, Any],
        calibration_metrics: Mapping[str, Any] | None = None,
        known_failure_modes: list[str] | None = None,
        model_type: str | None = None,
    ) -> RegisteredModel:
        """Persist a candidate model version."""
        version = self.next_version(symbol, timeframe)
        version_dir = self._family_dir(symbol, timeframe) / version
        version_dir.mkdir(parents=True, exist_ok=False)
        model_path = version_dir / "model.joblib"
        metadata_path = version_dir / "metadata.json"
        joblib.dump(model, model_path)

        model_id = self.model_id(symbol, timeframe, version)
        metadata = {
            "model_id": model_id,
            "model_version": version,
            "status": ModelStatus.CANDIDATE.value,
            "symbol": symbol,
            "timeframe": timeframe,
            "feature_set_id": feature_set_id,
            "validation_method": validation_method,
            "model_type": model_type or type(model).__name__,
            "trained_at": datetime.now(UTC).isoformat(),
            "metrics": dict(metrics),
            "calibration_metrics": dict(calibration_metrics or {}),
            "known_failure_modes": list(known_failure_modes or []),
            "model_path": str(model_path),
            "metadata_path": str(metadata_path),
        }
        _write_metadata(metadata_path, metadata)
        return _registered_from_metadata(metadata)

    def promote_if_eligible(
        self,
        model_id: str,
        baseline_metrics: Mapping[str, Any],
        baseline_calibration_metrics: Mapping[str, Any] | None = None,
        criteria: PromotionCriteria | None = None,
    ) -> PromotionDecision:
        """Promote a candidate only when all financial quality gates pass."""
        gate = criteria or PromotionCriteria()
        metadata, path = self._find_metadata_by_id(model_id)
        reasons = _promotion_failures(
            candidate=metadata,
            baseline_metrics=dict(baseline_metrics),
            baseline_calibration_metrics=dict(baseline_calibration_metrics or {}),
            criteria=gate,
        )
        if reasons:
            return PromotionDecision(
                promoted=False,
                model_id=model_id,
                reasons=reasons,
                metadata=metadata,
            )

        self._archive_existing_champions(
            symbol=str(metadata["symbol"]),
            timeframe=str(metadata["timeframe"]),
        )
        metadata["status"] = ModelStatus.CHAMPION.value
        metadata["promoted_at"] = datetime.now(UTC).isoformat()
        _write_metadata(path, metadata)
        return PromotionDecision(
            promoted=True,
            model_id=model_id,
            reasons=["promotion_criteria_passed"],
            metadata=metadata,
        )

    def archive(self, model_id: str) -> dict[str, Any]:
        """Archive one registered model."""
        metadata, path = self._find_metadata_by_id(model_id)
        metadata["status"] = ModelStatus.ARCHIVED.value
        _write_metadata(path, metadata)
        return metadata

    def load_metadata(self, model_id: str) -> dict[str, Any]:
        """Load metadata by model id."""
        metadata, _path = self._find_metadata_by_id(model_id)
        return metadata

    def list_models(
        self,
        symbol: str | None = None,
        timeframe: str | None = None,
    ) -> list[dict[str, Any]]:
        """List registry metadata records."""
        records: list[dict[str, Any]] = []
        for path in sorted(self._model_dir.glob("**/metadata.json")):
            try:
                metadata = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if symbol is not None and metadata.get("symbol") != symbol:
                continue
            if timeframe is not None and metadata.get("timeframe") != timeframe:
                continue
            metadata["metadata_path"] = str(path)
            records.append(metadata)
        return records

    def latest_champion(
        self,
        symbol: str,
        timeframe: str,
    ) -> dict[str, Any] | None:
        """Return latest champion metadata for a family."""
        champions = [
            item
            for item in self.list_models(symbol=symbol, timeframe=timeframe)
            if item.get("status") == ModelStatus.CHAMPION.value
        ]
        if not champions:
            return None
        return max(champions, key=lambda item: _version_number(str(item.get("model_version", "v000"))))

    def next_version(self, symbol: str, timeframe: str) -> str:
        """Return next vNNN for the symbol/timeframe family."""
        family_dir = self._family_dir(symbol, timeframe)
        versions = [
            path.name
            for path in family_dir.glob("v*")
            if path.is_dir() and path.name[1:].isdigit()
        ]
        if not versions:
            return "v001"
        return f"v{max(_version_number(version) for version in versions) + 1:03d}"

    @staticmethod
    def model_id(symbol: str, timeframe: str, version: str) -> str:
        return f"{_safe_symbol(symbol)}_{timeframe}_{version}"

    def _family_dir(self, symbol: str, timeframe: str) -> Path:
        return self._model_dir / _safe_symbol(symbol) / timeframe

    def _find_metadata_by_id(self, model_id: str) -> tuple[dict[str, Any], Path]:
        for metadata in self.list_models():
            if metadata.get("model_id") == model_id:
                return metadata, Path(str(metadata["metadata_path"]))
        raise ValueError(f"Model not found: {model_id}.")

    def _archive_existing_champions(self, symbol: str, timeframe: str) -> None:
        for metadata in self.list_models(symbol=symbol, timeframe=timeframe):
            if metadata.get("status") != ModelStatus.CHAMPION.value:
                continue
            metadata["status"] = ModelStatus.ARCHIVED.value
            _write_metadata(Path(str(metadata["metadata_path"])), metadata)


def _promotion_failures(
    candidate: Mapping[str, Any],
    baseline_metrics: dict[str, Any],
    baseline_calibration_metrics: dict[str, Any],
    criteria: PromotionCriteria,
) -> list[str]:
    failures: list[str] = []
    if candidate.get("status") != ModelStatus.CANDIDATE.value:
        failures.append("model_is_not_candidate")
    if candidate.get("validation_method") != criteria.required_validation_method:
        failures.append("validation_method_is_not_walk_forward")

    metrics = _flatten_metrics(candidate.get("metrics", {}))
    baseline = _flatten_metrics(baseline_metrics)
    candidate_profit = _metric(metrics, criteria.profit_metric)
    baseline_profit = _metric(baseline, criteria.profit_metric)
    if candidate_profit <= baseline_profit:
        failures.append("walk_forward_profit_not_better_than_baseline")

    candidate_drawdown = _metric(metrics, criteria.drawdown_metric)
    baseline_drawdown = _metric(baseline, criteria.drawdown_metric)
    if criteria.allow_equal_drawdown:
        if candidate_drawdown > baseline_drawdown:
            failures.append("drawdown_worse_than_baseline")
    elif candidate_drawdown >= baseline_drawdown:
        failures.append("drawdown_not_better_than_baseline")

    total_trades = int(_metric(metrics, "total_trades"))
    if total_trades < criteria.min_trades:
        failures.append("insufficient_trade_count")

    calibration = dict(candidate.get("calibration_metrics", {}))
    baseline_calibration = dict(baseline_calibration_metrics or baseline.get("calibration_metrics", {}))
    candidate_calibration = _metric(calibration, criteria.calibration_metric)
    baseline_calibration_value = _metric(baseline_calibration, criteria.calibration_metric)
    if criteria.allow_equal_calibration:
        if candidate_calibration > baseline_calibration_value:
            failures.append("calibration_worse_than_baseline")
    elif candidate_calibration >= baseline_calibration_value:
        failures.append("calibration_not_better_than_baseline")

    if candidate.get("known_failure_modes"):
        failures.append("known_failure_modes_present")
    return failures


def _flatten_metrics(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    flattened = dict(value)
    for nested_key in ("walk_forward", "validation_summary", "summary", "validation"):
        nested = value.get(nested_key)
        if isinstance(nested, Mapping):
            flattened.update(nested)
    return flattened


def _metric(metrics: Mapping[str, Any], key: str) -> float:
    try:
        return float(metrics.get(key, 0.0))
    except (TypeError, ValueError):
        return 0.0


def _registered_from_metadata(metadata: Mapping[str, Any]) -> RegisteredModel:
    return RegisteredModel(
        model_id=str(metadata["model_id"]),
        model_version=str(metadata["model_version"]),
        status=ModelStatus(str(metadata["status"])),
        symbol=str(metadata["symbol"]),
        timeframe=str(metadata["timeframe"]),
        feature_set_id=str(metadata["feature_set_id"]),
        validation_method=str(metadata["validation_method"]),
        model_path=Path(str(metadata["model_path"])),
        metadata_path=Path(str(metadata["metadata_path"])),
        metrics=dict(metadata.get("metrics", {})),
        calibration_metrics=dict(metadata.get("calibration_metrics", {})),
        known_failure_modes=list(metadata.get("known_failure_modes", [])),
    )


def _safe_symbol(symbol: str) -> str:
    return symbol.replace("/", "_").replace(":", "_")


def _version_number(version: str) -> int:
    return int(version[1:]) if version.startswith("v") and version[1:].isdigit() else 0


def _write_metadata(path: Path, metadata: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(dict(metadata), default=_json_default, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _json_default(value: Any) -> Any:
    if hasattr(value, "item"):
        return value.item()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable.")
