"""Tests for walk-forward and purged time-series validation."""

from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd

from config.settings import TrainingValidationSettings
from ml.validation.purged_cv import PurgedTimeSeriesSplit, apply_purge_and_embargo
from ml.validation.walk_forward import WalkForwardValidator


def test_walk_forward_creates_expected_number_of_folds():
    validator = WalkForwardValidator(
        settings=TrainingValidationSettings(
            method="walk_forward",
            n_splits=3,
            train_window_bars=10,
            validation_window_bars=5,
            expanding_window=True,
        ),
        purge_size=2,
    )

    split = validator.split(_dataset(30))

    assert len(split.folds) == 3


def test_walk_forward_folds_do_not_overlap_after_purge():
    validator = WalkForwardValidator(
        settings=TrainingValidationSettings(
            method="walk_forward",
            n_splits=2,
            train_window_bars=10,
            validation_window_bars=5,
            expanding_window=True,
        ),
        purge_size=2,
    )

    fold = validator.split(_dataset(25)).folds[0]

    assert set(fold.train_indices).isdisjoint(fold.validation_indices)
    assert max(fold.train_indices) < min(fold.validation_indices)
    assert 8 not in fold.train_indices
    assert 9 not in fold.train_indices


def test_purge_removes_train_rows_before_validation_boundary():
    fold = apply_purge_and_embargo(
        fold_id=0,
        train_indices=list(range(15)),
        validation_indices=list(range(10, 15)),
        purge_size=3,
    )

    assert 7 not in fold.train_indices
    assert 8 not in fold.train_indices
    assert 9 not in fold.train_indices
    assert 6 in fold.train_indices


def test_embargo_removes_train_rows_after_validation_boundary():
    fold = apply_purge_and_embargo(
        fold_id=0,
        train_indices=list(range(25)),
        validation_indices=list(range(10, 15)),
        purge_size=0,
        embargo_size=3,
    )

    assert 15 not in fold.train_indices
    assert 16 not in fold.train_indices
    assert 17 not in fold.train_indices
    assert 18 in fold.train_indices


def test_purged_cv_splits_train_on_both_sides_without_overlap():
    folds = PurgedTimeSeriesSplit(
        n_splits=2,
        purge_size=2,
        embargo_size=1,
    ).split(_dataset(30))

    assert len(folds) == 2
    for fold in folds:
        validation = set(fold.validation_indices)
        train = set(fold.train_indices)
        assert train.isdisjoint(validation)
        assert fold.validation_start - 1 not in train
        assert fold.validation_start - 2 not in train
        assert fold.validation_end not in train


def test_validation_timestamps_are_after_train_timestamps():
    validator = WalkForwardValidator(
        settings=TrainingValidationSettings(
            method="walk_forward",
            n_splits=3,
            train_window_bars=10,
            validation_window_bars=5,
            expanding_window=False,
        ),
        purge_size=1,
    )
    data = _dataset(35)

    split = validator.split(data)

    for fold in split.folds:
        train_end = data.iloc[max(fold.train_indices)]["timestamp"]
        validation_start = data.iloc[min(fold.validation_indices)]["timestamp"]
        assert validation_start > train_end


def _dataset(rows: int) -> pd.DataFrame:
    """Build a timestamped dummy dataset."""
    labels = (["BUY", "SELL", "WAIT", "BUY", "SELL"] * ((rows // 5) + 1))[:rows]
    return pd.DataFrame(
        {
            "timestamp": pd.date_range(
                datetime(2026, 1, 1, tzinfo=UTC),
                periods=rows,
                freq="h",
            ),
            "feature": range(rows),
            "label": labels,
        }
    )
