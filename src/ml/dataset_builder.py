"""Dataset assembly for time-series model training."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from config.settings import TrainingSettings
from domain.enums import TradingAction


EXCLUDED_FEATURE_COLUMNS = {
    "timestamp",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "label",
    "label_lookahead_complete",
    "regime_reason",
}
TARGET_LABELS = [
    TradingAction.BUY.value,
    TradingAction.SELL.value,
    TradingAction.WAIT.value,
]


@dataclass(frozen=True)
class DatasetSplit:
    """Time-ordered train/validation/test split."""

    x_train: pd.DataFrame
    y_train: pd.Series
    x_validation: pd.DataFrame
    y_validation: pd.Series
    x_test: pd.DataFrame
    y_test: pd.Series
    feature_columns: list[str]


class DatasetBuilder:
    """Builds ML matrices without shuffling time-series rows."""

    def __init__(self, settings: TrainingSettings) -> None:
        self._settings = settings

    def build(self, labeled_features: pd.DataFrame) -> DatasetSplit:
        """Create train/validation/test split from labeled features."""
        self._validate_input(labeled_features)
        dataset = labeled_features.copy(deep=True)
        if "label_lookahead_complete" in dataset:
            dataset = dataset[dataset["label_lookahead_complete"]]
        dataset = dataset[dataset["label"].isin(TARGET_LABELS)]
        feature_columns = self._select_feature_columns(dataset)
        dataset = dataset.dropna(subset=feature_columns + ["label"]).reset_index(drop=True)
        if len(dataset) < 10:
            raise ValueError("Not enough labeled rows after dropping missing feature values.")

        train_end, validation_end = self._split_indices(len(dataset))
        x = dataset[feature_columns]
        y = dataset["label"]
        return DatasetSplit(
            x_train=x.iloc[:train_end].reset_index(drop=True),
            y_train=y.iloc[:train_end].reset_index(drop=True),
            x_validation=x.iloc[train_end:validation_end].reset_index(drop=True),
            y_validation=y.iloc[train_end:validation_end].reset_index(drop=True),
            x_test=x.iloc[validation_end:].reset_index(drop=True),
            y_test=y.iloc[validation_end:].reset_index(drop=True),
            feature_columns=feature_columns,
        )

    def _validate_input(self, labeled_features: pd.DataFrame) -> None:
        """Validate labeled feature DataFrame."""
        if "label" not in labeled_features:
            raise ValueError("Dataset requires a label column.")
        if labeled_features.empty:
            raise ValueError("Dataset must not be empty.")

    def _select_feature_columns(self, dataset: pd.DataFrame) -> list[str]:
        """Select numeric feature columns and remove raw/future columns."""
        columns: list[str] = []
        for column in dataset.columns:
            lower_column = column.lower()
            if column in EXCLUDED_FEATURE_COLUMNS or lower_column.startswith("future"):
                continue
            if pd.api.types.is_numeric_dtype(dataset[column]):
                columns.append(column)
        if not columns:
            raise ValueError("No numeric feature columns available for training.")
        return columns

    def _split_indices(self, row_count: int) -> tuple[int, int]:
        """Return chronological split boundaries."""
        train_end = int(row_count * self._settings.train_ratio)
        validation_end = train_end + int(row_count * self._settings.validation_ratio)
        if train_end <= 0 or validation_end <= train_end or validation_end >= row_count:
            raise ValueError("Invalid time-series split; provide more rows or adjust ratios.")
        return train_end, validation_end
