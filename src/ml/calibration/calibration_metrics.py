"""Calibration metrics and reliability curve data."""

from __future__ import annotations

from typing import Any, Sequence

import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, log_loss


def calibration_report(
    y_true: pd.Series | Sequence[str],
    classes: Sequence[str],
    probabilities: np.ndarray,
    n_bins: int = 10,
) -> dict[str, Any]:
    """Build JSON-safe calibration diagnostics for multiclass probabilities."""
    labels = [str(label) for label in classes]
    y_values = pd.Series(y_true).astype(str).reset_index(drop=True)
    probability_values = np.asarray(probabilities, dtype=float)
    if probability_values.ndim != 2 or probability_values.shape[1] != len(labels):
        raise ValueError("Probabilities must be a 2D array aligned with classes.")

    per_class_brier = _per_class_brier(y_values, labels, probability_values)
    return {
        "brier_score": float(np.mean(list(per_class_brier.values()))),
        "log_loss": _safe_log_loss(y_values, labels, probability_values),
        "expected_calibration_error": expected_calibration_error(
            y_values,
            labels,
            probability_values,
            n_bins=n_bins,
        ),
        "per_class_brier_score": per_class_brier,
        "reliability_curve": reliability_curve_data(
            y_values,
            labels,
            probability_values,
            n_bins=n_bins,
        ),
        "probability_histogram": probability_histogram(
            labels,
            probability_values,
            n_bins=n_bins,
        ),
    }


def expected_calibration_error(
    y_true: pd.Series,
    classes: Sequence[str],
    probabilities: np.ndarray,
    n_bins: int = 10,
) -> float:
    """Return one-vs-rest weighted ECE averaged across classes."""
    total = 0.0
    labels = [str(label) for label in classes]
    for class_index, label in enumerate(labels):
        class_probability = probabilities[:, class_index]
        class_actual = (y_true == label).astype(float).to_numpy()
        total += _binary_ece(class_actual, class_probability, n_bins)
    return float(total / max(len(labels), 1))


def reliability_curve_data(
    y_true: pd.Series,
    classes: Sequence[str],
    probabilities: np.ndarray,
    n_bins: int = 10,
) -> dict[str, list[dict[str, float | int]]]:
    """Return per-class reliability curve bins."""
    curves: dict[str, list[dict[str, float | int]]] = {}
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    labels = [str(label) for label in classes]
    for class_index, label in enumerate(labels):
        class_probability = probabilities[:, class_index]
        class_actual = (y_true == label).astype(float).to_numpy()
        bins = _bin_indices(class_probability, n_bins)
        points: list[dict[str, float | int]] = []
        for bin_index in range(n_bins):
            mask = bins == bin_index
            count = int(mask.sum())
            if count == 0:
                mean_probability = 0.0
                observed_frequency = 0.0
            else:
                mean_probability = float(class_probability[mask].mean())
                observed_frequency = float(class_actual[mask].mean())
            points.append(
                {
                    "bin_start": float(edges[bin_index]),
                    "bin_end": float(edges[bin_index + 1]),
                    "mean_predicted_probability": mean_probability,
                    "observed_frequency": observed_frequency,
                    "count": count,
                }
            )
        curves[label] = points
    return curves


def probability_histogram(
    classes: Sequence[str],
    probabilities: np.ndarray,
    n_bins: int = 10,
) -> dict[str, list[dict[str, float | int]]]:
    """Return per-class probability histogram counts."""
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    histograms: dict[str, list[dict[str, float | int]]] = {}
    for class_index, label in enumerate(classes):
        counts, _ = np.histogram(probabilities[:, class_index], bins=edges)
        histograms[str(label)] = [
            {
                "bin_start": float(edges[index]),
                "bin_end": float(edges[index + 1]),
                "count": int(count),
            }
            for index, count in enumerate(counts)
        ]
    return histograms


def _per_class_brier(
    y_true: pd.Series,
    classes: Sequence[str],
    probabilities: np.ndarray,
) -> dict[str, float]:
    """Return one-vs-rest Brier score for each class."""
    return {
        label: float(
            brier_score_loss(
                (y_true == label).astype(int),
                probabilities[:, class_index],
            )
        )
        for class_index, label in enumerate(classes)
    }


def _safe_log_loss(
    y_true: pd.Series,
    classes: Sequence[str],
    probabilities: np.ndarray,
) -> float:
    """Return multiclass log loss with clipping for numeric stability."""
    clipped = np.clip(probabilities, 1e-15, 1.0 - 1e-15)
    normalized = clipped / clipped.sum(axis=1, keepdims=True)
    return float(log_loss(y_true, normalized, labels=list(classes)))


def _binary_ece(actual: np.ndarray, probabilities: np.ndarray, n_bins: int) -> float:
    """Return weighted binary expected calibration error."""
    bins = _bin_indices(probabilities, n_bins)
    total = 0.0
    row_count = len(probabilities)
    if row_count == 0:
        return 0.0
    for bin_index in range(n_bins):
        mask = bins == bin_index
        count = int(mask.sum())
        if count == 0:
            continue
        total += count / row_count * abs(
            float(probabilities[mask].mean()) - float(actual[mask].mean())
        )
    return float(total)


def _bin_indices(probabilities: np.ndarray, n_bins: int) -> np.ndarray:
    """Map probabilities to stable [0, n_bins) bin indices."""
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    indices = np.digitize(probabilities, edges[1:-1], right=False)
    return np.clip(indices, 0, n_bins - 1)
