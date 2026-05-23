"""Feature drift detection utilities."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite, log
from typing import Any, Mapping, Sequence


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


def _clip01(value: float) -> float:
    return max(0.0, min(float(value), 1.0))
