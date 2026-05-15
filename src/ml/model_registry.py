"""Model persistence and metadata registry."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import json
from typing import Any

import joblib


class ModelRegistry:
    """Saves trained models and metadata artifacts."""

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
    ) -> tuple[Path, Path]:
        """Persist a model and JSON metadata."""
        self._model_dir.mkdir(parents=True, exist_ok=True)
        trained_at = datetime.now(UTC)
        safe_symbol = symbol.replace("/", "_").replace(":", "_")
        stem = f"{safe_symbol}_{timeframe}_{trained_at.strftime('%Y%m%dT%H%M%SZ')}"
        model_path = self._model_dir / f"{stem}.joblib"
        metadata_path = self._model_dir / f"{stem}.metadata.json"

        joblib.dump(model, model_path)
        metadata = {
            "symbol": symbol,
            "timeframe": timeframe,
            "trained_at": trained_at.isoformat(),
            "feature_columns": feature_columns,
            "metrics": metrics,
            "model_type": model_type,
            "model_path": str(model_path),
        }
        metadata_path.write_text(
            json.dumps(metadata, default=_json_default, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return model_path, metadata_path


def _json_default(value: Any) -> Any:
    """Convert common numeric scalar objects into JSON-serializable values."""
    if hasattr(value, "item"):
        return value.item()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable.")
