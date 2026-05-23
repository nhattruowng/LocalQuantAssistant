"""Strictly-causal basic order block detection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class OrderBlockZone:
    """One detected order block zone."""

    direction: str
    index: int
    low: float
    high: float
    strength: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "direction": self.direction,
            "index": self.index,
            "low": self.low,
            "high": self.high,
            "strength": self.strength,
        }


@dataclass(frozen=True)
class OrderBlockResult:
    """Order block analysis output."""

    nearest_order_block: dict[str, Any] | None
    distance_to_nearest_ob: float
    ob_mitigation_score: float
    bullish_blocks: list[dict[str, Any]]
    bearish_blocks: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "nearest_order_block": self.nearest_order_block,
            "distance_to_nearest_ob": self.distance_to_nearest_ob,
            "ob_mitigation_score": self.ob_mitigation_score,
            "bullish_blocks": self.bullish_blocks,
            "bearish_blocks": self.bearish_blocks,
        }


class OrderBlockDetector:
    """Detect last-candle-before-impulse order blocks."""

    def __init__(self, impulse_multiplier: float = 1.25) -> None:
        self._impulse_multiplier = max(0.1, float(impulse_multiplier))

    def analyze(self, candles: pd.DataFrame) -> OrderBlockResult:
        return self.analyze_at(candles, len(candles) - 1)

    def analyze_at(self, candles: pd.DataFrame, index: int) -> OrderBlockResult:
        if index < 0:
            raise ValueError("Index must be non-negative.")
        window = candles.iloc[: index + 1].copy(deep=True)
        _validate_candles(window)
        if len(window) < 4:
            return OrderBlockResult(
                nearest_order_block=None,
                distance_to_nearest_ob=1.0,
                ob_mitigation_score=0.0,
                bullish_blocks=[],
                bearish_blocks=[],
            )

        bullish = self._detect_blocks(window, bullish=True)
        bearish = self._detect_blocks(window, bullish=False)
        nearest, distance = _nearest_zone(window, bullish + bearish)
        mitigation = _mitigation_score(window, nearest, distance)

        return OrderBlockResult(
            nearest_order_block=nearest.to_dict() if nearest else None,
            distance_to_nearest_ob=round(distance, 6),
            ob_mitigation_score=round(mitigation, 6),
            bullish_blocks=[zone.to_dict() for zone in bullish],
            bearish_blocks=[zone.to_dict() for zone in bearish],
        )

    def _detect_blocks(self, candles: pd.DataFrame, bullish: bool) -> list[OrderBlockZone]:
        blocks: list[OrderBlockZone] = []
        mean_range = float((candles["high"] - candles["low"]).tail(20).mean())
        min_impulse = max(mean_range * self._impulse_multiplier, 1e-9)

        for idx in range(len(candles) - 1):
            current = candles.iloc[idx]
            next_row = candles.iloc[idx + 1]
            body = float(next_row["close"]) - float(next_row["open"])
            impulse = abs(body)
            if impulse < min_impulse:
                continue

            is_bearish_candle = float(current["close"]) < float(current["open"])
            is_bullish_candle = float(current["close"]) > float(current["open"])
            if bullish:
                if not is_bearish_candle or body <= 0:
                    continue
                if float(next_row["close"]) <= float(current["high"]):
                    continue
                direction = "BUY"
            else:
                if not is_bullish_candle or body >= 0:
                    continue
                if float(next_row["close"]) >= float(current["low"]):
                    continue
                direction = "SELL"

            zone = OrderBlockZone(
                direction=direction,
                index=idx,
                low=float(current["low"]),
                high=float(current["high"]),
                strength=_clip(impulse / max(min_impulse, 1e-9)),
            )
            blocks.append(zone)
        return blocks


def _nearest_zone(candles: pd.DataFrame, zones: list[OrderBlockZone]) -> tuple[OrderBlockZone | None, float]:
    if not zones:
        return None, 1.0
    close = float(candles.iloc[-1]["close"])
    best_zone = None
    best_distance = float("inf")
    for zone in zones:
        if zone.low <= close <= zone.high:
            return zone, 0.0
        raw_distance = min(abs(close - zone.low), abs(close - zone.high))
        norm_distance = raw_distance / max(abs(close), 1e-9)
        if norm_distance < best_distance:
            best_distance = norm_distance
            best_zone = zone
    return best_zone, float(best_distance)


def _mitigation_score(
    candles: pd.DataFrame,
    zone: OrderBlockZone | None,
    distance: float,
) -> float:
    if zone is None:
        return 0.0
    close = float(candles.iloc[-1]["close"])
    if zone.low <= close <= zone.high:
        touch = 1.0
    else:
        touch = _clip(1.0 - distance / 0.02)
    recency = _clip(1.0 - (len(candles) - 1 - zone.index) / 50.0)
    return _clip(0.65 * touch + 0.35 * recency)


def _validate_candles(candles: pd.DataFrame) -> None:
    required = {"open", "high", "low", "close"}
    missing = [column for column in required if column not in candles]
    if missing:
        raise ValueError(f"Candle DataFrame is missing columns: {missing}.")
    if candles.empty:
        raise ValueError("Candle DataFrame must not be empty.")


def _clip(value: float) -> float:
    return max(0.0, min(float(value), 1.0))

