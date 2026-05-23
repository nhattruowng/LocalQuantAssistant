"""Calibration drift monitoring helpers."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite, log
from typing import Mapping, Sequence


@dataclass(frozen=True)
class CalibrationShift:
    """Calibration change summary between baseline and recent windows."""

    brier_before: float | None
    brier_recent: float | None
    brier_delta: float
    logloss_before: float | None
    logloss_recent: float | None
    logloss_delta: float
    score: float

    def to_dict(self) -> dict[str, object]:
        return {
            "brier_before": self.brier_before,
            "brier_recent": self.brier_recent,
            "brier_delta": self.brier_delta,
            "logloss_before": self.logloss_before,
            "logloss_recent": self.logloss_recent,
            "logloss_delta": self.logloss_delta,
            "score": self.score,
        }


class CalibrationMonitor:
    """Compute calibration drift score over time windows."""

    def __init__(
        self,
        brier_high_threshold: float = 0.06,
        logloss_high_threshold: float = 0.15,
    ) -> None:
        self._brier_high_threshold = max(1e-9, float(brier_high_threshold))
        self._logloss_high_threshold = max(1e-9, float(logloss_high_threshold))

    def evaluate(
        self,
        baseline_records: Sequence[Mapping[str, object]] | None,
        recent_records: Sequence[Mapping[str, object]] | None,
    ) -> CalibrationShift:
        """Return calibration shift without crashing when labels are missing."""
        base_brier, base_logloss = _scores(baseline_records or [])
        recent_brier, recent_logloss = _scores(recent_records or [])
        brier_delta = _delta(base_brier, recent_brier)
        logloss_delta = _delta(base_logloss, recent_logloss)
        brier_score = _clip01(brier_delta / self._brier_high_threshold)
        logloss_score = _clip01(logloss_delta / self._logloss_high_threshold)
        return CalibrationShift(
            brier_before=base_brier,
            brier_recent=recent_brier,
            brier_delta=round(brier_delta, 8),
            logloss_before=base_logloss,
            logloss_recent=recent_logloss,
            logloss_delta=round(logloss_delta, 8),
            score=round(max(brier_score, logloss_score), 8),
        )


def _scores(records: Sequence[Mapping[str, object]]) -> tuple[float | None, float | None]:
    entries: list[tuple[str, dict[str, float]]] = []
    for row in records:
        label = str(row.get("label", "")).upper()
        probs_raw = row.get("probabilities")
        if not label or not isinstance(probs_raw, Mapping):
            continue
        probs: dict[str, float] = {}
        for key, value in probs_raw.items():
            try:
                probs[str(key).upper()] = float(value)
            except (TypeError, ValueError):
                continue
        if not probs:
            continue
        entries.append((label, probs))
    if not entries:
        return None, None

    labels = sorted({key for _, probs in entries for key in probs.keys()} | {"BUY", "SELL", "WAIT"})
    brier_values: list[float] = []
    logloss_values: list[float] = []
    epsilon = 1e-12
    for label, probs in entries:
        sum_sq = 0.0
        for candidate in labels:
            predicted = probs.get(candidate, 0.0)
            actual = 1.0 if candidate == label else 0.0
            sum_sq += (predicted - actual) ** 2
        brier_values.append(sum_sq / max(1, len(labels)))
        p_true = max(epsilon, min(1.0 - epsilon, probs.get(label, 0.0)))
        logloss_values.append(-log(p_true))

    brier = sum(brier_values) / len(brier_values)
    logloss = sum(logloss_values) / len(logloss_values)
    return (round(brier, 8), round(logloss, 8))


def _delta(before: float | None, after: float | None) -> float:
    if before is None or after is None:
        return 0.0
    if not isfinite(before) or not isfinite(after):
        return 0.0
    return max(0.0, after - before)


def _clip01(value: float) -> float:
    return max(0.0, min(float(value), 1.0))
