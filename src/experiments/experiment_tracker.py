"""JSON-backed experiment tracking for research and backtests."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True)
class ExperimentRecord:
    """Persisted experiment metadata without storing secrets or raw datasets."""

    experiment_id: str
    model_version: str | None = None
    config_hash: str | None = None
    feature_set_id: str | None = None
    evidence_weights: dict[str, float] = field(default_factory=dict)
    backtest_metrics: dict[str, Any] = field(default_factory=dict)
    ablation_result: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "model_version": self.model_version,
            "config_hash": self.config_hash,
            "feature_set_id": self.feature_set_id,
            "evidence_weights": dict(self.evidence_weights),
            "backtest_metrics": dict(self.backtest_metrics),
            "ablation_result": dict(self.ablation_result),
            "created_at": self.created_at,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ExperimentRecord":
        return cls(
            experiment_id=str(payload.get("experiment_id") or "unknown_experiment"),
            model_version=_optional_string(payload.get("model_version")),
            config_hash=_optional_string(payload.get("config_hash")),
            feature_set_id=_optional_string(payload.get("feature_set_id")),
            evidence_weights=_float_mapping(payload.get("evidence_weights")),
            backtest_metrics=dict(payload.get("backtest_metrics") or {}),
            ablation_result=dict(payload.get("ablation_result") or {}),
            created_at=str(payload.get("created_at") or datetime.now(timezone.utc).isoformat()),
            metadata=dict(payload.get("metadata") or {}),
        )


@dataclass(frozen=True)
class ExperimentComparison:
    """Metric deltas from baseline experiment to candidate experiment."""

    baseline_experiment_id: str
    candidate_experiment_id: str
    metric_deltas: dict[str, float] = field(default_factory=dict)
    winner: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "baseline_experiment_id": self.baseline_experiment_id,
            "candidate_experiment_id": self.candidate_experiment_id,
            "metric_deltas": dict(self.metric_deltas),
            "winner": self.winner,
        }


class ExperimentTracker:
    """Save, load, and compare experiment metadata records."""

    def __init__(self, root_dir: str | Path) -> None:
        self.root_dir = Path(root_dir)

    def save(self, record: ExperimentRecord | Mapping[str, Any]) -> Path:
        experiment = record if isinstance(record, ExperimentRecord) else ExperimentRecord.from_dict(record)
        path = self._record_path(experiment.experiment_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(experiment.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
        return path

    def load(self, experiment_id: str) -> ExperimentRecord:
        payload = json.loads(self._record_path(experiment_id).read_text(encoding="utf-8"))
        return ExperimentRecord.from_dict(payload)

    def list_experiments(self) -> list[ExperimentRecord]:
        if not self.root_dir.exists():
            return []
        records: list[ExperimentRecord] = []
        for path in sorted(self.root_dir.glob("*.json")):
            try:
                records.append(ExperimentRecord.from_dict(json.loads(path.read_text(encoding="utf-8"))))
            except (OSError, json.JSONDecodeError, TypeError, ValueError):
                continue
        return records

    def compare(
        self,
        baseline: str | ExperimentRecord,
        candidate: str | ExperimentRecord,
        metric_keys: list[str] | None = None,
    ) -> ExperimentComparison:
        baseline_record = self.load(baseline) if isinstance(baseline, str) else baseline
        candidate_record = self.load(candidate) if isinstance(candidate, str) else candidate
        keys = metric_keys or _numeric_metric_keys(baseline_record.backtest_metrics, candidate_record.backtest_metrics)
        deltas: dict[str, float] = {}
        for key in keys:
            baseline_value = _numeric_value(baseline_record.backtest_metrics.get(key))
            candidate_value = _numeric_value(candidate_record.backtest_metrics.get(key))
            if baseline_value is None or candidate_value is None:
                continue
            deltas[key] = round(candidate_value - baseline_value, 8)
        winner = _choose_winner(baseline_record, candidate_record, deltas)
        return ExperimentComparison(
            baseline_experiment_id=baseline_record.experiment_id,
            candidate_experiment_id=candidate_record.experiment_id,
            metric_deltas=deltas,
            winner=winner,
        )

    def _record_path(self, experiment_id: str) -> Path:
        return self.root_dir / f"{_safe_name(experiment_id)}.json"


def _choose_winner(
    baseline: ExperimentRecord,
    candidate: ExperimentRecord,
    deltas: Mapping[str, float],
) -> str | None:
    for metric in ("net_profit", "expectancy", "profit_factor", "winrate"):
        if metric in deltas:
            return candidate.experiment_id if deltas[metric] > 0 else baseline.experiment_id
    if not deltas:
        return None
    total_delta = sum(deltas.values())
    return candidate.experiment_id if total_delta > 0 else baseline.experiment_id


def _numeric_metric_keys(left: Mapping[str, Any], right: Mapping[str, Any]) -> list[str]:
    keys = sorted(set(left.keys()) | set(right.keys()))
    return [key for key in keys if _numeric_value(left.get(key)) is not None and _numeric_value(right.get(key)) is not None]


def _numeric_value(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _float_mapping(value: Any) -> dict[str, float]:
    if not isinstance(value, Mapping):
        return {}
    parsed: dict[str, float] = {}
    for key, amount in value.items():
        numeric = _numeric_value(amount)
        if numeric is not None:
            parsed[str(key)] = numeric
    return parsed


def _safe_name(value: str | None) -> str:
    text = str(value or "unknown")
    for char in ("\\", "/", ":", "*", "?", '"', "<", ">", "|"):
        text = text.replace(char, "_")
    return text.strip() or "unknown"


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)
