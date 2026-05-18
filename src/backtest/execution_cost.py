"""Execution cost models for backtesting."""

from __future__ import annotations

from dataclasses import replace
from typing import Mapping, Protocol

from config.settings import BacktestSettings, ExecutionCostSettings
from signals.models import SignalType


class ExecutionCostModel(Protocol):
    """Interface for trade fill and fee calculations."""

    name: str

    def calculate_entry_fill(
        self,
        price: float,
        signal: SignalType,
        row: Mapping[str, object],
    ) -> float:
        """Return simulated entry fill price."""

    def calculate_exit_fill(
        self,
        price: float,
        signal: SignalType,
        row: Mapping[str, object],
    ) -> float:
        """Return simulated exit fill price."""

    def calculate_fees(
        self,
        entry_fill: float,
        exit_fill: float,
        position_size: float,
    ) -> float:
        """Return total execution fees."""


class FixedCostModel:
    """Fixed fee and slippage model matching the original backtester behavior."""

    name = "fixed"

    def __init__(self, settings: ExecutionCostSettings) -> None:
        self._settings = settings

    def calculate_entry_fill(
        self,
        price: float,
        signal: SignalType,
        row: Mapping[str, object],
    ) -> float:
        """Apply fixed adverse entry slippage."""
        return _apply_adverse_entry(price, signal, self._slippage_rate(row))

    def calculate_exit_fill(
        self,
        price: float,
        signal: SignalType,
        row: Mapping[str, object],
    ) -> float:
        """Apply fixed adverse exit slippage."""
        return _apply_adverse_exit(price, signal, self._slippage_rate(row))

    def calculate_fees(
        self,
        entry_fill: float,
        exit_fill: float,
        position_size: float,
    ) -> float:
        """Calculate round-trip proportional fees."""
        return (
            abs(entry_fill * position_size) * self._settings.fee_rate
            + abs(exit_fill * position_size) * self._settings.fee_rate
        )

    def _slippage_rate(self, row: Mapping[str, object]) -> float:
        """Return the effective slippage rate."""
        return min(self._settings.base_slippage_rate, self._settings.max_slippage_rate)


class VolatilityAdjustedCostModel(FixedCostModel):
    """Slippage model that increases with ATR percent."""

    name = "volatility_adjusted"

    def _slippage_rate(self, row: Mapping[str, object]) -> float:
        """Return ATR-adjusted slippage capped by max_slippage_rate."""
        atr_percent = _float(row.get("atr_percent"), 0.0)
        adjusted = self._settings.base_slippage_rate * (
            1.0 + max(0.0, atr_percent) * self._settings.volatility_multiplier
        )
        return min(adjusted, self._settings.max_slippage_rate)


class SpreadAwareCostModel(FixedCostModel):
    """Cost model that uses spread column when available."""

    name = "spread_aware"

    def calculate_entry_fill(
        self,
        price: float,
        signal: SignalType,
        row: Mapping[str, object],
    ) -> float:
        """Apply half-spread adverse entry cost."""
        half_spread = self._half_spread(price, row)
        if signal is SignalType.BUY:
            return price + half_spread
        return price - half_spread

    def calculate_exit_fill(
        self,
        price: float,
        signal: SignalType,
        row: Mapping[str, object],
    ) -> float:
        """Apply half-spread adverse exit cost."""
        half_spread = self._half_spread(price, row)
        if signal is SignalType.BUY:
            return price - half_spread
        return price + half_spread

    def _half_spread(self, price: float, row: Mapping[str, object]) -> float:
        """Return half of observed or estimated spread in price units."""
        spread = row.get("spread")
        if spread is None:
            spread = row.get("bid_ask_spread")
        spread_value = _float(spread, price * self._settings.estimated_spread_rate)
        capped_spread = min(spread_value, price * self._settings.max_slippage_rate * 2.0)
        return max(0.0, capped_spread) / 2.0


class StressCostModel(SpreadAwareCostModel):
    """Worst-case cost model that multiplies slippage or spread."""

    name = "stress"

    def _slippage_rate(self, row: Mapping[str, object]) -> float:
        """Return stressed slippage capped by max_slippage_rate."""
        stressed = self._settings.base_slippage_rate * self._settings.stress_multiplier
        return min(stressed, self._settings.max_slippage_rate)

    def _half_spread(self, price: float, row: Mapping[str, object]) -> float:
        """Return stressed half-spread when spread data is available."""
        raw_spread = row.get("spread", row.get("bid_ask_spread"))
        if raw_spread is None:
            return price * self._slippage_rate(row)
        spread_value = _float(raw_spread, price * self._settings.estimated_spread_rate)
        stressed_spread = spread_value * self._settings.stress_multiplier
        capped_spread = min(stressed_spread, price * self._settings.max_slippage_rate * 2.0)
        return max(0.0, capped_spread) / 2.0


def create_execution_cost_model(
    settings: BacktestSettings,
    model_name: str | None = None,
) -> ExecutionCostModel:
    """Create an execution cost model from settings."""
    cost_settings = settings.execution_cost or ExecutionCostSettings(
        fee_rate=settings.fee_rate,
        base_slippage_rate=settings.slippage_rate,
    )
    if model_name is not None:
        cost_settings = replace(cost_settings, model=model_name)
    if cost_settings.model == "fixed":
        return FixedCostModel(cost_settings)
    if cost_settings.model == "volatility_adjusted":
        return VolatilityAdjustedCostModel(cost_settings)
    if cost_settings.model == "spread_aware":
        return SpreadAwareCostModel(cost_settings)
    if cost_settings.model == "stress":
        return StressCostModel(cost_settings)
    raise ValueError(f"Unsupported execution cost model: {cost_settings.model}.")


def scenario_cost_models(settings: BacktestSettings) -> dict[str, ExecutionCostModel]:
    """Create standard execution cost scenario models."""
    base = settings.execution_cost or ExecutionCostSettings(
        fee_rate=settings.fee_rate,
        base_slippage_rate=settings.slippage_rate,
    )
    return {
        "normal": FixedCostModel(replace(base, model="fixed")),
        "high_slippage": VolatilityAdjustedCostModel(
            replace(
                base,
                model="volatility_adjusted",
                base_slippage_rate=base.base_slippage_rate * 2.0,
            )
        ),
        "stress": StressCostModel(replace(base, model="stress")),
        "zero_slippage": FixedCostModel(
            replace(base, model="fixed", base_slippage_rate=0.0, max_slippage_rate=0.0)
        ),
    }


def _apply_adverse_entry(price: float, signal: SignalType, slippage_rate: float) -> float:
    """Apply adverse entry slippage."""
    if signal is SignalType.BUY:
        return price * (1.0 + slippage_rate)
    return price * (1.0 - slippage_rate)


def _apply_adverse_exit(price: float, signal: SignalType, slippage_rate: float) -> float:
    """Apply adverse exit slippage."""
    if signal is SignalType.BUY:
        return price * (1.0 - slippage_rate)
    return price * (1.0 + slippage_rate)


def _float(value: object, default: float) -> float:
    """Convert values to float with fallback."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
