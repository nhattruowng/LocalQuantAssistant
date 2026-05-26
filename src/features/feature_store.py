"""Lightweight metadata store for causal feature sets."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True)
class FeatureSetMetadata:
    """Versioned metadata for a feature set without storing raw market data."""

    feature_set_id: str
    feature_version: str = "v1"
    feature_names: list[str] = field(default_factory=list)
    source_modules: list[str] = field(default_factory=list)
    causal_check_passed: bool = False
    config_hash: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "feature_set_id": self.feature_set_id,
            "feature_version": self.feature_version,
            "feature_names": list(self.feature_names),
            "source_modules": list(self.source_modules),
            "causal_check_passed": bool(self.causal_check_passed),
            "config_hash": self.config_hash,
            "created_at": self.created_at,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "FeatureSetMetadata":
        return cls(
            feature_set_id=str(payload.get("feature_set_id") or "unknown_feature_set"),
            feature_version=str(payload.get("feature_version") or "v1"),
            feature_names=_string_list(payload.get("feature_names")),
            source_modules=_string_list(payload.get("source_modules")),
            causal_check_passed=bool(payload.get("causal_check_passed", False)),
            config_hash=_optional_string(payload.get("config_hash")),
            created_at=str(payload.get("created_at") or datetime.now(timezone.utc).isoformat()),
            metadata=dict(payload.get("metadata") or {}),
        )


class FeatureStore:
    """Persist and load feature metadata JSON files."""

    def __init__(self, root_dir: str | Path) -> None:
        self.root_dir = Path(root_dir)

    def save_metadata(self, metadata: FeatureSetMetadata | Mapping[str, Any]) -> Path:
        record = metadata if isinstance(metadata, FeatureSetMetadata) else FeatureSetMetadata.from_dict(metadata)
        path = self._metadata_path(record.feature_set_id, record.feature_version)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(record.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
        return path

    def load_metadata(self, feature_set_id: str, feature_version: str | None = None) -> FeatureSetMetadata:
        version = feature_version or self._latest_version(feature_set_id)
        path = self._metadata_path(feature_set_id, version)
        payload = json.loads(path.read_text(encoding="utf-8"))
        return FeatureSetMetadata.from_dict(payload)

    def list_metadata(self, feature_set_id: str | None = None) -> list[FeatureSetMetadata]:
        search_root = self.root_dir / _safe_name(feature_set_id) if feature_set_id else self.root_dir
        if not search_root.exists():
            return []
        records: list[FeatureSetMetadata] = []
        for path in sorted(search_root.rglob("metadata.json")):
            try:
                records.append(FeatureSetMetadata.from_dict(json.loads(path.read_text(encoding="utf-8"))))
            except (OSError, json.JSONDecodeError, TypeError, ValueError):
                continue
        return records

    def _metadata_path(self, feature_set_id: str, feature_version: str) -> Path:
        return self.root_dir / _safe_name(feature_set_id) / _safe_name(feature_version) / "metadata.json"

    def _latest_version(self, feature_set_id: str) -> str:
        feature_root = self.root_dir / _safe_name(feature_set_id)
        versions = sorted(path.name for path in feature_root.iterdir() if path.is_dir()) if feature_root.exists() else []
        if not versions:
            raise FileNotFoundError(f"No feature metadata found for feature_set_id={feature_set_id!r}")
        return versions[-1]


def _safe_name(value: str | None) -> str:
    text = str(value or "unknown")
    for char in ("\\", "/", ":", "*", "?", '"', "<", ">", "|"):
        text = text.replace(char, "_")
    return text.strip() or "unknown"


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    try:
        return [str(item) for item in value]
    except TypeError:
        return []


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)
