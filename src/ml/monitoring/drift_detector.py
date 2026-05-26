"""Feature and model drift detection utilities."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from math import isfinite, log
from typing import Any, Mapping, Sequence

from ml.monitoring.calibration_monitor import CalibrationMonitor


@dataclass(frozen=True)
class FeatureDriftMetric:
    """One feature drift summary."""

    feature: str
    psi: float
    ks_stat: float | None
    ks_pvalue: float | None
    drift_score: float
    drifted: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "feature": self.feature,
            "psi": self.psi,
            "ks_stat": self.ks_stat,
            "ks_pvalue": self.ks_pvalue,
            "drift_score": self.drift_score,
            "drifted": self.drifted,
        }


class FeatureDriftDetector:
    """Detect feature drift by PSI and optional KS test."""

    def __init__(
        self,
        psi_medium_threshold: float = 0.10,
        psi_high_threshold: float = 0.25,
        ks_pvalue_threshold: float = 0.05,
    ) -> None:
        self._psi_medium_threshold = max(0.0, float(psi_medium_threshold))
        self._psi_high_threshold = max(self._psi_medium_threshold, float(psi_high_threshold))
        self._ks_pvalue_threshold = max(0.0, min(float(ks_pvalue_threshold), 1.0))

    def detect(
        self,
        train_rows: Sequence[Mapping[str, object]] | None,
        recent_rows: Sequence[Mapping[str, object]] | None,
        features: Sequence[str] | None = None,
    ) -> list[FeatureDriftMetric]:
        """Return per-feature drift metrics without crashing on sparse inputs."""
        if not train_rows or not recent_rows:
            return []
        selected_features = list(features) if features else _numeric_features(train_rows, recent_rows)
        metrics: list[FeatureDriftMetric] = []
        for feature in selected_features:
            train_values = _numeric_values(train_rows, feature)
            recent_values = _numeric_values(recent_rows, feature)
            if len(train_values) < 5 or len(recent_values) < 5:
                continue
            psi_value = population_stability_index(train_values, recent_values)
            ks_stat, ks_pvalue = ks_test(train_values, recent_values)
            ks_score = 0.0
            if ks_pvalue is not None and ks_pvalue < self._ks_pvalue_threshold:
                ks_score = _clip01(1.0 - ks_pvalue)
            psi_score = 0.0
            if psi_value >= self._psi_high_threshold:
                psi_score = 1.0
            elif psi_value >= self._psi_medium_threshold:
                psi_score = _clip01((psi_value - self._psi_medium_threshold) / max(1e-9, self._psi_high_threshold - self._psi_medium_threshold))
            drift_score = _clip01(max(psi_score, ks_score))
            drifted = psi_value >= self._psi_medium_threshold or (ks_pvalue is not None and ks_pvalue < self._ks_pvalue_threshold)
            metrics.append(
                FeatureDriftMetric(
                    feature=feature,
                    psi=round(psi_value, 8),
                    ks_stat=(round(float(ks_stat), 8) if ks_stat is not None else None),
                    ks_pvalue=(round(float(ks_pvalue), 8) if ks_pvalue is not None else None),
                    drift_score=round(drift_score, 8),
                    drifted=drifted,
                )
            )
        return metrics


@dataclass(frozen=True)
class DriftDetectionReport:
    """Unified drift summary for feature, prediction, calibration, and regime drift."""

    feature_metrics: list[dict[str, object]] = field(default_factory=list)
    prediction_distribution_shift: dict[str, object] = field(default_factory=dict)
    calibration_drift: dict[str, object] = field(default_factory=dict)
    regime_drift: dict[str, object] = field(default_factory=dict)
    drift_score: float = 0.0
    drifted: bool = False
    metadata: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "feature_metrics": list(self.feature_metrics),
            "prediction_distribution_shift": dict(self.prediction_distribution_shift),
            "calibration_drift": dict(self.calibration_drift),
            "regime_drift": dict(self.regime_drift),
            "drift_score": self.drift_score,
            "drifted": self.drifted,
            "metadata": dict(self.metadata),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)


class DriftDetector:
    """Facade for platform drift checks while preserving the feature detector API."""

    def __init__(
        self,
        feature_detector: FeatureDriftDetector | None = None,
        calibration_monitor: CalibrationMonitor | None = None,
        drift_threshold: float = 0.20,
    ) -> None:
        self._feature_detector = feature_detector or FeatureDriftDetector()
        self._calibration_monitor = calibration_monitor or CalibrationMonitor()
        self._drift_threshold = _clip01(drift_threshold)

    def detect(
        self,
        baseline_features: Sequence[Mapping[str, object]] | None = None,
        recent_features: Sequence[Mapping[str, object]] | None = None,
        baseline_predictions: Sequence[Mapping[str, object]] | None = None,
        recent_predictions: Sequence[Mapping[str, object]] | None = None,
        baseline_calibration: Sequence[Mapping[str, object]] | None = None,
        recent_calibration: Sequence[Mapping[str, object]] | None = None,
        baseline_regimes: Mapping[str, float | int] | None = None,
        recent_regimes: Mapping[str, float | int] | None = None,
        features: Sequence[str] | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> DriftDetectionReport:
        """Detect available drift dimensions and tolerate missing optional inputs."""
        feature_metrics = self._feature_detector.detect(
            train_rows=baseline_features,
            recent_rows=recent_features,
            features=features,
        )
        feature_payload = [metric.to_dict() for metric in feature_metrics]
        feature_score = max((float(metric.drift_score) for metric in feature_metrics), default=0.0)
        prediction_shift = prediction_distribution_shift(
            baseline_predictions=baseline_predictions,
            recent_predictions=recent_predictions,
        )
        calibration_drift_payload = self._calibration_monitor.evaluate(
            baseline_records=baseline_calibration,
            recent_records=recent_calibration,
        ).to_dict()
        regime_shift = regime_drift(
            baseline_regimes=baseline_regimes,
            recent_regimes=recent_regimes,
        )
        drift_score = _clip01(
            max(
                feature_score,
                float(prediction_shift.get("score", 0.0)),
                float(calibration_drift_payload.get("score", 0.0)),
                float(regime_shift.get("score", 0.0)),
            )
        )
        return DriftDetectionReport(
            feature_metrics=feature_payload,
            prediction_distribution_shift=prediction_shift,
            calibration_drift=calibration_drift_payload,
            regime_drift=regime_shift,
            drift_score=round(drift_score, 8),
            drifted=drift_score >= self._drift_threshold,
            metadata=dict(metadata or {}),
        )


def prediction_distribution_shift(
    baseline_predictions: Sequence[Mapping[str, object]] | None,
    recent_predictions: Sequence[Mapping[str, object]] | None,
) -> dict[str, object]:
    """Compare signal and probability distributions between two prediction windows."""
    baseline = list(baseline_predictions or [])
    recent = list(recent_predictions or [])
    if not baseline or not recent:
        return {
            "distribution_shift": 0.0,
            "probability_shift": 0.0,
            "score": 0.0,
        }
    baseline_distribution = _signal_distribution(baseline)
    recent_distribution = _signal_distribution(recent)
    distribution_shift = _total_variation(baseline_distribution, recent_distribution)
    baseline_probabilities = _mean_probabilities(baseline)
    recent_probabilities = _mean_probabilities(recent)
    probability_shift = _total_variation(baseline_probabilities, recent_probabilities)
    return {
        "distribution_shift": round(distribution_shift, 8),
        "probability_shift": round(probability_shift, 8),
        "baseline_distribution": baseline_distribution,
        "recent_distribution": recent_distribution,
        "baseline_mean_probabilities": baseline_probabilities,
        "recent_mean_probabilities": recent_probabilities,
        "score": round(_clip01(max(distribution_shift, probability_shift) / 0.35), 8),
    }


def regime_drift(
    baseline_regimes: Mapping[str, float | int] | None,
    recent_regimes: Mapping[str, float | int] | None,
) -> dict[str, object]:
    """Compare market regime distributions using total variation distance."""
    if not baseline_regimes or not recent_regimes:
        return {"shift": 0.0, "score": 0.0}
    baseline_distribution = _normalize_counts(baseline_regimes)
    recent_distribution = _normalize_counts(recent_regimes)
    shift = _total_variation(baseline_distribution, recent_distribution)
    return {
        "baseline_distribution": baseline_distribution,
        "recent_distribution": recent_distribution,
        "shift": round(shift, 8),
        "score": round(_clip01(shift / 0.30), 8),
    }


def population_stability_index(
    baseline: Sequence[float],
    recent: Sequence[float],
    bins: int = 10,
) -> float:
    """Calculate PSI between two numeric distributions."""
    if not baseline or not recent:
        return 0.0
    bucket_count = max(2, int(bins))
    edges = _quantile_edges(list(baseline), bucket_count)
    if len(edges) < 2:
        return 0.0
    expected = _histogram(baseline, edges)
    actual = _histogram(recent, edges)
    epsilon = 1e-9
    psi = 0.0
    for exp, act in zip(expected, actual, strict=False):
        e = max(exp, epsilon)
        a = max(act, epsilon)
        psi += (a - e) * log(a / e)
    return float(max(0.0, psi))


def ks_test(
    baseline: Sequence[float],
    recent: Sequence[float],
) -> tuple[float | None, float | None]:
    """Return KS statistic and p-value when scipy is available."""
    try:
        from scipy.stats import ks_2samp  # type: ignore
    except Exception:
        return None, None
    try:
        result = ks_2samp(list(baseline), list(recent))
    except Exception:
        return None, None
    return float(result.statistic), float(result.pvalue)


def _numeric_features(
    baseline_rows: Sequence[Mapping[str, object]],
    recent_rows: Sequence[Mapping[str, object]],
) -> list[str]:
    keys = set()
    for row in list(baseline_rows)[:5] + list(recent_rows)[:5]:
        keys.update(str(key) for key in row.keys())
    features: list[str] = []
    for key in sorted(keys):
        baseline_values = _numeric_values(baseline_rows, key)
        recent_values = _numeric_values(recent_rows, key)
        if baseline_values and recent_values:
            features.append(key)
    return features


def _numeric_values(rows: Sequence[Mapping[str, object]], key: str) -> list[float]:
    values: list[float] = []
    for row in rows:
        if key not in row:
            continue
        try:
            value = float(row[key])
        except (TypeError, ValueError):
            continue
        if isfinite(value):
            values.append(value)
    return values


def _quantile_edges(values: list[float], bins: int) -> list[float]:
    if not values:
        return []
    sorted_values = sorted(values)
    edges = [sorted_values[0]]
    for index in range(1, bins):
        rank = int(round((len(sorted_values) - 1) * index / bins))
        edges.append(sorted_values[rank])
    edges.append(sorted_values[-1])
    deduped: list[float] = [edges[0]]
    for edge in edges[1:]:
        if edge > deduped[-1]:
            deduped.append(edge)
    if len(deduped) == 1:
        deduped.append(deduped[0] + 1e-9)
    return deduped


def _histogram(values: Sequence[float], edges: Sequence[float]) -> list[float]:
    counts = [0] * (len(edges) - 1)
    if not values:
        return [0.0 for _ in counts]
    for value in values:
        placed = False
        for idx in range(len(edges) - 1):
            left = edges[idx]
            right = edges[idx + 1]
            if idx == len(edges) - 2:
                if left <= value <= right:
                    counts[idx] += 1
                    placed = True
                    break
            elif left <= value < right:
                counts[idx] += 1
                placed = True
                break
        if not placed and value < edges[0]:
            counts[0] += 1
        elif not placed:
            counts[-1] += 1
    total = float(len(values))
    return [count / total for count in counts]


def _signal_distribution(rows: Sequence[Mapping[str, object]]) -> dict[str, float]:
    counts = {"BUY": 0.0, "SELL": 0.0, "WAIT": 0.0}
    total = 0.0
    for row in rows:
        signal = row.get("signal")
        if signal is None:
            probabilities = row.get("probabilities")
            if isinstance(probabilities, Mapping):
                parsed = _parse_probabilities(probabilities)
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
    totals = {"BUY": 0.0, "SELL": 0.0, "WAIT": 0.0}
    used = 0
    for row in rows:
        probabilities = row.get("probabilities")
        if not isinstance(probabilities, Mapping):
            continue
        parsed = _parse_probabilities(probabilities)
        if not parsed:
            continue
        used += 1
        for key in totals:
            totals[key] += parsed.get(key, 0.0)
    if used <= 0:
        return {key: 0.0 for key in totals}
    return {key: round(value / used, 8) for key, value in totals.items()}


def _parse_probabilities(payload: Mapping[str, object]) -> dict[str, float]:
    parsed: dict[str, float] = {}
    for key in ("BUY", "SELL", "WAIT"):
        try:
            parsed[key] = max(0.0, float(payload.get(key, 0.0)))
        except (TypeError, ValueError):
            parsed[key] = 0.0
    return parsed


def _normalize_counts(counts: Mapping[str, float | int]) -> dict[str, float]:
    normalized: dict[str, float] = {}
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
        return {key: 0.0 for key in sorted(normalized)}
    return {key: round(normalized[key] / total, 8) for key in sorted(normalized)}


def _total_variation(left: Mapping[str, float], right: Mapping[str, float]) -> float:
    keys = set(left.keys()) | set(right.keys())
    return 0.5 * sum(abs(float(left.get(key, 0.0)) - float(right.get(key, 0.0))) for key in keys)


def _clip01(value: float) -> float:
    return max(0.0, min(float(value), 1.0))
