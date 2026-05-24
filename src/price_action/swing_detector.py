"""Strictly-causal swing high/low detection."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import pandas as pd


REQUIRED_COLUMNS = ("timestamp", "open", "high", "low", "close")


class SwingType(str, Enum):
    """Supported swing point types."""

    HIGH = "HIGH"
    LOW = "LOW"


@dataclass(frozen=True)
class SwingDetectorConfig:
    """Configuration for confirmed causal swing detection."""

    left_bars: int = 3
    confirmation_bars: int = 1
    min_swing_distance_atr: float = 0.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "left_bars", max(1, int(self.left_bars)))
        object.__setattr__(self, "confirmation_bars", max(0, int(self.confirmation_bars)))
        object.__setattr__(
            self,
            "min_swing_distance_atr",
            max(0.0, float(self.min_swing_distance_atr)),
        )


@dataclass(frozen=True)
class SwingPoint:
    """One causal swing point detected at a closed candle."""

    index: int
    timestamp: object
    price: float
    swing_type: SwingType
    confirmed_index: int | None = None
    confirmed_at: object | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize swing point to primitive values."""
        return {
            "index": self.index,
            "timestamp": _timestamp_value(self.timestamp),
            "price": self.price,
            "swing_type": self.swing_type.value,
            "confirmed_index": self.confirmed_index,
            "confirmed_at": _timestamp_value(self.confirmed_at),
        }


@dataclass(frozen=True)
class SwingDetectionResult:
    """Confirmed swing detection output for UI/reasoning consumers."""

    swing_highs: list[SwingPoint] = field(default_factory=list)
    swing_lows: list[SwingPoint] = field(default_factory=list)
    latest_swing_high: SwingPoint | None = None
    latest_swing_low: SwingPoint | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize result into API-friendly primitive values."""
        return {
            "swing_highs": [point.to_dict() for point in self.swing_highs],
            "swing_lows": [point.to_dict() for point in self.swing_lows],
            "latest_swing_high": (
                self.latest_swing_high.to_dict()
                if self.latest_swing_high is not None
                else None
            ),
            "latest_swing_low": (
                self.latest_swing_low.to_dict()
                if self.latest_swing_low is not None
                else None
            ),
        }


class SwingDetector:
    """Detect swing highs/lows using only completed candles up to decision time."""

    def __init__(
        self,
        lookback: int | None = None,
        min_separation: int = 1,
        *,
        left_bars: int | None = None,
        confirmation_bars: int = 1,
        min_swing_distance_atr: float = 0.0,
        config: SwingDetectorConfig | None = None,
    ) -> None:
        legacy_lookback = 3 if lookback is None else int(lookback)
        self._lookback = max(1, legacy_lookback)
        self._min_separation = max(1, int(min_separation))
        self._config = config or SwingDetectorConfig(
            left_bars=self._lookback if left_bars is None else left_bars,
            confirmation_bars=confirmation_bars,
            min_swing_distance_atr=min_swing_distance_atr,
        )

    @property
    def config(self) -> SwingDetectorConfig:
        """Return normalized detector config."""
        return self._config

    def detect(self, candles: pd.DataFrame | list[Mapping[str, object]] | list[object]) -> list[SwingPoint]:
        """Return legacy causal swing points from the provided candles.

        This preserves the original list-based API used by existing ICT and
        structure analyzers. New consumers should prefer detect_report().
        """
        frame = _to_frame(candles)
        _validate_candles(frame)
        return _legacy_turning_point_swings(frame, self._min_separation)

    def detect_report(
        self,
        candles: pd.DataFrame | list[Mapping[str, object]] | list[object],
    ) -> SwingDetectionResult:
        """Return confirmed swing highs/lows from all currently available candles."""
        frame = _to_frame(candles)
        if frame.empty:
            return SwingDetectionResult()
        _validate_candles(frame)
        return self._detect_confirmed(frame)

    def detect_report_at(
        self,
        candles: pd.DataFrame | list[Mapping[str, object]] | list[object],
        index: int,
    ) -> SwingDetectionResult:
        """Return confirmed swings using only candles up to and including index."""
        frame = _to_frame(candles)
        if frame.empty:
            return SwingDetectionResult()
        if index < 0 or index >= len(frame):
            raise ValueError("Index is outside available candle range.")
        return self.detect_report(frame.iloc[: index + 1].copy(deep=True))

    def _detect_confirmed(self, candles: pd.DataFrame) -> SwingDetectionResult:
        highs = candles["high"].astype(float)
        lows = candles["low"].astype(float)
        timestamps = candles["timestamp"]
        left_bars = self._config.left_bars
        confirmation_bars = self._config.confirmation_bars

        swing_highs: list[SwingPoint] = []
        swing_lows: list[SwingPoint] = []
        if len(candles) <= left_bars + confirmation_bars:
            return SwingDetectionResult()

        for candidate_index in range(left_bars, len(candles) - confirmation_bars):
            confirmation_index = candidate_index + confirmation_bars
            high = float(highs.iloc[candidate_index])
            low = float(lows.iloc[candidate_index])

            left_highs = highs.iloc[candidate_index - left_bars : candidate_index]
            right_highs = highs.iloc[candidate_index + 1 : confirmation_index + 1]
            if high > float(left_highs.max()) and (
                right_highs.empty or high >= float(right_highs.max())
            ):
                point = SwingPoint(
                    index=candidate_index,
                    timestamp=timestamps.iloc[candidate_index],
                    price=high,
                    swing_type=SwingType.HIGH,
                    confirmed_index=confirmation_index,
                    confirmed_at=timestamps.iloc[confirmation_index],
                )
                if self._passes_filters(candles, point, swing_highs[-1] if swing_highs else None):
                    swing_highs.append(point)

            left_lows = lows.iloc[candidate_index - left_bars : candidate_index]
            right_lows = lows.iloc[candidate_index + 1 : confirmation_index + 1]
            if low < float(left_lows.min()) and (
                right_lows.empty or low <= float(right_lows.min())
            ):
                point = SwingPoint(
                    index=candidate_index,
                    timestamp=timestamps.iloc[candidate_index],
                    price=low,
                    swing_type=SwingType.LOW,
                    confirmed_index=confirmation_index,
                    confirmed_at=timestamps.iloc[confirmation_index],
                )
                if self._passes_filters(candles, point, swing_lows[-1] if swing_lows else None):
                    swing_lows.append(point)

        return SwingDetectionResult(
            swing_highs=swing_highs,
            swing_lows=swing_lows,
            latest_swing_high=swing_highs[-1] if swing_highs else None,
            latest_swing_low=swing_lows[-1] if swing_lows else None,
        )

    def _passes_filters(
        self,
        candles: pd.DataFrame,
        point: SwingPoint,
        previous_same_type: SwingPoint | None,
    ) -> bool:
        if previous_same_type is None:
            return True
        if point.index - previous_same_type.index < self._min_separation:
            return False
        min_distance = self._config.min_swing_distance_atr
        if min_distance <= 0:
            return True
        atr = _atr_at(candles, point.index)
        if atr is None or atr <= 0:
            return True
        return abs(point.price - previous_same_type.price) >= atr * min_distance


def _legacy_turning_point_swings(candles: pd.DataFrame, min_separation: int) -> list[SwingPoint]:
    """Preserve the original close-turn swing behavior for existing imports."""
    if len(candles) == 1:
        return [
            SwingPoint(
                index=0,
                timestamp=candles["timestamp"].iloc[0],
                price=float(candles["high"].iloc[0]),
                swing_type=SwingType.HIGH,
                confirmed_index=0,
                confirmed_at=candles["timestamp"].iloc[0],
            ),
            SwingPoint(
                index=0,
                timestamp=candles["timestamp"].iloc[0],
                price=float(candles["low"].iloc[0]),
                swing_type=SwingType.LOW,
                confirmed_index=0,
                confirmed_at=candles["timestamp"].iloc[0],
            ),
        ]

    highs = candles["high"]
    lows = candles["low"]
    closes = candles["close"]
    timestamps = candles["timestamp"]
    swings: list[SwingPoint] = []

    last_added_high: int | None = None
    last_added_low: int | None = None
    leg_high_index = 0
    leg_low_index = 0
    leg_high_price = float(highs.iloc[0])
    leg_low_price = float(lows.iloc[0])
    prev_direction = 0

    for index in range(1, len(candles)):
        close_delta = float(closes.iloc[index]) - float(closes.iloc[index - 1])
        direction = 1 if close_delta > 0 else -1 if close_delta < 0 else prev_direction

        high = float(highs.iloc[index])
        low = float(lows.iloc[index])
        if high >= leg_high_price:
            leg_high_price = high
            leg_high_index = index
        if low <= leg_low_price:
            leg_low_price = low
            leg_low_index = index

        if prev_direction == 0:
            prev_direction = direction
            continue

        if prev_direction > 0 and direction < 0:
            if last_added_high is None or leg_high_index - last_added_high >= min_separation:
                swings.append(
                    SwingPoint(
                        index=leg_high_index,
                        timestamp=timestamps.iloc[leg_high_index],
                        price=leg_high_price,
                        swing_type=SwingType.HIGH,
                        confirmed_index=index,
                        confirmed_at=timestamps.iloc[index],
                    )
                )
                last_added_high = leg_high_index
            leg_low_index = index
            leg_low_price = low
        elif prev_direction < 0 and direction > 0:
            if last_added_low is None or leg_low_index - last_added_low >= min_separation:
                swings.append(
                    SwingPoint(
                        index=leg_low_index,
                        timestamp=timestamps.iloc[leg_low_index],
                        price=leg_low_price,
                        swing_type=SwingType.LOW,
                        confirmed_index=index,
                        confirmed_at=timestamps.iloc[index],
                    )
                )
                last_added_low = leg_low_index
            leg_high_index = index
            leg_high_price = high

        prev_direction = direction

    if prev_direction >= 0 and (last_added_high is None or leg_high_index != last_added_high):
        swings.append(
            SwingPoint(
                index=leg_high_index,
                timestamp=timestamps.iloc[leg_high_index],
                price=leg_high_price,
                swing_type=SwingType.HIGH,
                confirmed_index=len(candles) - 1,
                confirmed_at=timestamps.iloc[-1],
            )
        )
    if prev_direction <= 0 and (last_added_low is None or leg_low_index != last_added_low):
        swings.append(
            SwingPoint(
                index=leg_low_index,
                timestamp=timestamps.iloc[leg_low_index],
                price=leg_low_price,
                swing_type=SwingType.LOW,
                confirmed_index=len(candles) - 1,
                confirmed_at=timestamps.iloc[-1],
            )
        )
    return sorted(swings, key=lambda item: (item.index, item.swing_type.value))


def _to_frame(candles: pd.DataFrame | list[Mapping[str, object]] | list[object]) -> pd.DataFrame:
    if isinstance(candles, pd.DataFrame):
        return candles.copy(deep=True)
    rows: list[dict[str, object]] = []
    for candle in candles:
        if isinstance(candle, Mapping):
            rows.append(dict(candle))
        else:
            rows.append({column: getattr(candle, column, None) for column in REQUIRED_COLUMNS})
    return pd.DataFrame(rows)


def _validate_candles(candles: pd.DataFrame) -> None:
    missing = [column for column in REQUIRED_COLUMNS if column not in candles]
    if missing:
        raise ValueError(f"Candle DataFrame is missing columns: {missing}.")
    if candles.empty:
        raise ValueError("Candle DataFrame must not be empty.")


def _atr_at(candles: pd.DataFrame, index: int) -> float | None:
    if "atr_14" in candles:
        try:
            value = float(candles["atr_14"].iloc[index])
        except (TypeError, ValueError):
            value = 0.0
        if pd.notna(value) and value > 0:
            return value
    start = max(0, index - 13)
    window = candles.iloc[start : index + 1]
    if window.empty:
        return None
    high_low = window["high"].astype(float) - window["low"].astype(float)
    previous_close = window["close"].astype(float).shift(1)
    high_prev_close = (window["high"].astype(float) - previous_close).abs()
    low_prev_close = (window["low"].astype(float) - previous_close).abs()
    true_range = pd.concat([high_low, high_prev_close, low_prev_close], axis=1).max(axis=1)
    value = float(true_range.dropna().mean()) if not true_range.dropna().empty else 0.0
    return value if value > 0 else None


def _timestamp_value(value: object) -> object:
    if value is None:
        return None
    return value.isoformat() if hasattr(value, "isoformat") else value

