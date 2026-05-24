"""Causal OHLCV data quality gate for signal research."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Any, Mapping

import pandas as pd


REQUIRED_COLUMNS = ("timestamp", "open", "high", "low", "close", "volume")


class DataQualitySeverity(str, Enum):
    """Severity bucket for data quality issues."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class DataQualityAction(str, Enum):
    """Recommended downstream action for a quality report."""

    CONTINUE = "CONTINUE"
    WARN = "WARN"
    BLOCK = "BLOCK"


@dataclass(frozen=True)
class DataQualityReport:
    """Serializable result of the data quality gate."""

    passed: bool
    score: float
    issues: list[str]
    severity: DataQualitySeverity
    recommended_action: DataQualityAction

    def to_dict(self) -> dict[str, object]:
        """Serialize the report into API-friendly primitive values."""
        return {
            "passed": self.passed,
            "score": self.score,
            "issues": list(self.issues),
            "severity": self.severity.value,
            "recommended_action": self.recommended_action.value,
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> "DataQualityReport":
        """Build a report from a serialized payload."""
        severity = _enum_or_default(
            DataQualitySeverity,
            payload.get("severity"),
            DataQualitySeverity.LOW,
        )
        action = _enum_or_default(
            DataQualityAction,
            payload.get("recommended_action"),
            DataQualityAction.CONTINUE,
        )
        try:
            score = float(payload.get("score", 1.0))
        except (TypeError, ValueError):
            score = 1.0
        raw_issues = payload.get("issues", [])
        issues = [str(item) for item in raw_issues] if isinstance(raw_issues, list) else []
        return cls(
            passed=bool(payload.get("passed", action is not DataQualityAction.BLOCK)),
            score=_clip(score),
            issues=issues,
            severity=severity,
            recommended_action=action,
        )


@dataclass(frozen=True)
class _Issue:
    message: str
    severity: DataQualitySeverity
    penalty: float


class DataQualityGate:
    """Detect quality failures using only candles available up to the evaluated row."""

    def __init__(
        self,
        *,
        missing_gap_tolerance: float = 1.5,
        large_gap_multiplier: float = 3.0,
        price_jump_threshold: float = 0.25,
        volume_outlier_multiplier: float = 8.0,
        volume_outlier_window: int = 20,
        min_volume_history: int = 5,
    ) -> None:
        self._missing_gap_tolerance = missing_gap_tolerance
        self._large_gap_multiplier = large_gap_multiplier
        self._price_jump_threshold = price_jump_threshold
        self._volume_outlier_multiplier = volume_outlier_multiplier
        self._volume_outlier_window = volume_outlier_window
        self._min_volume_history = min_volume_history

    def evaluate(
        self,
        candles: pd.DataFrame | list[Mapping[str, object]] | list[object],
        *,
        timeframe: str | None = None,
    ) -> DataQualityReport:
        """Evaluate all provided candles without mutating the input object."""
        frame = _to_frame(candles)
        issues: list[_Issue] = []
        issues.extend(_schema_issues(frame))
        if issues:
            return _report(issues)

        working = _normalized_frame(frame)
        issues.extend(_timestamp_issues(working, timeframe, self._missing_gap_tolerance, self._large_gap_multiplier))
        issues.extend(_ohlc_issues(working))
        issues.extend(_volume_issues(working))
        issues.extend(_price_jump_issues(working, self._price_jump_threshold))
        issues.extend(
            _volume_outlier_issues(
                working,
                multiplier=self._volume_outlier_multiplier,
                window=self._volume_outlier_window,
                min_history=self._min_volume_history,
            )
        )
        return _report(issues)

    def evaluate_at(
        self,
        candles: pd.DataFrame | list[Mapping[str, object]] | list[object],
        *,
        index: int,
        timeframe: str | None = None,
    ) -> DataQualityReport:
        """Evaluate using only candles up to and including index."""
        frame = _to_frame(candles)
        if index < 0 or index >= len(frame):
            return _report(
                [
                    _Issue(
                        f"Data quality index {index} is outside available candle range.",
                        DataQualitySeverity.HIGH,
                        0.5,
                    )
                ]
            )
        return self.evaluate(frame.iloc[: index + 1].copy(deep=True), timeframe=timeframe)


def _schema_issues(frame: pd.DataFrame) -> list[_Issue]:
    issues: list[_Issue] = []
    if frame.empty:
        issues.append(_Issue("Candle dataset is empty.", DataQualitySeverity.HIGH, 0.6))
        return issues
    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        issues.append(
            _Issue(
                f"Candle dataset is missing required columns: {', '.join(missing)}.",
                DataQualitySeverity.HIGH,
                0.6,
            )
        )
    return issues


def _normalized_frame(frame: pd.DataFrame) -> pd.DataFrame:
    working = frame.loc[:, REQUIRED_COLUMNS].copy(deep=True)
    working["timestamp"] = pd.to_datetime(working["timestamp"], utc=True, errors="coerce")
    for column in ("open", "high", "low", "close", "volume"):
        working[column] = pd.to_numeric(working[column], errors="coerce")
    return working.sort_values("timestamp", kind="mergesort").reset_index(drop=True)


def _timestamp_issues(
    frame: pd.DataFrame,
    timeframe: str | None,
    missing_gap_tolerance: float,
    large_gap_multiplier: float,
) -> list[_Issue]:
    issues: list[_Issue] = []
    if frame["timestamp"].isna().any():
        issues.append(_Issue("Null or invalid candle timestamp detected.", DataQualitySeverity.HIGH, 0.45))
    duplicate_mask = frame["timestamp"].duplicated(keep=False)
    if duplicate_mask.any():
        count = int(duplicate_mask.sum())
        issues.append(_Issue(f"Duplicated timestamp detected in {count} candle rows.", DataQualitySeverity.HIGH, 0.45))

    clean_timestamps = frame["timestamp"].dropna()
    if len(clean_timestamps) < 2:
        return issues
    expected_delta = _timeframe_delta(timeframe) or _infer_delta(clean_timestamps)
    if expected_delta is None or expected_delta <= pd.Timedelta(0):
        return issues
    diffs = clean_timestamps.diff().dropna()
    for timestamp, gap in diffs.items():
        if gap > expected_delta * missing_gap_tolerance:
            missing_count = max(int(round(gap / expected_delta)) - 1, 1)
            issues.append(
                _Issue(
                    (
                        f"Missing candles detected before {clean_timestamps.loc[timestamp].isoformat()}: "
                        f"gap={gap}, expected={expected_delta}, estimated_missing={missing_count}."
                    ),
                    DataQualitySeverity.MEDIUM,
                    min(0.1 + missing_count * 0.05, 0.3),
                )
            )
        if gap >= expected_delta * large_gap_multiplier:
            issues.append(
                _Issue(
                    f"Large timestamp gap detected before {clean_timestamps.loc[timestamp].isoformat()}: gap={gap}.",
                    DataQualitySeverity.HIGH,
                    0.4,
                )
            )
    return issues


def _ohlc_issues(frame: pd.DataFrame) -> list[_Issue]:
    price_columns = ("open", "high", "low", "close")
    issues: list[_Issue] = []
    null_count = int(frame.loc[:, price_columns].isna().sum().sum())
    if null_count:
        issues.append(_Issue(f"Null OHLC value detected in {null_count} cells.", DataQualitySeverity.HIGH, 0.45))

    non_positive = (frame.loc[:, price_columns] <= 0).sum().sum()
    if int(non_positive):
        issues.append(_Issue(f"Non-positive OHLC value detected in {int(non_positive)} cells.", DataQualitySeverity.HIGH, 0.45))

    invalid_range = frame["high"] < frame["low"]
    outside_range = (
        (frame["open"] > frame["high"])
        | (frame["open"] < frame["low"])
        | (frame["close"] > frame["high"])
        | (frame["close"] < frame["low"])
    )
    invalid_rows = int((invalid_range | outside_range).sum())
    if invalid_rows:
        issues.append(_Issue(f"OHLC invalid range detected in {invalid_rows} candle rows.", DataQualitySeverity.HIGH, 0.45))
    return issues


def _volume_issues(frame: pd.DataFrame) -> list[_Issue]:
    issues: list[_Issue] = []
    null_count = int(frame["volume"].isna().sum())
    if null_count:
        issues.append(_Issue(f"Null volume detected in {null_count} candle rows.", DataQualitySeverity.HIGH, 0.4))
    negative_count = int((frame["volume"] < 0).sum())
    if negative_count:
        issues.append(_Issue(f"Negative volume detected in {negative_count} candle rows.", DataQualitySeverity.HIGH, 0.4))
    return issues


def _price_jump_issues(frame: pd.DataFrame, threshold: float) -> list[_Issue]:
    issues: list[_Issue] = []
    closes = frame["close"]
    previous = closes.shift(1)
    jumps = ((closes - previous).abs() / previous.abs()).replace([float("inf"), -float("inf")], pd.NA)
    jump_mask = jumps > threshold
    if jump_mask.any():
        max_jump = float(jumps[jump_mask].max())
        issues.append(
            _Issue(
                f"Abnormal price jump detected: max close-to-close move {max_jump:.2%}.",
                DataQualitySeverity.HIGH,
                0.35,
            )
        )
    return issues


def _volume_outlier_issues(
    frame: pd.DataFrame,
    *,
    multiplier: float,
    window: int,
    min_history: int,
) -> list[_Issue]:
    issues: list[_Issue] = []
    volumes = frame["volume"]
    outlier_count = 0
    max_ratio = 0.0
    for index in range(len(volumes)):
        start = max(0, index - window)
        history = volumes.iloc[start:index].dropna()
        history = history[history > 0]
        if len(history) < min_history:
            continue
        median = float(history.median())
        current = volumes.iloc[index]
        if median <= 0 or not _finite_number(current):
            continue
        ratio = float(current) / median
        if ratio >= multiplier:
            outlier_count += 1
            max_ratio = max(max_ratio, ratio)
    if outlier_count:
        issues.append(
            _Issue(
                f"Outlier volume detected in {outlier_count} candle rows: max ratio {max_ratio:.2f}x.",
                DataQualitySeverity.MEDIUM,
                0.2,
            )
        )
    return issues


def _report(issues: list[_Issue]) -> DataQualityReport:
    if not issues:
        return DataQualityReport(
            passed=True,
            score=1.0,
            issues=[],
            severity=DataQualitySeverity.LOW,
            recommended_action=DataQualityAction.CONTINUE,
        )
    severity = max((issue.severity for issue in issues), key=_severity_rank)
    action = (
        DataQualityAction.BLOCK
        if severity is DataQualitySeverity.HIGH
        else DataQualityAction.WARN
    )
    score = _clip(1.0 - sum(issue.penalty for issue in issues))
    return DataQualityReport(
        passed=action is not DataQualityAction.BLOCK,
        score=round(score, 4),
        issues=[issue.message for issue in issues],
        severity=severity,
        recommended_action=action,
    )


def _to_frame(candles: pd.DataFrame | list[Mapping[str, object]] | list[object]) -> pd.DataFrame:
    if isinstance(candles, pd.DataFrame):
        return candles.copy(deep=True)
    rows: list[dict[str, object]] = []
    for candle in candles:
        if isinstance(candle, Mapping):
            rows.append(dict(candle))
        else:
            rows.append(
                {
                    column: getattr(candle, column, None)
                    for column in REQUIRED_COLUMNS
                }
            )
    return pd.DataFrame(rows)


def _timeframe_delta(timeframe: str | None) -> pd.Timedelta | None:
    if not timeframe:
        return None
    value = timeframe.strip().lower()
    if len(value) < 2:
        return None
    unit = value[-1]
    try:
        amount = int(value[:-1])
    except ValueError:
        return None
    if amount <= 0:
        return None
    if unit == "m":
        return pd.Timedelta(minutes=amount)
    if unit == "h":
        return pd.Timedelta(hours=amount)
    if unit == "d":
        return pd.Timedelta(days=amount)
    if unit == "w":
        return pd.Timedelta(weeks=amount)
    return None


def _infer_delta(timestamps: pd.Series) -> pd.Timedelta | None:
    diffs = timestamps.diff().dropna()
    if diffs.empty:
        return None
    positive_diffs = diffs[diffs > pd.Timedelta(0)]
    if positive_diffs.empty:
        return None
    return positive_diffs.median()


def _enum_or_default(enum_type: type[Enum], value: object, default: Any) -> Any:
    if isinstance(value, enum_type):
        return value
    if isinstance(value, str):
        try:
            return enum_type(value.strip().upper())
        except ValueError:
            return default
    return default


def _severity_rank(severity: DataQualitySeverity) -> int:
    return {
        DataQualitySeverity.LOW: 0,
        DataQualitySeverity.MEDIUM: 1,
        DataQualitySeverity.HIGH: 2,
    }[severity]


def _finite_number(value: object) -> bool:
    try:
        return isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _clip(value: float) -> float:
    return max(0.0, min(float(value), 1.0))
