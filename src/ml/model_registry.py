"""Versioned model registry for global and regime-specific models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
import json
from typing import Any

import joblib


GLOBAL_SCOPE = "global"
REGIME_SCOPE = "regime_specific"
VALID_STATUSES = {"candidate", "champion", "archived"}


@dataclass(frozen=True)
class RegisteredModel:
    """Metadata and artifact paths for a registered model version."""

    model_id: str
    model_version: str
    model_scope: str
    symbol: str
    timeframe: str
    regime: str | None
    status: str
    model_path: Path
    metadata_path: Path
    metrics: dict[str, Any]


class ModelRegistry:
    """Persists models in a versioned symbol/timeframe registry."""

    def __init__(self, model_dir: Path) -> None:
        self._model_dir = model_dir

    def save(
        self,
        model: Any,
        symbol: str,
        timeframe: str,
        feature_columns: list[str],
        metrics: dict[str, Any],
        model_type: str,
        extra_metadata: dict[str, Any] | None = None,
        model_scope: str = GLOBAL_SCOPE,
        regime: str | None = None,
        status: str = "candidate",
        auto_promote_champion: bool = False,
    ) -> tuple[Path, Path]:
        """Persist a model version and JSON metadata."""
        if status not in VALID_STATUSES:
            raise ValueError(f"Unsupported model status: {status}.")
        scope_dir = self._scope_dir(symbol, timeframe, model_scope, regime)
        version = self.next_version(symbol, timeframe, model_scope, regime)
        version_dir = scope_dir / version
        version_dir.mkdir(parents=True, exist_ok=False)

        model_path = version_dir / "model.joblib"
        metadata_path = version_dir / "metadata.json"
        final_status = "champion" if auto_promote_champion else status
        if final_status == "champion":
            self._archive_existing_champions(symbol, timeframe, model_scope, regime)

        joblib.dump(model, model_path)
        trained_at = datetime.now(UTC)
        metadata = {
            "model_id": self.model_id(symbol, timeframe, model_scope, regime, version),
            "model_version": version,
            "model_scope": model_scope,
            "regime": regime,
            "symbol": symbol,
            "timeframe": timeframe,
            "trained_at": trained_at.isoformat(),
            "dataset_start": None,
            "dataset_end": None,
            "feature_columns": feature_columns,
            "label_distribution": {},
            "validation_metrics": metrics.get("validation", {}),
            "calibration_metrics": metrics.get("calibration", {}),
            "metrics": metrics,
            "model_type": model_type,
            "status": final_status,
            "model_path": str(model_path),
            "metadata_path": str(metadata_path),
        }
        if extra_metadata:
            metadata.update(extra_metadata)
            metadata["validation_metrics"] = metadata.get(
                "validation_metrics",
                metrics.get("validation", {}),
            )
            metadata["calibration_metrics"] = metadata.get(
                "calibration_metrics",
                metrics.get("calibration", {}),
            )
        metadata_path.write_text(
            json.dumps(metadata, default=_json_default, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return model_path, metadata_path

    def next_version(
        self,
        symbol: str,
        timeframe: str,
        model_scope: str = GLOBAL_SCOPE,
        regime: str | None = None,
    ) -> str:
        """Return the next vNNN version for a model family."""
        versions = [
            path.name
            for path in self._scope_dir(symbol, timeframe, model_scope, regime).glob("v*")
            if path.is_dir() and path.name[1:].isdigit()
        ]
        if not versions:
            return "v001"
        latest = max(int(version[1:]) for version in versions)
        return f"v{latest + 1:03d}"

    def latest_metadata(
        self,
        symbol: str,
        timeframe: str,
        model_scope: str = GLOBAL_SCOPE,
        regime: str | None = None,
        prefer_champion: bool = True,
    ) -> dict[str, Any] | None:
        """Return latest metadata for a model family."""
        records = self.list_models(symbol=symbol, timeframe=timeframe)
        records = [
            item
            for item in records
            if item.get("model_scope") == model_scope and item.get("regime") == regime
        ]
        if not records:
            if model_scope == GLOBAL_SCOPE and regime is None:
                return self._latest_legacy_metadata(symbol, timeframe)
            return None
        if prefer_champion:
            champions = [item for item in records if item.get("status") == "champion"]
            if champions:
                return _latest_by_version(champions)
        return _latest_by_version(records)

    def resolve_for_prediction(
        self,
        symbol: str,
        timeframe: str,
        regime: str | None,
        min_validation_accuracy: float = 0.0,
    ) -> tuple[dict[str, Any] | None, str | None]:
        """Resolve regime-specific champion or fallback global model."""
        if regime:
            regime_metadata = self.latest_metadata(
                symbol=symbol,
                timeframe=timeframe,
                model_scope=REGIME_SCOPE,
                regime=regime,
            )
            if regime_metadata and _passes_quality(regime_metadata, min_validation_accuracy):
                return regime_metadata, None
            if regime_metadata:
                reason = "regime_model_below_quality_threshold"
            else:
                reason = "no_regime_specific_model"
        else:
            reason = "missing_market_regime"
        return (
            self.latest_metadata(symbol, timeframe, model_scope=GLOBAL_SCOPE, regime=None),
            reason,
        )

    def list_models(
        self,
        symbol: str | None = None,
        timeframe: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return registry metadata records."""
        paths = sorted(self._model_dir.glob("**/metadata.json"))
        records = []
        for path in paths:
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
        records.extend(self._legacy_records(symbol, timeframe))
        return records

    def promote(self, model_id: str) -> dict[str, Any]:
        """Promote a model to champion and archive previous champions in its family."""
        metadata, path = self._find_metadata_by_id(model_id)
        self._archive_existing_champions(
            symbol=str(metadata["symbol"]),
            timeframe=str(metadata["timeframe"]),
            model_scope=str(metadata["model_scope"]),
            regime=metadata.get("regime"),
        )
        metadata["status"] = "champion"
        _write_metadata(path, metadata)
        return metadata

    def archive(self, model_id: str) -> dict[str, Any]:
        """Mark a model version as archived."""
        metadata, path = self._find_metadata_by_id(model_id)
        metadata["status"] = "archived"
        _write_metadata(path, metadata)
        return metadata

    def load_metadata(self, model_id: str) -> dict[str, Any]:
        """Load one metadata record by model id."""
        metadata, _path = self._find_metadata_by_id(model_id)
        return metadata

    @staticmethod
    def model_id(
        symbol: str,
        timeframe: str,
        model_scope: str,
        regime: str | None,
        version: str,
    ) -> str:
        """Build a stable model id."""
        family = "global" if model_scope == GLOBAL_SCOPE else f"regime_{regime}"
        return f"{_safe_symbol(symbol)}_{timeframe}_{family}_{version}"

    def _scope_dir(
        self,
        symbol: str,
        timeframe: str,
        model_scope: str,
        regime: str | None,
    ) -> Path:
        """Return directory for a model family."""
        base = self._model_dir / _safe_symbol(symbol) / timeframe
        if model_scope == GLOBAL_SCOPE:
            return base / "global"
        if not regime:
            raise ValueError("Regime-specific models require a regime.")
        return base / "regime" / str(regime)

    def _archive_existing_champions(
        self,
        symbol: str,
        timeframe: str,
        model_scope: str,
        regime: str | None,
    ) -> None:
        """Archive current champions within the same model family."""
        for metadata in self.list_models(symbol=symbol, timeframe=timeframe):
            if metadata.get("model_scope") != model_scope:
                continue
            if metadata.get("regime") != regime:
                continue
            if metadata.get("status") != "champion":
                continue
            path_value = metadata.get("metadata_path")
            if not path_value:
                continue
            metadata["status"] = "archived"
            _write_metadata(Path(str(path_value)), metadata)

    def _find_metadata_by_id(self, model_id: str) -> tuple[dict[str, Any], Path]:
        """Find metadata by id or raise ValueError."""
        for metadata in self.list_models():
            if metadata.get("model_id") == model_id:
                path = Path(str(metadata["metadata_path"]))
                return metadata, path
        raise ValueError(f"Model not found: {model_id}.")

    def _latest_legacy_metadata(
        self,
        symbol: str,
        timeframe: str,
    ) -> dict[str, Any] | None:
        """Return latest flat-file metadata from older registry layout."""
        records = self._legacy_records(symbol, timeframe)
        if not records:
            return None
        return max(records, key=lambda item: str(item.get("trained_at", "")))

    def _legacy_records(
        self,
        symbol: str | None = None,
        timeframe: str | None = None,
    ) -> list[dict[str, Any]]:
        """Load pre-versioned metadata files for backward compatibility."""
        records: list[dict[str, Any]] = []
        for path in sorted(self._model_dir.glob("*.metadata.json")):
            try:
                metadata = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if symbol is not None and metadata.get("symbol") != symbol:
                continue
            if timeframe is not None and metadata.get("timeframe") != timeframe:
                continue
            metadata.setdefault("model_version", "legacy")
            metadata.setdefault("model_scope", GLOBAL_SCOPE)
            metadata.setdefault("regime", None)
            metadata.setdefault("status", "champion")
            metadata.setdefault(
                "model_id",
                f"{_safe_symbol(str(metadata.get('symbol', 'UNKNOWN')))}_"
                f"{metadata.get('timeframe', 'unknown')}_global_legacy",
            )
            metadata["metadata_path"] = str(path)
            records.append(metadata)
        return records


def _latest_by_version(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Return latest record by numeric version, falling back to trained_at."""
    def sort_key(record: dict[str, Any]) -> tuple[int, str]:
        version = str(record.get("model_version", "v000"))
        number = int(version[1:]) if version.startswith("v") and version[1:].isdigit() else -1
        return number, str(record.get("trained_at", ""))

    return max(records, key=sort_key)


def _passes_quality(metadata: dict[str, Any], min_validation_accuracy: float) -> bool:
    """Return True when validation accuracy meets the minimum quality bar."""
    if metadata.get("status") != "champion":
        return False
    metrics = metadata.get("validation_metrics", {})
    if not isinstance(metrics, dict):
        return min_validation_accuracy <= 0
    accuracy = metrics.get("accuracy")
    if accuracy is None:
        return min_validation_accuracy <= 0
    return float(accuracy) >= min_validation_accuracy


def _safe_symbol(symbol: str) -> str:
    """Return a filesystem-safe symbol."""
    return symbol.replace("/", "_").replace(":", "_")


def _write_metadata(path: Path, metadata: dict[str, Any]) -> None:
    """Write metadata JSON."""
    path.write_text(
        json.dumps(metadata, default=_json_default, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _json_default(value: Any) -> Any:
    """Convert common numeric scalar objects into JSON-serializable values."""
    if hasattr(value, "item"):
        return value.item()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable.")
