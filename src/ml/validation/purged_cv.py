"""Purged train/validation splitting helpers."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class PurgedFold:
    """A train/validation fold after purge and embargo rules."""

    fold_id: int
    train_indices: list[int]
    validation_indices: list[int]
    train_start: int
    train_end: int
    validation_start: int
    validation_end: int
    purge_size: int
    embargo_size: int

    def to_metadata(self, dataset: pd.DataFrame) -> dict[str, object]:
        """Return timestamp-aware fold metadata."""
        return {
            "fold_id": self.fold_id,
            "train_rows": len(self.train_indices),
            "validation_rows": len(self.validation_indices),
            "train_start_index": self.train_start,
            "train_end_index": self.train_end - 1,
            "validation_start_index": self.validation_start,
            "validation_end_index": self.validation_end - 1,
            "train_start": _timestamp_at(dataset, self.train_indices[0]),
            "train_end": _timestamp_at(dataset, self.train_indices[-1]),
            "validation_start": _timestamp_at(dataset, self.validation_indices[0]),
            "validation_end": _timestamp_at(dataset, self.validation_indices[-1]),
            "purge_size": self.purge_size,
            "embargo_size": self.embargo_size,
        }


class PurgedTimeSeriesSplit:
    """Creates chronological CV folds with purge and embargo leakage guards."""

    def __init__(
        self,
        n_splits: int,
        purge_size: int,
        embargo_size: int = 0,
    ) -> None:
        if n_splits <= 0:
            raise ValueError("n_splits must be positive.")
        if purge_size < 0 or embargo_size < 0:
            raise ValueError("Purge and embargo sizes must be non-negative.")
        self._n_splits = n_splits
        self._purge_size = purge_size
        self._embargo_size = embargo_size

    def split(self, dataset: pd.DataFrame) -> list[PurgedFold]:
        """Return purged folds where validation blocks move forward in time."""
        if dataset.empty:
            raise ValueError("Dataset must not be empty.")
        row_count = len(dataset)
        validation_window = row_count // (self._n_splits + 1)
        if validation_window <= 0:
            raise ValueError("Not enough rows to create purged CV folds.")

        folds: list[PurgedFold] = []
        for fold_id in range(self._n_splits):
            validation_start = validation_window * (fold_id + 1)
            validation_end = (
                row_count
                if fold_id == self._n_splits - 1
                else validation_start + validation_window
            )
            if validation_start >= row_count or validation_end <= validation_start:
                break
            validation_indices = list(range(validation_start, validation_end))
            train_indices = [
                index
                for index in range(row_count)
                if index < validation_start or index >= validation_end
            ]
            folds.append(
                apply_purge_and_embargo(
                    fold_id=fold_id,
                    train_indices=train_indices,
                    validation_indices=validation_indices,
                    purge_size=self._purge_size,
                    embargo_size=self._embargo_size,
                )
            )

        if not folds:
            raise ValueError("No purged CV folds could be created.")
        return folds


def apply_purge_and_embargo(
    fold_id: int,
    train_indices: list[int],
    validation_indices: list[int],
    purge_size: int,
    embargo_size: int = 0,
) -> PurgedFold:
    """Remove train rows near validation boundaries to reduce label leakage."""
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
    )


def _timestamp_at(dataset: pd.DataFrame, index: int) -> str | int:
    """Return timestamp value when available, otherwise the integer index."""
    if "timestamp" not in dataset:
        return index
    value = dataset.iloc[index]["timestamp"]
    return value.isoformat() if hasattr(value, "isoformat") else str(value)
