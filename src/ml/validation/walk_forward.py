"""Walk-forward validation fold generation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from config.settings import TrainingValidationSettings
from ml.validation.purged_cv import (
    PurgedFold,
    apply_purge_and_embargo,
    build_validation_metadata,
    validate_chronological_folds,
)


@dataclass(frozen=True)
class WalkForwardSplit:
    """Collection of chronological walk-forward folds."""

    folds: list[PurgedFold]

    def to_metadata(self, dataset: pd.DataFrame) -> list[dict[str, object]]:
        """Return serializable metadata for every fold."""
        return [fold.to_metadata(dataset) for fold in self.folds]

    def to_summary_metadata(
        self,
        dataset: pd.DataFrame,
        fold_metrics: list[dict[str, Any]] | None = None,
        metric_key: str = "accuracy",
    ) -> dict[str, Any]:
        """Return summary metadata for model registry and research reports."""
        return build_validation_metadata(
            dataset=dataset,
            folds=self.folds,
            validation_method="walk_forward",
            fold_metrics=fold_metrics,
            metric_key=metric_key,
        )


class WalkForwardValidator:
    """Creates expanding (anchored) or rolling walk-forward folds."""

    def __init__(
        self,
        settings: TrainingValidationSettings,
        purge_size: int,
    ) -> None:
        if purge_size < 0:
            raise ValueError("purge_size must be non-negative.")
        self._settings = settings
        self._purge_size = purge_size

    def split(self, dataset: pd.DataFrame) -> WalkForwardSplit:
        """Create chronological train/validation/test folds."""
        if dataset.empty:
            raise ValueError("Dataset must not be empty.")
        data = dataset.reset_index(drop=True)
        folds: list[PurgedFold] = []
        train_window = self._settings.train_window_bars
        validation_window = self._settings.validation_window_bars
        test_window = self._settings.test_window_bars
        stride = validation_window + test_window
        if stride <= 0:
            stride = validation_window

        for fold_id in range(self._settings.n_splits):
            if self._settings.expanding_window:
                train_start = 0
                train_end = train_window + fold_id * stride
            else:
                train_start = fold_id * stride
                train_end = train_start + train_window

            validation_start = train_end
            validation_end = validation_start + validation_window
            if validation_end > len(data):
                break

            train_indices = list(range(train_start, train_end))
            validation_indices = list(range(validation_start, validation_end))
            if not train_indices or not validation_indices:
                break
            base_fold = apply_purge_and_embargo(
                fold_id=fold_id,
                train_indices=train_indices,
                validation_indices=validation_indices,
                purge_size=self._purge_size,
                embargo_size=self._settings.embargo_size,
            )

            test_indices: list[int] = []
            if test_window > 0:
                test_start = validation_end
                test_end = test_start + test_window
                if test_end > len(data):
                    break
                test_indices = list(range(test_start, test_end))

            folds.append(
                PurgedFold(
                    fold_id=base_fold.fold_id,
                    train_indices=base_fold.train_indices,
                    validation_indices=base_fold.validation_indices,
                    test_indices=test_indices,
                    train_start=base_fold.train_start,
                    train_end=base_fold.train_end,
                    validation_start=base_fold.validation_start,
                    validation_end=base_fold.validation_end,
                    test_start=test_indices[0] if test_indices else None,
                    test_end=(test_indices[-1] + 1) if test_indices else None,
                    purge_size=base_fold.purge_size,
                    embargo_size=base_fold.embargo_size,
                    validation_method="walk_forward",
                )
            )

        if not folds:
            raise ValueError("No walk-forward folds could be created with current settings.")
        validate_chronological_folds(folds)
        return WalkForwardSplit(folds=folds)
