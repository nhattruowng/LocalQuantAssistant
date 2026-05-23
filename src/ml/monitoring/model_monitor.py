"""Model/data drift monitoring orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import json
from typing import Mapping, Sequence

from ml.monitoring.calibration_monitor import CalibrationMonitor
from ml.monitoring.drift_detector import FeatureDriftDetector


class DriftLevel(str, Enum):
    """Drift severity levels."""

    NONE = "NONE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class DriftAction(str, Enum):
    """Recommended actions after drift detection."""

    CONTINUE = "CONTINUE"
    WARN = "WARN"
    RETRAIN_CANDIDATE = "RETRAIN_CANDIDATE"
    DISABLE_MODEL = "DISABLE_MODEL"


@dataclass(frozen=True)
class DriftReport:
    """Unified monitoring report for feature/model drift."""

    drift_level: DriftLevel
    drift_score: float
    drifted_features: list[dict[str, object]] = field(default_factory=list)
    prediction_shift: dict[str, object] = field(default_factory=dict)
    calibration_shift: dict[str, object] = field(default_factory=dict)
    regime_shift: dict[str, object] = field(default_factory=dict)
    recommended_action: DriftAction = DriftAction.CONTINUE

    def to_dict(self) -> dict[str, object]:
        return {
            "drift_level": self.drift_level.value,
            "drift_score": self.drift_score,
            "drifted_features": list(self.drifted_features),
            "prediction_shift": dict(self.prediction_shift),
            "calibration_shift": dict(self.calibration_shift),
            "regime_shift": dict(self.regime_shift),
            "recommended_action": self.recommended_action.value,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict())


class ModelMonitor:
    """Evaluate feature, prediction, calibration, and regime drift."""

    def __init__(
        self,
        feature_detector: FeatureDriftDetector | None = None,
        calibration_monitor: CalibrationMonitor | None = None,
    ) -> None:
        self._feature_detector = feature_detector or FeatureDriftDetector()
        self._calibration_monitor = calibration_monitor or CalibrationMonitor()

    def build_report(
        self,
        train_feature_rows: Sequence[Mapping[str, object]] | None,
        recent_feature_rows: Sequence[Mapping[str, object]] | None,
        baseline_predictions: Sequence[Mapping[str, object]] | None,
        recent_predictions: Sequence[Mapping[str, object]] | None,
        baseline_calibration: Sequence[Mapping[str, object]] | None = None,
        recent_calibration: Sequence[Mapping[str, object]] | None = None,
        baseline_regime_counts: Mapping[str, float | int] | None = None,
        recent_regime_counts: Mapping[str, float | int] | None = None,
    ) -> DriftReport:
        """Create drift report with robust handling for missing windows."""
        feature_metrics = self._feature_detector.detect(
            train_rows=train_feature_rows,
            recent_rows=recent_feature_rows,
        )
        drifted_features = [item.to_dict() for item in feature_metrics if item.drifted]
        feature_score = max((float(item.drift_score) for item in feature_metrics), default=0.0)

        prediction_shift = _prediction_shift(baseline_predictions or [], recent_predictions or [])
        calibration = self._calibration_monitor.evaluate(
            baseline_records=baseline_calibration,
            recent_records=recent_calibration,
        ).to_dict()
        regime_shift = _regime_shift(baseline_regime_counts or {}, recent_regime_counts or {})

        drift_score = _clip01(
            max(
                feature_score,
                float(prediction_shift.get("score", 0.0)),
                float(calibration.get("score", 0.0)),
                float(regime_shift.get("score", 0.0)),
            )
        )
        level = _drift_level(drift_score)
        action = _recommended_action(level)
        return DriftReport(
            drift_level=level,
            drift_score=round(drift_score, 8),
            drifted_features=drifted_features,
            prediction_shift=prediction_shift,
            calibration_shift=calibration,
            regime_shift=regime_shift,
            recommended_action=action,
        )


def _prediction_shift(
    baseline: Sequence[Mapping[str, object]],
    recent: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    if not baseline or not recent:
        return {
            "distribution_shift": 0.0,
            "probability_shift": 0.0,
            "score": 0.0,
        }
    base_dist = _signal_distribution(baseline)
    recent_dist = _signal_distribution(recent)
    dist_shift = _total_variation(base_dist, recent_dist)
    base_probs = _mean_probabilities(baseline)
    recent_probs = _mean_probabilities(recent)
    prob_shift = _total_variation(base_probs, recent_probs)
    return {
        "distribution_shift": round(dist_shift, 8),
        "probability_shift": round(prob_shift, 8),
        "baseline_distribution": base_dist,
        "recent_distribution": recent_dist,
        "baseline_mean_probabilities": base_probs,
        "recent_mean_probabilities": recent_probs,
        "score": round(_clip01(max(dist_shift, prob_shift) / 0.35), 8),
    }


def _regime_shift(
    baseline_counts: Mapping[str, float | int],
    recent_counts: Mapping[str, float | int],
) -> dict[str, object]:
    if not baseline_counts or not recent_counts:
        return {"shift": 0.0, "score": 0.0}
    base = _normalize_counts(baseline_counts)
    recent = _normalize_counts(recent_counts)
    shift = _total_variation(base, recent)
    return {
        "baseline_distribution": base,
        "recent_distribution": recent,
        "shift": round(shift, 8),
        "score": round(_clip01(shift / 0.30), 8),
    }


def _signal_distribution(rows: Sequence[Mapping[str, object]]) -> dict[str, float]:
    counts = {"BUY": 0.0, "SELL": 0.0, "WAIT": 0.0}
    total = 0.0
    for row in rows:
        signal = row.get("signal")
        if signal is None:
            probs = row.get("probabilities")
            if isinstance(probs, Mapping):
                parsed = _parse_probabilities(probs)
                if parsed:
                    signal = max(parsed, key=parsed.get)
        key = str(signal or "").upper()
        if key in counts:
            counts[key] += 1.0
            total += 1.0
    if total <= 0:
        return {"BUY": 0.0, "SELL": 0.0, "WAIT": 0.0}
    return {key: round(value / total, 8) for key, value in counts.items()}


def _mean_probabilities(rows: Sequence[Mapping[str, object]]) -> dict[str, float]:
    sums = {"BUY": 0.0, "SELL": 0.0, "WAIT": 0.0}
    used = 0
    for row in rows:
        probs = row.get("probabilities")
        if not isinstance(probs, Mapping):
            continue
        parsed = _parse_probabilities(probs)
        if not parsed:
            continue
        used += 1
        for key in sums:
            sums[key] += parsed.get(key, 0.0)
    if used <= 0:
        return {key: 0.0 for key in sums}
    return {key: round(value / used, 8) for key, value in sums.items()}


def _normalize_counts(counts: Mapping[str, float | int]) -> dict[str, float]:
    keys = sorted(str(key).upper() for key in counts.keys())
    normalized: dict[str, float] = {key: 0.0 for key in keys}
    total = 0.0
    for key, value in counts.items():
        name = str(key).upper()
        try:
            amount = max(0.0, float(value))
        except (TypeError, ValueError):
            amount = 0.0
        normalized[name] = normalized.get(name, 0.0) + amount
        total += amount
    if total <= 0:
        return normalized
    return {key: round(value / total, 8) for key, value in normalized.items()}


def _parse_probabilities(payload: Mapping[str, object]) -> dict[str, float]:
    parsed: dict[str, float] = {}
    for key in ("BUY", "SELL", "WAIT"):
        try:
            parsed[key] = max(0.0, float(payload.get(key, 0.0)))
        except (TypeError, ValueError):
            parsed[key] = 0.0
    return parsed


def _total_variation(left: Mapping[str, float], right: Mapping[str, float]) -> float:
    keys = set(left.keys()) | set(right.keys())
    return 0.5 * sum(abs(float(left.get(key, 0.0)) - float(right.get(key, 0.0))) for key in keys)


def _drift_level(score: float) -> DriftLevel:
    if score >= 0.75:
        return DriftLevel.HIGH
    if score >= 0.45:
        return DriftLevel.MEDIUM
    if score >= 0.20:
        return DriftLevel.LOW
    return DriftLevel.NONE


def _recommended_action(level: DriftLevel) -> DriftAction:
    if level is DriftLevel.HIGH:
        return DriftAction.DISABLE_MODEL
    if level is DriftLevel.MEDIUM:
        return DriftAction.RETRAIN_CANDIDATE
    if level is DriftLevel.LOW:
        return DriftAction.WARN
    return DriftAction.CONTINUE


def _clip01(value: float) -> float:
    return max(0.0, min(float(value), 1.0))
