"""Purged/embargo-aware chronological validation splitters."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class PurgedFold:
    """One chronological train/validation (and optional test) fold."""

    fold_id: int
    train_indices: list[int]
    validation_indices: list[int]
    test_indices: list[int] = field(default_factory=list)
    train_start: int = 0
    train_end: int = 0
    validation_start: int = 0
    validation_end: int = 0
    test_start: int | None = None
    test_end: int | None = None
    purge_size: int = 0
    embargo_size: int = 0
    validation_method: str = "purged_cv"

    def to_metadata(self, dataset: pd.DataFrame) -> dict[str, object]:
        """Return timestamp-aware metadata for this fold."""
        train_start_index = self.train_indices[0] if self.train_indices else None
        train_end_index = self.train_indices[-1] if self.train_indices else None
        validation_start_index = self.validation_indices[0] if self.validation_indices else None
        validation_end_index = self.validation_indices[-1] if self.validation_indices else None
        test_start_index = self.test_indices[0] if self.test_indices else None
        test_end_index = self.test_indices[-1] if self.test_indices else None
        return {
            "validation_method": self.validation_method,
            "fold_id": self.fold_id,
            "train_rows": len(self.train_indices),
            "validation_rows": len(self.validation_indices),
            "test_rows": len(self.test_indices),
            "train_start_index": train_start_index,
            "train_end_index": train_end_index,
            "validation_start_index": validation_start_index,
            "validation_end_index": validation_end_index,
            "test_start_index": test_start_index,
            "test_end_index": test_end_index,
            "train_start": _timestamp_at(dataset, train_start_index),
            "train_end": _timestamp_at(dataset, train_end_index),
            "validation_start": _timestamp_at(dataset, validation_start_index),
            "validation_end": _timestamp_at(dataset, validation_end_index),
            "test_start": _timestamp_at(dataset, test_start_index),
            "test_end": _timestamp_at(dataset, test_end_index),
            "purge_size": self.purge_size,
            "embargo_size": self.embargo_size,
        }


class PurgedTimeSeriesSplit:
    """Chronological purged cross-validation without shuffling."""

    def __init__(
        self,
        n_splits: int,
        purge_size: int | None = None,
        embargo_size: int = 0,
        lookahead_bars: int | None = None,
        validation_window_bars: int | None = None,
        train_window_bars: int | None = None,
        test_window_bars: int = 0,
    ) -> None:
        if n_splits <= 0:
            raise ValueError("n_splits must be positive.")
        resolved_purge_size = _resolve_purge_size(purge_size, lookahead_bars)
        if resolved_purge_size < 0 or embargo_size < 0:
            raise ValueError("Purge and embargo sizes must be non-negative.")
        if validation_window_bars is not None and validation_window_bars <= 0:
            raise ValueError("validation_window_bars must be positive when provided.")
        if train_window_bars is not None and train_window_bars <= 0:
            raise ValueError("train_window_bars must be positive when provided.")
        if test_window_bars < 0:
            raise ValueError("test_window_bars must be non-negative.")
        self._n_splits = n_splits
        self._purge_size = resolved_purge_size
        self._embargo_size = embargo_size
        self._validation_window_bars = validation_window_bars
        self._train_window_bars = train_window_bars
        self._test_window_bars = test_window_bars

    def split(self, dataset: pd.DataFrame) -> list[PurgedFold]:
        """Return purged folds with train timestamps strictly before validation."""
        if dataset.empty:
            raise ValueError("Dataset must not be empty.")
        row_count = len(dataset)
        validation_window = self._validation_window_bars or row_count // (self._n_splits + 1)
        if validation_window <= 0:
            raise ValueError("Not enough rows to create purged CV folds.")

        folds: list[PurgedFold] = []
        for fold_id in range(self._n_splits):
            validation_start = validation_window * (fold_id + 1)
            validation_end = validation_start + validation_window
            if validation_end > row_count:
                break

            train_end = validation_start
            if self._train_window_bars is None:
                train_start = 0
            else:
                train_start = max(0, train_end - self._train_window_bars)
            raw_train_indices = list(range(train_start, train_end))
            validation_indices = list(range(validation_start, validation_end))
            if not raw_train_indices or not validation_indices:
                break

            fold = apply_purge_and_embargo(
                fold_id=fold_id,
                train_indices=raw_train_indices,
                validation_indices=validation_indices,
                purge_size=self._purge_size,
                embargo_size=self._embargo_size,
            )
            test_indices = self._test_indices(
                row_count=row_count,
                validation_end=validation_end,
            )
            folds.append(
                PurgedFold(
                    fold_id=fold.fold_id,
                    train_indices=fold.train_indices,
                    validation_indices=fold.validation_indices,
                    test_indices=test_indices,
                    train_start=fold.train_start,
                    train_end=fold.train_end,
                    validation_start=fold.validation_start,
                    validation_end=fold.validation_end,
                    test_start=test_indices[0] if test_indices else None,
                    test_end=(test_indices[-1] + 1) if test_indices else None,
                    purge_size=fold.purge_size,
                    embargo_size=fold.embargo_size,
                    validation_method="purged_cv",
                )
            )

        if not folds:
            raise ValueError("No purged CV folds could be created.")
        validate_chronological_folds(folds)
        return folds

    def _test_indices(self, row_count: int, validation_end: int) -> list[int]:
        if self._test_window_bars <= 0:
            return []
        test_start = validation_end
        test_end = test_start + self._test_window_bars
        if test_end > row_count:
            return []
        return list(range(test_start, test_end))


def apply_purge_and_embargo(
    fold_id: int,
    train_indices: list[int],
    validation_indices: list[int],
    purge_size: int,
    embargo_size: int = 0,
) -> PurgedFold:
    """Remove train rows near validation boundaries to reduce leakage."""
    if not train_indices:
        raise ValueError("Train indices must not be empty.")
    if not validation_indices:
        raise ValueError("Validation indices must not be empty.")
    if purge_size < 0 or embargo_size < 0:
        raise ValueError("Purge and embargo sizes must be non-negative.")

    validation_start = min(validation_indices)
    validation_end = max(validation_indices) + 1
    blocked_start = max(0, validation_start - purge_size)
    blocked_end = validation_end + embargo_size
    purged_train = [
        index
        for index in train_indices
        if not (blocked_start <= index < blocked_end)
    ]
    if not purged_train:
        raise ValueError("Purge/embargo removed all train rows for a fold.")
    return PurgedFold(
        fold_id=fold_id,
        train_indices=purged_train,
        validation_indices=validation_indices,
        train_start=min(train_indices),
        train_end=max(train_indices) + 1,
        validation_start=validation_start,
        validation_end=validation_end,
        purge_size=purge_size,
        embargo_size=embargo_size,
        validation_method="purged_cv",
    )


def validate_chronological_folds(folds: list[PurgedFold]) -> None:
    """Validate strict chronological no-shuffle folds."""
    for fold in folds:
        train = set(fold.train_indices)
        validation = set(fold.validation_indices)
        test = set(fold.test_indices)
        if train & validation:
            raise ValueError(f"Fold {fold.fold_id} has train/validation overlap.")
        if train & test:
            raise ValueError(f"Fold {fold.fold_id} has train/test overlap.")
        if validation & test:
            raise ValueError(f"Fold {fold.fold_id} has validation/test overlap.")
        if fold.train_indices and fold.validation_indices:
            if max(fold.train_indices) >= min(fold.validation_indices):
                raise ValueError(
                    f"Fold {fold.fold_id} has validation timestamps before train ends."
                )
        if fold.validation_indices and fold.test_indices:
            if max(fold.validation_indices) >= min(fold.test_indices):
                raise ValueError(
                    f"Fold {fold.fold_id} has test timestamps before validation ends."
                )


def build_validation_metadata(
    dataset: pd.DataFrame,
    folds: list[PurgedFold],
    validation_method: str,
    fold_metrics: list[dict[str, Any]] | None = None,
    metric_key: str = "accuracy",
) -> dict[str, Any]:
    """Build metadata shared by walk-forward and purged validation reports."""
    metrics = list(fold_metrics or [])
    purge_size = max((fold.purge_size for fold in folds), default=0)
    embargo_size = max((fold.embargo_size for fold in folds), default=0)
    return {
        "validation_method": validation_method,
        "folds": [fold.to_metadata(dataset) for fold in folds],
        "fold_metrics": metrics,
        "purge_size": purge_size,
        "embargo_size": embargo_size,
        "worst_fold_metric": _worst_fold_metric(metrics, metric_key),
        "dataset_start": _timestamp_at(dataset, 0 if not dataset.empty else None),
        "dataset_end": _timestamp_at(dataset, len(dataset) - 1 if not dataset.empty else None),
    }


def _resolve_purge_size(purge_size: int | None, lookahead_bars: int | None) -> int:
    if purge_size is not None:
        return int(purge_size)
    if lookahead_bars is None:
        raise ValueError("purge_size or lookahead_bars is required.")
    return int(lookahead_bars)


def _worst_fold_metric(
    fold_metrics: list[dict[str, Any]],
    metric_key: str,
) -> float | None:
    values: list[float] = []
    for item in fold_metrics:
        if metric_key not in item:
            continue
        try:
            values.append(float(item[metric_key]))
        except (TypeError, ValueError):
            continue
    return min(values) if values else None


def _timestamp_at(dataset: pd.DataFrame, index: int | None) -> str | int | None:
    """Return timestamp value when available, otherwise integer index."""
    if index is None:
        return None
    if "timestamp" not in dataset:
        return index
    value = dataset.iloc[index]["timestamp"]
    return value.isoformat() if hasattr(value, "isoformat") else str(value)
