"""Strictly-causal swing point detection."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

import pandas as pd


class SwingType(str, Enum):
    """Supported swing point types."""

    HIGH = "HIGH"
    LOW = "LOW"


@dataclass(frozen=True)
class SwingPoint:
    """One causal swing point detected at close of a candle."""

    index: int
    timestamp: object
    price: float
    swing_type: SwingType

    def to_dict(self) -> dict[str, Any]:
        """Serialize swing point to primitive values."""
        return {
            "index": self.index,
            "timestamp": self.timestamp.isoformat()
            if hasattr(self.timestamp, "isoformat")
            else self.timestamp,
            "price": self.price,
            "swing_type": self.swing_type.value,
        }


class SwingDetector:
    """Detect swing highs/lows using only completed candles up to now."""

    def __init__(
        self,
        lookback: int = 3,
        min_separation: int = 1,
    ) -> None:
        self._lookback = max(1, int(lookback))
        self._min_separation = max(1, int(min_separation))

    def detect(self, candles: pd.DataFrame) -> list[SwingPoint]:
        """Return causal swing points from the provided candles."""
        _validate_candles(candles)
        if len(candles) == 1:
            return [
                SwingPoint(
                    index=0,
                    timestamp=candles["timestamp"].iloc[0],
                    price=float(candles["high"].iloc[0]),
                    swing_type=SwingType.HIGH,
                ),
                SwingPoint(
                    index=0,
                    timestamp=candles["timestamp"].iloc[0],
                    price=float(candles["low"].iloc[0]),
                    swing_type=SwingType.LOW,
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
                if (
                    last_added_high is None
                    or leg_high_index - last_added_high >= self._min_separation
                ):
                    swings.append(
                        SwingPoint(
                            index=leg_high_index,
                            timestamp=timestamps.iloc[leg_high_index],
                            price=leg_high_price,
                            swing_type=SwingType.HIGH,
                        )
                    )
                    last_added_high = leg_high_index
                leg_low_index = index
                leg_low_price = low
            elif prev_direction < 0 and direction > 0:
                if (
                    last_added_low is None
                    or leg_low_index - last_added_low >= self._min_separation
                ):
                    swings.append(
                        SwingPoint(
                            index=leg_low_index,
                            timestamp=timestamps.iloc[leg_low_index],
                            price=leg_low_price,
                            swing_type=SwingType.LOW,
                        )
                    )
                    last_added_low = leg_low_index
                leg_high_index = index
                leg_high_price = high

            prev_direction = direction

        # Emit the active leg extreme at current close for causal "state now".
        if prev_direction >= 0:
            if last_added_high is None or leg_high_index != last_added_high:
                swings.append(
                    SwingPoint(
                        index=leg_high_index,
                        timestamp=timestamps.iloc[leg_high_index],
                        price=leg_high_price,
                        swing_type=SwingType.HIGH,
                    )
                )
        if prev_direction <= 0:
            if last_added_low is None or leg_low_index != last_added_low:
                swings.append(
                    SwingPoint(
                        index=leg_low_index,
                        timestamp=timestamps.iloc[leg_low_index],
                        price=leg_low_price,
                        swing_type=SwingType.LOW,
                    )
                )
        return sorted(swings, key=lambda item: (item.index, item.swing_type.value))


def _validate_candles(candles: pd.DataFrame) -> None:
    required = {"timestamp", "open", "high", "low", "close"}
    missing = [column for column in required if column not in candles]
    if missing:
        raise ValueError(f"Candle DataFrame is missing columns: {missing}.")
    if candles.empty:
        raise ValueError("Candle DataFrame must not be empty.")
