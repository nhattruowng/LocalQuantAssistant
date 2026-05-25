"""Triple-barrier labels for supervised model training."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping

import pandas as pd


class BarrierLabel(str, Enum):
    """Triple-barrier outcome labels."""

    WIN = "WIN"
    LOSS = "LOSS"
    TIMEOUT = "TIMEOUT"


@dataclass(frozen=True)
class TripleBarrierConfig:
    """Triple-barrier labeling parameters."""

    lookahead_bars: int
    take_profit_pct: float = 0.02
    stop_loss_pct: float = 0.01
    take_profit_atr_multiplier: float | None = None
    stop_loss_atr_multiplier: float | None = None

    def __post_init__(self) -> None:
        if self.lookahead_bars <= 0:
            raise ValueError("lookahead_bars must be positive.")
        if self.take_profit_pct < 0 or self.stop_loss_pct < 0:
            raise ValueError("Barrier percentages must be non-negative.")
        if self.take_profit_atr_multiplier is not None and self.take_profit_atr_multiplier < 0:
            raise ValueError("take_profit_atr_multiplier must be non-negative.")
        if self.stop_loss_atr_multiplier is not None and self.stop_loss_atr_multiplier < 0:
            raise ValueError("stop_loss_atr_multiplier must be non-negative.")


@dataclass(frozen=True)
class TripleBarrierLabel:
    """One triple-barrier label with CV-friendly metadata."""

    label: BarrierLabel
    r_multiple: float
    entry_index: int
    exit_index: int
    entry_price: float
    exit_price: float
    take_profit: float
    stop_loss: float
    direction: str
    barrier_touched: str
    lookahead_bars: int
    label_start_index: int
    label_end_index: int
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label.value,
            "r_multiple": self.r_multiple,
            "entry_index": self.entry_index,
            "exit_index": self.exit_index,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "take_profit": self.take_profit,
            "stop_loss": self.stop_loss,
            "direction": self.direction,
            "barrier_touched": self.barrier_touched,
            "lookahead_bars": self.lookahead_bars,
            "label_start_index": self.label_start_index,
            "label_end_index": self.label_end_index,
            "metadata": dict(self.metadata),
        }


class TripleBarrierLabeler:
    """Generate first-touch TP/SL/time-expiry labels inside a finite horizon."""

    def __init__(self, config: TripleBarrierConfig) -> None:
        self._config = config

    @property
    def config(self) -> TripleBarrierConfig:
        return self._config

    def label_one(
        self,
        candles: pd.DataFrame,
        entry_index: int,
        direction: str,
        entry_price: float | None = None,
        take_profit: float | None = None,
        stop_loss: float | None = None,
    ) -> TripleBarrierLabel:
        """Label one candidate using only candles in the configured label window."""
        self._validate_candles(candles)
        if entry_index < 0 or entry_index >= len(candles):
            raise IndexError("entry_index is outside candle data.")

        normalized_direction = _normalize_direction(direction)
        entry = _as_float(entry_price, _as_float(candles["close"].iat[entry_index]))
        tp, sl = self._resolve_barriers(
            candles=candles,
            entry_index=entry_index,
            direction=normalized_direction,
            entry_price=entry,
            take_profit=take_profit,
            stop_loss=stop_loss,
        )
        risk_per_unit = abs(entry - sl)
        if risk_per_unit <= 0:
            raise ValueError("stop_loss must create positive risk distance.")

        label_start = entry_index + 1
        label_end = min(entry_index + self._config.lookahead_bars, len(candles) - 1)
        if label_start > label_end:
            return self._timeout_label(
                entry_index=entry_index,
                exit_index=entry_index,
                entry=entry,
                exit_price=entry,
                take_profit=tp,
                stop_loss=sl,
                direction=normalized_direction,
                label_start=label_start,
                label_end=label_end,
                risk_per_unit=risk_per_unit,
            )

        for index in range(label_start, label_end + 1):
            high = _as_float(candles["high"].iat[index])
            low = _as_float(candles["low"].iat[index])
            tp_hit = _tp_hit(direction=normalized_direction, high=high, low=low, take_profit=tp)
            sl_hit = _sl_hit(direction=normalized_direction, high=high, low=low, stop_loss=sl)

            # Same-candle path is unknowable from OHLC, so choose conservative loss.
            if sl_hit:
                return self._final_label(
                    label=BarrierLabel.LOSS,
                    entry_index=entry_index,
                    exit_index=index,
                    entry=entry,
                    exit_price=sl,
                    take_profit=tp,
                    stop_loss=sl,
                    direction=normalized_direction,
                    barrier_touched="stop_loss",
                    label_start=label_start,
                    label_end=label_end,
                    risk_per_unit=risk_per_unit,
                )
            if tp_hit:
                return self._final_label(
                    label=BarrierLabel.WIN,
                    entry_index=entry_index,
                    exit_index=index,
                    entry=entry,
                    exit_price=tp,
                    take_profit=tp,
                    stop_loss=sl,
                    direction=normalized_direction,
                    barrier_touched="take_profit",
                    label_start=label_start,
                    label_end=label_end,
                    risk_per_unit=risk_per_unit,
                )

        exit_price = _as_float(candles["close"].iat[label_end])
        return self._timeout_label(
            entry_index=entry_index,
            exit_index=label_end,
            entry=entry,
            exit_price=exit_price,
            take_profit=tp,
            stop_loss=sl,
            direction=normalized_direction,
            label_start=label_start,
            label_end=label_end,
            risk_per_unit=risk_per_unit,
        )

    def label_candidates(
        self,
        candles: pd.DataFrame,
        candidates: pd.DataFrame | Iterable[Mapping[str, Any]],
    ) -> list[TripleBarrierLabel]:
        """Label strategy candidates with per-row barriers when provided."""
        rows = _candidate_rows(candidates)
        labels: list[TripleBarrierLabel] = []
        for row in rows:
            labels.append(
                self.label_one(
                    candles=candles,
                    entry_index=int(_row_get(row, "entry_index", _row_get(row, "index", 0))),
                    direction=str(_row_get(row, "direction", _row_get(row, "signal", "BUY"))),
                    entry_price=_optional_float(_row_get(row, "entry_price")),
                    take_profit=_optional_float(_row_get(row, "take_profit")),
                    stop_loss=_optional_float(_row_get(row, "stop_loss")),
                )
            )
        return labels

    def _validate_candles(self, candles: pd.DataFrame) -> None:
        required = ["high", "low", "close"]
        missing = [column for column in required if column not in candles]
        if missing:
            raise ValueError(f"Candle DataFrame is missing triple-barrier columns: {missing}.")
        if candles.empty:
            raise ValueError("Candle DataFrame must not be empty.")

    def _resolve_barriers(
        self,
        candles: pd.DataFrame,
        entry_index: int,
        direction: str,
        entry_price: float,
        take_profit: float | None,
        stop_loss: float | None,
    ) -> tuple[float, float]:
        tp_distance = None
        sl_distance = None
        atr = _optional_float(candles["atr_14"].iat[entry_index]) if "atr_14" in candles else None
        if atr is not None and self._config.take_profit_atr_multiplier is not None:
            tp_distance = atr * self._config.take_profit_atr_multiplier
        if atr is not None and self._config.stop_loss_atr_multiplier is not None:
            sl_distance = atr * self._config.stop_loss_atr_multiplier
        if tp_distance is None:
            tp_distance = entry_price * self._config.take_profit_pct
        if sl_distance is None:
            sl_distance = entry_price * self._config.stop_loss_pct

        if direction == "BUY":
            resolved_tp = take_profit if take_profit is not None else entry_price + tp_distance
            resolved_sl = stop_loss if stop_loss is not None else entry_price - sl_distance
        else:
            resolved_tp = take_profit if take_profit is not None else entry_price - tp_distance
            resolved_sl = stop_loss if stop_loss is not None else entry_price + sl_distance
        return float(resolved_tp), float(resolved_sl)

    def _timeout_label(
        self,
        entry_index: int,
        exit_index: int,
        entry: float,
        exit_price: float,
        take_profit: float,
        stop_loss: float,
        direction: str,
        label_start: int,
        label_end: int,
        risk_per_unit: float,
    ) -> TripleBarrierLabel:
        return self._final_label(
            label=BarrierLabel.TIMEOUT,
            entry_index=entry_index,
            exit_index=exit_index,
            entry=entry,
            exit_price=exit_price,
            take_profit=take_profit,
            stop_loss=stop_loss,
            direction=direction,
            barrier_touched="time_expiry",
            label_start=label_start,
            label_end=label_end,
            risk_per_unit=risk_per_unit,
        )

    def _final_label(
        self,
        label: BarrierLabel,
        entry_index: int,
        exit_index: int,
        entry: float,
        exit_price: float,
        take_profit: float,
        stop_loss: float,
        direction: str,
        barrier_touched: str,
        label_start: int,
        label_end: int,
        risk_per_unit: float,
    ) -> TripleBarrierLabel:
        return TripleBarrierLabel(
            label=label,
            r_multiple=round(_r_multiple(direction, entry, exit_price, risk_per_unit), 8),
            entry_index=entry_index,
            exit_index=exit_index,
            entry_price=round(entry, 8),
            exit_price=round(exit_price, 8),
            take_profit=round(take_profit, 8),
            stop_loss=round(stop_loss, 8),
            direction=direction,
            barrier_touched=barrier_touched,
            lookahead_bars=self._config.lookahead_bars,
            label_start_index=label_start,
            label_end_index=label_end,
            metadata={
                "lookahead_bars": self._config.lookahead_bars,
                "label_start_index": label_start,
                "label_end_index": label_end,
                "purge_until_index": label_end,
            },
        )


def _tp_hit(direction: str, high: float, low: float, take_profit: float) -> bool:
    return high >= take_profit if direction == "BUY" else low <= take_profit


def _sl_hit(direction: str, high: float, low: float, stop_loss: float) -> bool:
    return low <= stop_loss if direction == "BUY" else high >= stop_loss


def _r_multiple(direction: str, entry: float, exit_price: float, risk_per_unit: float) -> float:
    pnl_per_unit = exit_price - entry if direction == "BUY" else entry - exit_price
    return pnl_per_unit / risk_per_unit


def _normalize_direction(value: str) -> str:
    normalized = str(value).strip().upper()
    if normalized not in {"BUY", "SELL"}:
        raise ValueError("Triple-barrier direction must be BUY or SELL.")
    return normalized


def _candidate_rows(candidates: pd.DataFrame | Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    if isinstance(candidates, pd.DataFrame):
        return [dict(row) for row in candidates.to_dict(orient="records")]
    return [dict(item) for item in candidates]


def _row_get(row: Mapping[str, Any], key: str, default: Any = None) -> Any:
    return row.get(key, default)


def _optional_float(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    return _as_float(value)


def _as_float(value: Any, default: float | None = None) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        if default is None:
            raise
        return float(default)
