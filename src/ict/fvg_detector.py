"""Strictly-causal Fair Value Gap (FVG) detection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class FVGZone:
    """One bullish/bearish FVG zone."""

    direction: str
    created_index: int
    low: float
    high: float
    fill_ratio: float
    distance: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "direction": self.direction,
            "created_index": self.created_index,
            "low": self.low,
            "high": self.high,
            "fill_ratio": self.fill_ratio,
            "distance": self.distance,
        }


@dataclass(frozen=True)
class FVGResult:
    """FVG analysis output."""

    fvg_detected: bool
    direction: str
    fvg_fill_ratio: float
    nearest_fvg_distance: float
    nearest_fvg: dict[str, Any] | None
    bullish_zones: list[dict[str, Any]]
    bearish_zones: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "fvg_detected": self.fvg_detected,
            "direction": self.direction,
            "fvg_fill_ratio": self.fvg_fill_ratio,
            "nearest_fvg_distance": self.nearest_fvg_distance,
            "nearest_fvg": self.nearest_fvg,
            "bullish_zones": self.bullish_zones,
            "bearish_zones": self.bearish_zones,
        }


class FVGDetector:
    """Detect bullish/bearish FVG from 3-candle pattern without future data."""

    def analyze(self, candles: pd.DataFrame) -> FVGResult:
        return self.analyze_at(candles, len(candles) - 1)

    def analyze_at(self, candles: pd.DataFrame, index: int) -> FVGResult:
        if index < 0:
            raise ValueError("Index must be non-negative.")
        window = candles.iloc[: index + 1].copy(deep=True)
        _validate_candles(window)
        if len(window) < 3:
            return FVGResult(
                fvg_detected=False,
                direction="NONE",
                fvg_fill_ratio=0.0,
                nearest_fvg_distance=1.0,
                nearest_fvg=None,
                bullish_zones=[],
                bearish_zones=[],
            )

        bullish: list[FVGZone] = []
        bearish: list[FVGZone] = []
        for idx in range(2, len(window)):
            left = window.iloc[idx - 2]
            right = window.iloc[idx]
            left_high = float(left["high"])
            left_low = float(left["low"])
            right_high = float(right["high"])
            right_low = float(right["low"])
            if right_low > left_high:
                low = left_high
                high = right_low
                bullish.append(
                    FVGZone(
                        direction="BUY",
                        created_index=idx,
                        low=low,
                        high=high,
                        fill_ratio=round(_fill_ratio(window, idx, low, high, bullish=True), 6),
                        distance=0.0,
                    )
                )
            if right_high < left_low:
                low = right_high
                high = left_low
                bearish.append(
                    FVGZone(
                        direction="SELL",
                        created_index=idx,
                        low=low,
                        high=high,
                        fill_ratio=round(_fill_ratio(window, idx, low, high, bullish=False), 6),
                        distance=0.0,
                    )
                )

        nearest = _nearest_zone(window, bullish + bearish)
        if nearest is None:
            return FVGResult(
                fvg_detected=False,
                direction="NONE",
                fvg_fill_ratio=0.0,
                nearest_fvg_distance=1.0,
                nearest_fvg=None,
                bullish_zones=[zone.to_dict() for zone in bullish],
                bearish_zones=[zone.to_dict() for zone in bearish],
            )
        return FVGResult(
            fvg_detected=True,
            direction=nearest.direction,
            fvg_fill_ratio=nearest.fill_ratio,
            nearest_fvg_distance=nearest.distance,
            nearest_fvg=nearest.to_dict(),
            bullish_zones=[zone.to_dict() for zone in bullish],
            bearish_zones=[zone.to_dict() for zone in bearish],
        )


def _fill_ratio(
    candles: pd.DataFrame,
    created_index: int,
    low: float,
    high: float,
    bullish: bool,
) -> float:
    width = max(high - low, 1e-9)
    after = candles.iloc[created_index + 1 :]
    if after.empty:
        return 0.0

    if bullish:
        deepest_low = float(after["low"].min())
        if deepest_low >= high:
            return 0.0
        if deepest_low <= low:
            return 1.0
        return _clip((high - deepest_low) / width)

    highest_high = float(after["high"].max())
    if highest_high <= low:
        return 0.0
    if highest_high >= high:
        return 1.0
    return _clip((highest_high - low) / width)


def _nearest_zone(candles: pd.DataFrame, zones: list[FVGZone]) -> FVGZone | None:
    if not zones:
        return None
    close = float(candles.iloc[-1]["close"])
    nearest = None
    best_distance = float("inf")
    for zone in zones:
        if zone.low <= close <= zone.high:
            distance = 0.0
        else:
            distance = min(abs(close - zone.low), abs(close - zone.high)) / max(abs(close), 1e-9)
        if distance < best_distance:
            best_distance = distance
            nearest = FVGZone(
                direction=zone.direction,
                created_index=zone.created_index,
                low=zone.low,
                high=zone.high,
                fill_ratio=zone.fill_ratio,
                distance=round(float(distance), 6),
            )
    return nearest


def _validate_candles(candles: pd.DataFrame) -> None:
    required = {"open", "high", "low", "close"}
    missing = [column for column in required if column not in candles]
    if missing:
        raise ValueError(f"Candle DataFrame is missing columns: {missing}.")
    if candles.empty:
        raise ValueError("Candle DataFrame must not be empty.")


def _clip(value: float) -> float:
    return max(0.0, min(float(value), 1.0))

