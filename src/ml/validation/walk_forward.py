"""Walk-forward validation fold generation."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from config.settings import TrainingValidationSettings
from ml.validation.purged_cv import PurgedFold, apply_purge_and_embargo


@dataclass(frozen=True)
class WalkForwardSplit:
    """Collection of chronological walk-forward folds."""

    folds: list[PurgedFold]

    def to_metadata(self, dataset: pd.DataFrame) -> list[dict[str, object]]:
        """Return serializable metadata for every fold."""
        return [fold.to_metadata(dataset) for fold in self.folds]


class WalkForwardValidator:
    """Creates expanding or rolling walk-forward validation folds."""

    def __init__(
        self,
        settings: TrainingValidationSettings,
        purge_size: int,
    ) -> None:
        self._settings = settings
        self._purge_size = purge_size

    def split(self, dataset: pd.DataFrame) -> WalkForwardSplit:
        """Create chronological train/validation folds."""
        if dataset.empty:
            raise ValueError("Dataset must not be empty.")
        data = dataset.reset_index(drop=True)
        folds: list[PurgedFold] = []
        train_window = self._settings.train_window_bars
        validation_window = self._settings.validation_window_bars

        for fold_id in range(self._settings.n_splits):
            if self._settings.expanding_window:
                train_start = 0
                train_end = train_window + fold_id * validation_window
            else:
                train_start = fold_id * validation_window
                train_end = train_start + train_window

            validation_start = train_end
            validation_end = validation_start + validation_window
            if validation_end > len(data):
                break

            train_indices = list(range(train_start, train_end))
            validation_indices = list(range(validation_start, validation_end))
            folds.append(
                apply_purge_and_embargo(
                    fold_id=fold_id,
                    train_indices=train_indices,
                    validation_indices=validation_indices,
                    purge_size=self._purge_size,
                    embargo_size=self._settings.embargo_size,
                )
            )

        if not folds:
            raise ValueError("No walk-forward folds could be created with current settings.")
        return WalkForwardSplit(folds=folds)
