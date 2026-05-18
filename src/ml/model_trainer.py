"""Model training pipeline for setup classification."""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
from statistics import mean, pstdev
from typing import Any

import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)

from config.settings import Settings
from labeling.label_generator import LabelGenerator
from ml.calibration.calibration_metrics import calibration_report
from ml.calibration.probability_calibrator import ProbabilityCalibrator
from ml.dataset_builder import DatasetBuilder, DatasetSplit, TARGET_LABELS
from ml.model_registry import GLOBAL_SCOPE, REGIME_SCOPE, ModelRegistry
from ml.validation.walk_forward import WalkForwardValidator


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
    registry_report: dict[str, Any] | None = None


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
        prepared, feature_columns = self._dataset_builder.prepare(labeled)
        global_result = self._train_prepared_model(
            prepared=prepared,
            feature_columns=feature_columns,
            symbol=symbol,
            timeframe=timeframe,
            model_scope=GLOBAL_SCOPE,
            regime=None,
        )
        registry_report = self._train_regime_models(
            prepared=prepared,
            feature_columns=feature_columns,
            symbol=symbol,
            timeframe=timeframe,
            global_metrics=global_result["metrics"],
        )
        global_result["metrics"]["regime_specific"] = registry_report
        _update_saved_metrics(
            global_result["metadata_path"],
            global_result["metrics"],
        )
        return TrainingResult(
            model_path=str(global_result["model_path"]),
            metadata_path=str(global_result["metadata_path"]),
            model_type=str(global_result["model_type"]),
            metrics=global_result["metrics"],
            feature_columns=feature_columns,
            registry_report=registry_report,
        )

    def _train_prepared_model(
        self,
        prepared: pd.DataFrame,
        feature_columns: list[str],
        symbol: str,
        timeframe: str,
        model_scope: str,
        regime: str | None,
    ) -> dict[str, Any]:
        """Train, evaluate, and register one model family."""
        split = self._dataset_builder.build_from_prepared(prepared, feature_columns)
        self._validate_train_labels(split)
        model, base_model_type = self._create_model()
        self._logger.info(
            "Training %s model: scope=%s regime=%s rows_train=%s rows_validation=%s rows_test=%s",
            base_model_type,
            model_scope,
            regime or "-",
            len(split.x_train),
            len(split.x_validation),
            len(split.x_test),
        )
        model.fit(split.x_train, split.y_train)
        model_to_save, calibration_metadata = self._calibrate_model(model, split)
        metrics = self._evaluate(model_to_save, split)
        metrics["calibration"] = calibration_metadata
        validation_metadata = self._validation_metadata(prepared)
        if model_scope == GLOBAL_SCOPE and self._settings.training.validation.method == "walk_forward":
            metrics["walk_forward"] = self._walk_forward_metrics(
                prepared,
                feature_columns,
            )
            metrics["validation_summary"] = metrics["walk_forward"]["summary"]
            validation_metadata["fold_metrics"] = metrics["walk_forward"]["fold_metrics"]
            validation_metadata["validation_summary"] = metrics["walk_forward"]["summary"]
        else:
            validation_metadata["fold_metrics"] = []

        model_type = (
            f"Calibrated{base_model_type}"
            if calibration_metadata["calibration_enabled"]
            else base_model_type
        )
        model_path, metadata_path = self._registry.save(
            model=model_to_save,
            symbol=symbol,
            timeframe=timeframe,
            feature_columns=feature_columns,
            metrics=metrics,
            model_type=model_type,
            model_scope=model_scope,
            regime=regime,
            status="candidate",
            auto_promote_champion=self._settings.training.registry.auto_promote_champion,
            extra_metadata={
                **validation_metadata,
                **_calibration_metadata(calibration_metadata),
                "label_distribution": _label_distribution(prepared),
                "validation_metrics": metrics["validation"],
                "calibration_metrics": calibration_metadata,
            },
        )
        return {
            "model_path": model_path,
            "metadata_path": metadata_path,
            "model_type": model_type,
            "metrics": metrics,
            "split": split,
        }

    def _train_regime_models(
        self,
        prepared: pd.DataFrame,
        feature_columns: list[str],
        symbol: str,
        timeframe: str,
        global_metrics: dict[str, Any],
    ) -> dict[str, Any]:
        """Train optional regime-specific models and compare them with global metrics."""
        config = self._settings.training.regime_specific
        report: dict[str, Any] = {"enabled": config.enabled, "models": [], "skipped": [], "comparison": []}
        if not config.enabled:
            return report
        if "market_regime" not in prepared:
            report["skipped"].append({"regime": None, "reason": "missing_market_regime_column"})
            self._logger.warning("Skipping regime-specific training: missing market_regime column.")
            return report

        allowed_regimes = list(config.allowed_regimes)
        global_test_accuracy = float(global_metrics.get("test", {}).get("accuracy", 0.0))
        for regime in allowed_regimes:
            subset = prepared[prepared["market_regime"].astype(str) == regime].reset_index(drop=True)
            sample_count = len(subset)
            if sample_count < config.min_samples_per_regime:
                reason = "insufficient_samples"
                report["skipped"].append(
                    {"regime": regime, "sample_count": sample_count, "reason": reason}
                )
                self._logger.warning(
                    "Skipping regime-specific model: regime=%s samples=%s min_samples=%s",
                    regime,
                    sample_count,
                    config.min_samples_per_regime,
                )
                continue
            try:
                result = self._train_prepared_model(
                    prepared=subset,
                    feature_columns=feature_columns,
                    symbol=symbol,
                    timeframe=timeframe,
                    model_scope=REGIME_SCOPE,
                    regime=regime,
                )
            except ValueError as error:
                report["skipped"].append(
                    {"regime": regime, "sample_count": sample_count, "reason": str(error)}
                )
                self._logger.warning("Skipping regime-specific model %s: %s", regime, error)
                continue
            regime_accuracy = float(result["metrics"].get("test", {}).get("accuracy", 0.0))
            winner = "regime_specific" if regime_accuracy >= global_test_accuracy else "global"
            report["models"].append(
                {
                    "regime": regime,
                    "sample_count": sample_count,
                    "model_path": str(result["model_path"]),
                    "metadata_path": str(result["metadata_path"]),
                    "test_accuracy": regime_accuracy,
                }
            )
            report["comparison"].append(
                {
                    "regime": regime,
                    "global_model_metric": global_test_accuracy,
                    "regime_model_metric": regime_accuracy,
                    "winner": winner,
                    "sample_count": sample_count,
                }
            )
        return report

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

    def _calibrate_model(
        self,
        model: Any,
        split: DatasetSplit,
    ) -> tuple[Any, dict[str, Any]]:
        """Fit probability calibration on validation data when enabled."""
        calibration = self._settings.training.calibration
        method = calibration.method if calibration.enabled else "none"
        if method == "none":
            raw_report = calibration_report(
                split.y_validation,
                getattr(model, "classes_", TARGET_LABELS),
                model.predict_proba(split.x_validation),
            )
            return model, {
                "calibration_enabled": False,
                "calibration_method": "none",
                "classes": [str(label) for label in getattr(model, "classes_", TARGET_LABELS)],
                "before": raw_report,
                "after": raw_report,
                "brier_score_before": raw_report["brier_score"],
                "brier_score_after": raw_report["brier_score"],
                "log_loss_before": raw_report["log_loss"],
                "log_loss_after": raw_report["log_loss"],
            }

        try:
            result = ProbabilityCalibrator().calibrate(
                base_model=model,
                x_validation=split.x_validation,
                y_validation=split.y_validation,
                method=method,
                cv=calibration.cv,
            )
            self._logger.info(
                "Probability calibration completed: method=%s brier_before=%.4f brier_after=%.4f",
                method,
                result.report["brier_score_before"],
                result.report["brier_score_after"],
            )
            return result.model, {
                "calibration_enabled": True,
                "calibration_method": method,
                **result.report,
            }
        except Exception as error:
            self._logger.warning("Probability calibration failed; using raw probabilities: %s", error)
            raw_report = calibration_report(
                split.y_validation,
                getattr(model, "classes_", TARGET_LABELS),
                model.predict_proba(split.x_validation),
            )
            return model, {
                "calibration_enabled": False,
                "calibration_method": method,
                "calibration_error": str(error),
                "classes": [str(label) for label in getattr(model, "classes_", TARGET_LABELS)],
                "before": raw_report,
                "after": raw_report,
                "brier_score_before": raw_report["brier_score"],
                "brier_score_after": raw_report["brier_score"],
                "log_loss_before": raw_report["log_loss"],
                "log_loss_after": raw_report["log_loss"],
            }

    def _walk_forward_metrics(
        self,
        dataset: pd.DataFrame,
        feature_columns: list[str],
    ) -> dict[str, Any]:
        """Run purged walk-forward validation and summarize fold metrics."""
        validator = WalkForwardValidator(
            settings=self._settings.training.validation,
            purge_size=self._settings.labeling.lookahead_bars,
        )
        split = validator.split(dataset)
        fold_metrics: list[dict[str, Any]] = []
        for fold in split.folds:
            fold_model_type, metrics = self._fit_and_score_fold(
                dataset=dataset,
                feature_columns=feature_columns,
                train_indices=fold.train_indices,
                validation_indices=fold.validation_indices,
            )
            fold_metrics.append(
                {
                    **fold.to_metadata(dataset),
                    "model_type": fold_model_type,
                    "accuracy": metrics["accuracy"],
                    "f1_macro": metrics["f1_macro"],
                    "classification": metrics,
                }
            )

        accuracies = [float(item["accuracy"]) for item in fold_metrics]
        f1_scores = [float(item["f1_macro"]) for item in fold_metrics]
        return {
            "fold_metrics": fold_metrics,
            "summary": {
                "mean_accuracy": mean(accuracies),
                "std_accuracy": pstdev(accuracies) if len(accuracies) > 1 else 0.0,
                "mean_f1": mean(f1_scores),
                "std_f1": pstdev(f1_scores) if len(f1_scores) > 1 else 0.0,
                "mean_profit_factor": None,
                "worst_fold_metric": min(accuracies),
            },
        }

    def _fit_and_score_fold(
        self,
        dataset: pd.DataFrame,
        feature_columns: list[str],
        train_indices: list[int],
        validation_indices: list[int],
    ) -> tuple[str, dict[str, Any]]:
        """Fit all fold-local training steps on train rows only."""
        fold_model, fold_model_type = self._create_model()
        train = dataset.iloc[train_indices]
        validation = dataset.iloc[validation_indices]
        x_train = train[feature_columns]
        y_train = train["label"]
        x_validation = validation[feature_columns]
        y_validation = validation["label"]
        fold_model.fit(x_train, y_train)
        predictions = fold_model.predict(x_validation)
        return fold_model_type, self._classification_metrics(
            y_validation,
            predictions,
        )

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
            "f1_macro": f1_score(
                actual,
                predicted,
                labels=TARGET_LABELS,
                average="macro",
                zero_division=0,
            ),
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

    def _validation_metadata(self, dataset: pd.DataFrame) -> dict[str, Any]:
        """Build model metadata for the configured validation method."""
        validation = self._settings.training.validation
        metadata: dict[str, Any] = {
            "validation_method": validation.method,
            "purge_size": (
                self._settings.labeling.lookahead_bars
                if validation.method == "walk_forward"
                else 0
            ),
            "embargo_size": validation.embargo_size,
            "dataset_start": _dataset_timestamp(dataset, 0),
            "dataset_end": _dataset_timestamp(dataset, len(dataset) - 1),
        }
        if validation.method == "walk_forward":
            metadata.update(
                {
                    "validation_n_splits": validation.n_splits,
                    "validation_train_window_bars": validation.train_window_bars,
                    "validation_window_bars": validation.validation_window_bars,
                    "validation_expanding_window": validation.expanding_window,
                }
            )
        return metadata

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


def _dataset_timestamp(dataset: pd.DataFrame, index: int) -> str | None:
    """Return dataset timestamp metadata when available."""
    if dataset.empty or "timestamp" not in dataset:
        return None
    value = dataset.iloc[index]["timestamp"]
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def _calibration_metadata(report: dict[str, Any]) -> dict[str, Any]:
    """Return top-level metadata fields for calibration."""
    return {
        "calibration_enabled": report["calibration_enabled"],
        "calibration_method": report["calibration_method"],
        "brier_score_before": report["brier_score_before"],
        "brier_score_after": report["brier_score_after"],
        "log_loss_before": report["log_loss_before"],
        "log_loss_after": report["log_loss_after"],
    }


def _label_distribution(dataset: pd.DataFrame) -> dict[str, int]:
    """Return label counts for model metadata."""
    if "label" not in dataset:
        return {}
    return {str(label): int(count) for label, count in dataset["label"].value_counts().items()}


def _update_saved_metrics(metadata_path: Any, metrics: dict[str, Any]) -> None:
    """Update saved global metadata after optional regime training report is built."""
    path = metadata_path
    metadata = json.loads(path.read_text(encoding="utf-8"))
    metadata["metrics"] = metrics
    path.write_text(
        json.dumps(metadata, default=_json_default, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _json_default(value: Any) -> Any:
    """Convert common numeric scalar objects into JSON-serializable values."""
    if hasattr(value, "item"):
        return value.item()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable.")
