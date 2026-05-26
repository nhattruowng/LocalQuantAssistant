"""Tests for walk-forward and purged time-series validation."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

pd = pytest.importorskip("pandas")

from dataclasses import replace

from config.settings import TrainingValidationSettings
from ml.model_trainer import ModelTrainer
from ml.validation.purged_cv import (
    PurgedFold,
    PurgedTimeSeriesSplit,
    apply_purge_and_embargo,
    build_validation_metadata,
    validate_chronological_folds,
)
from ml.validation.walk_forward import WalkForwardValidator


def test_walk_forward_creates_expected_number_of_folds():
    validator = WalkForwardValidator(
        settings=TrainingValidationSettings(
            method="walk_forward",
            n_splits=3,
            train_window_bars=10,
            validation_window_bars=5,
            test_window_bars=0,
            expanding_window=True,
            purge_size=0,
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
            test_window_bars=0,
            expanding_window=True,
            purge_size=0,
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


def test_purged_cv_splits_use_past_only_train_without_overlap():
    folds = PurgedTimeSeriesSplit(
        n_splits=2,
        validation_window_bars=5,
        train_window_bars=12,
        test_window_bars=0,
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
        assert max(train) < min(validation)
        assert list(train) == sorted(train)
        assert list(validation) == sorted(validation)


def test_walk_forward_with_test_window_creates_test_indices():
    validator = WalkForwardValidator(
        settings=TrainingValidationSettings(
            method="walk_forward",
            n_splits=2,
            train_window_bars=10,
            validation_window_bars=4,
            test_window_bars=3,
            expanding_window=False,
            purge_size=1,
            embargo_size=0,
        ),
        purge_size=1,
    )
    split = validator.split(_dataset(30))

    assert split.folds[0].test_indices == [14, 15, 16]
    assert split.folds[1].test_indices == [21, 22, 23]


def test_validation_timestamps_are_after_train_timestamps():
    validator = WalkForwardValidator(
        settings=TrainingValidationSettings(
            method="walk_forward",
            n_splits=3,
            train_window_bars=10,
            validation_window_bars=5,
            test_window_bars=0,
            expanding_window=False,
            purge_size=0,
        ),
        purge_size=1,
    )
    data = _dataset(35)

    split = validator.split(data)

    for fold in split.folds:
        train_end = data.iloc[max(fold.train_indices)]["timestamp"]
        validation_start = data.iloc[min(fold.validation_indices)]["timestamp"]
        assert validation_start > train_end


def test_fold_metadata_contains_purge_and_embargo():
    data = _dataset(25)
    fold = PurgedTimeSeriesSplit(
        n_splits=1,
        validation_window_bars=5,
        train_window_bars=12,
        purge_size=3,
        embargo_size=2,
    ).split(data)[0]
    metadata = fold.to_metadata(data)

    assert metadata["purge_size"] == 3
    assert metadata["embargo_size"] == 2
    assert metadata["validation_method"] == "purged_cv"
    assert metadata["validation_start_index"] is not None


def test_purged_cv_can_use_lookahead_bars_as_purge_size():
    fold = PurgedTimeSeriesSplit(
        n_splits=1,
        validation_window_bars=10,
        train_window_bars=12,
        purge_size=None,
        lookahead_bars=4,
        embargo_size=0,
    ).split(_dataset(30))[0]

    assert fold.purge_size == 4
    assert fold.validation_start - 1 not in fold.train_indices
    assert fold.validation_start - 4 not in fold.train_indices
    assert fold.validation_start - 5 in fold.train_indices


def test_walk_forward_summary_metadata_contains_required_fields():
    data = _dataset(35)
    validator = WalkForwardValidator(
        settings=TrainingValidationSettings(
            method="walk_forward",
            n_splits=2,
            train_window_bars=10,
            validation_window_bars=5,
            test_window_bars=2,
            expanding_window=True,
            purge_size=0,
            embargo_size=1,
        ),
        purge_size=3,
    )
    split = validator.split(data)
    metadata = split.to_summary_metadata(
        data,
        fold_metrics=[
            {"fold_id": 0, "accuracy": 0.62},
            {"fold_id": 1, "accuracy": 0.51},
        ],
    )

    assert metadata["validation_method"] == "walk_forward"
    assert metadata["purge_size"] == 3
    assert metadata["embargo_size"] == 1
    assert metadata["worst_fold_metric"] == 0.51
    assert metadata["dataset_start"] is not None
    assert metadata["dataset_end"] is not None
    assert len(metadata["fold_metrics"]) == 2
    assert metadata["folds"][0]["validation_method"] == "walk_forward"


def test_validation_metadata_builder_handles_empty_fold_metrics():
    data = _dataset(25)
    folds = PurgedTimeSeriesSplit(
        n_splits=1,
        validation_window_bars=5,
        train_window_bars=12,
        purge_size=3,
        embargo_size=2,
    ).split(data)

    metadata = build_validation_metadata(
        dataset=data,
        folds=folds,
        validation_method="purged_cv",
    )

    assert metadata["fold_metrics"] == []
    assert metadata["worst_fold_metric"] is None
    assert metadata["dataset_start"] is not None
    assert metadata["dataset_end"] is not None


def test_chronological_validation_rejects_overlap():
    with pytest.raises(ValueError, match="overlap"):
        validate_chronological_folds(
            [
                PurgedFold(
                    fold_id=0,
                    train_indices=[0, 1, 2],
                    validation_indices=[2, 3, 4],
                )
            ]
        )


def test_model_trainer_validation_metadata_for_purged_cv(settings):
    trainer = ModelTrainer(
        settings=replace(
            settings,
            training=replace(
                settings.training,
                validation=replace(
                    settings.training.validation,
                    method="purged_cv",
                    purge_size=7,
                    embargo_size=3,
                    test_window_bars=5,
                ),
            ),
        )
    )
    metadata = trainer._validation_metadata(_dataset(40))

    assert metadata["validation_method"] == "purged_cv"
    assert metadata["purge_size"] == 7
    assert metadata["embargo_size"] == 3
    assert metadata["fold_metrics"] == []
    assert metadata["worst_fold_metric"] is None
    assert metadata["validation_test_window_bars"] == 5
    assert metadata["dataset_start"] is not None
    assert metadata["dataset_end"] is not None


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
