"""Model training pipeline for setup classification."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    precision_score,
    recall_score,
)

from config.settings import Settings
from labeling.label_generator import LabelGenerator
from ml.dataset_builder import DatasetBuilder, DatasetSplit, TARGET_LABELS
from ml.model_registry import ModelRegistry


class EncodedXGBClassifier:
    """Small adapter that lets XGBoost train on encoded labels and predict strings."""

    def __init__(self, model: Any) -> None:
        self._model = model
        self.classes_: list[str] = []

    @property
    def feature_importances_(self):
        """Expose wrapped model feature importances."""
        return getattr(self._model, "feature_importances_", None)

    def fit(self, x_train: pd.DataFrame, y_train: pd.Series) -> "EncodedXGBClassifier":
        """Fit XGBoost on integer-encoded class labels."""
        self.classes_ = sorted(y_train.unique().tolist())
        class_to_index = {label: index for index, label in enumerate(self.classes_)}
        encoded_y = y_train.map(class_to_index)
        self._model.fit(x_train, encoded_y)
        return self

    def predict(self, x_values: pd.DataFrame) -> pd.Series:
        """Predict string labels."""
        encoded_predictions = self._model.predict(x_values)
        labels = [self.classes_[int(index)] for index in encoded_predictions]
        return pd.Series(labels, index=x_values.index)

    def predict_proba(self, x_values: pd.DataFrame):
        """Return class probabilities in classes_ order."""
        return self._model.predict_proba(x_values)


@dataclass(frozen=True)
class TrainingResult:
    """Summary of a completed training run."""

    model_path: str
    metadata_path: str
    model_type: str
    metrics: dict[str, Any]
    feature_columns: list[str]


class ModelTrainer:
    """Trains setup classifiers from feature datasets."""

    def __init__(
        self,
        settings: Settings,
        registry: ModelRegistry | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._settings = settings
        self._label_generator = LabelGenerator(settings.labeling)
        self._dataset_builder = DatasetBuilder(settings.training)
        self._registry = registry or ModelRegistry(settings.training.model_dir)
        self._logger = logger or logging.getLogger("localquant.ml")

    def train(
        self,
        features: pd.DataFrame,
        symbol: str,
        timeframe: str,
    ) -> TrainingResult:
        """Generate labels, split chronologically, train, evaluate, and save model."""
        labeled = self._label_generator.generate(features)
        split = self._dataset_builder.build(labeled)
        self._validate_train_labels(split)
        model, model_type = self._create_model()
        self._logger.info(
            "Training %s model: rows_train=%s rows_validation=%s rows_test=%s",
            model_type,
            len(split.x_train),
            len(split.x_validation),
            len(split.x_test),
        )
        model.fit(split.x_train, split.y_train)
        metrics = self._evaluate(model, split)
        model_path, metadata_path = self._registry.save(
            model=model,
            symbol=symbol,
            timeframe=timeframe,
            feature_columns=split.feature_columns,
            metrics=metrics,
            model_type=model_type,
        )
        return TrainingResult(
            model_path=str(model_path),
            metadata_path=str(metadata_path),
            model_type=model_type,
            metrics=metrics,
            feature_columns=split.feature_columns,
        )

    def _validate_train_labels(self, split: DatasetSplit) -> None:
        """Ensure the classifier can learn all target classes."""
        missing = set(TARGET_LABELS) - set(split.y_train.unique())
        if missing:
            raise ValueError(
                "Training split must contain all labels so predict_proba can expose "
                f"BUY/SELL/WAIT classes. Missing: {sorted(missing)}."
            )

    def _create_model(self) -> tuple[Any, str]:
        """Create XGBoost if available, otherwise RandomForest."""
        try:
            from xgboost import XGBClassifier

            model = XGBClassifier(
                n_estimators=self._settings.training.n_estimators,
                max_depth=self._settings.training.max_depth or 6,
                random_state=self._settings.training.random_state,
                eval_metric="mlogloss",
            )
            return (
                EncodedXGBClassifier(model),
                "XGBoostClassifier",
            )
        except ModuleNotFoundError:
            return (
                RandomForestClassifier(
                    n_estimators=self._settings.training.n_estimators,
                    max_depth=self._settings.training.max_depth,
                    random_state=self._settings.training.random_state,
                    class_weight="balanced",
                    n_jobs=-1,
                ),
                "RandomForestClassifier",
            )

    def _evaluate(self, model: Any, split: DatasetSplit) -> dict[str, Any]:
        """Evaluate model on validation and test splits."""
        validation_predictions = model.predict(split.x_validation)
        test_predictions = model.predict(split.x_test)
        metrics = {
            "validation": self._classification_metrics(
                split.y_validation,
                validation_predictions,
            ),
            "test": self._classification_metrics(split.y_test, test_predictions),
            "feature_importance": self._feature_importance(model, split.feature_columns),
        }
        self._logger.info(
            "Validation accuracy=%.4f Test accuracy=%.4f",
            metrics["validation"]["accuracy"],
            metrics["test"]["accuracy"],
        )
        return metrics

    def _classification_metrics(
        self,
        actual: pd.Series,
        predicted: pd.Series,
    ) -> dict[str, Any]:
        """Build required classification metrics."""
        report = classification_report(
            actual,
            predicted,
            labels=TARGET_LABELS,
            zero_division=0,
            output_dict=True,
        )
        return {
            "accuracy": accuracy_score(actual, predicted),
            "precision": {
                label: precision_score(
                    actual,
                    predicted,
                    labels=[label],
                    average="macro",
                    zero_division=0,
                )
                for label in TARGET_LABELS
            },
            "recall": {
                label: recall_score(
                    actual,
                    predicted,
                    labels=[label],
                    average="macro",
                    zero_division=0,
                )
                for label in TARGET_LABELS
            },
            "confusion_matrix": confusion_matrix(
                actual,
                predicted,
                labels=TARGET_LABELS,
            ).tolist(),
            "classification_report": report,
        }

    def _feature_importance(
        self,
        model: Any,
        feature_columns: list[str],
    ) -> dict[str, float]:
        """Return feature importance if the model exposes it."""
        importances = getattr(model, "feature_importances_", None)
        if importances is None:
            return {}
        pairs = zip(feature_columns, importances)
        return {
            feature: float(importance)
            for feature, importance in sorted(
                pairs,
                key=lambda item: item[1],
                reverse=True,
            )
        }
