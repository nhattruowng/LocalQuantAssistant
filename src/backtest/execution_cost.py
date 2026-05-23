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


class ZeroSlippageBaselineCostModel:
    """Baseline model with zero slippage, preserving configured fees."""

    name = "zero_slippage_baseline"

    def __init__(self, settings: ExecutionCostSettings) -> None:
        self._settings = settings

    def calculate_entry_fill(
        self,
        price: float,
        signal: SignalType,
        row: Mapping[str, object],
    ) -> float:
        return float(price)

    def calculate_exit_fill(
        self,
        price: float,
        signal: SignalType,
        row: Mapping[str, object],
    ) -> float:
        return float(price)

    def calculate_fees(
        self,
        entry_fill: float,
        exit_fill: float,
        position_size: float,
    ) -> float:
        return (
            abs(entry_fill * position_size) * self._settings.fee_rate
            + abs(exit_fill * position_size) * self._settings.fee_rate
        )


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


class DynamicCostModel(FixedCostModel):
    """Causal dynamic slippage based on ATR, volume, and volatility regime."""

    name = "dynamic"

    def _slippage_rate(self, row: Mapping[str, object]) -> float:
        base = max(0.0, self._settings.base_slippage_rate)
        atr_percent = max(0.0, _float(row.get("atr_percent"), 0.0))
        volume_ratio = max(0.0, _float(row.get("volume_ratio"), 1.0))
        volatility_level = str(row.get("volatility_level", "NORMAL")).upper()

        slippage = base + atr_percent * max(0.0, self._settings.atr_factor)
        if volume_ratio < self._settings.low_volume_threshold:
            slippage *= max(1.0, self._settings.low_volume_multiplier)
        if volatility_level == "HIGH":
            slippage *= max(1.0, self._settings.high_vol_multiplier)
        elif volatility_level == "EXTREME":
            slippage *= max(1.0, self._settings.extreme_vol_multiplier)
        return min(slippage, self._settings.max_slippage_rate)


class HighSlippageCostModel(DynamicCostModel):
    """Aggressive cost model for poor liquidity conditions."""

    name = "high_slippage"

    def _slippage_rate(self, row: Mapping[str, object]) -> float:
        baseline = super()._slippage_rate(row)
        stressed = baseline * max(1.0, self._settings.high_slippage_multiplier)
        return min(stressed, self._settings.max_slippage_rate)


class StressDynamicCostModel(DynamicCostModel):
    """Worst-case dynamic model for stress testing."""

    name = "stress"

    def _slippage_rate(self, row: Mapping[str, object]) -> float:
        baseline = super()._slippage_rate(row)
        stressed = baseline * max(1.0, self._settings.stress_multiplier)
        return min(stressed, self._settings.max_slippage_rate)


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
    if cost_settings.model in {"zero_slippage_baseline", "zero_slippage"}:
        return ZeroSlippageBaselineCostModel(cost_settings)
    if cost_settings.model in {"normal", "fixed"}:
        return FixedCostModel(cost_settings)
    if cost_settings.model == "dynamic":
        return DynamicCostModel(cost_settings)
    if cost_settings.model == "high_slippage":
        return HighSlippageCostModel(cost_settings)
    if cost_settings.model == "volatility_adjusted":
        return VolatilityAdjustedCostModel(cost_settings)
    if cost_settings.model == "spread_aware":
        return SpreadAwareCostModel(cost_settings)
    if cost_settings.model == "stress":
        return StressDynamicCostModel(cost_settings)
    if cost_settings.model == "stress_spread":
        return StressCostModel(cost_settings)
    raise ValueError(f"Unsupported execution cost model: {cost_settings.model}.")


def scenario_cost_models(settings: BacktestSettings) -> dict[str, ExecutionCostModel]:
    """Create standard execution cost scenario models."""
    base = settings.execution_cost or ExecutionCostSettings(
        fee_rate=settings.fee_rate,
        base_slippage_rate=settings.slippage_rate,
    )
    return {
        "zero_slippage_baseline": ZeroSlippageBaselineCostModel(
            replace(base, model="zero_slippage_baseline")
        ),
        "normal": DynamicCostModel(replace(base, model="dynamic")),
        "high_slippage": HighSlippageCostModel(
            replace(base, model="high_slippage")
        ),
        "stress": StressDynamicCostModel(
            replace(base, model="stress")
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
