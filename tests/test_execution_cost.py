"""Tests for execution cost models."""

from __future__ import annotations

import pytest

from backtest.execution_cost import (
    DynamicCostModel,
    FixedCostModel,
    HighSlippageCostModel,
    StressDynamicCostModel,
    ZeroSlippageBaselineCostModel,
    scenario_cost_models,
)
from config.settings import ExecutionCostSettings
from signals.models import SignalType


def test_fixed_cost_model_buy_entry_fill():
    model = FixedCostModel(_settings(base_slippage_rate=0.001))

    assert model.calculate_entry_fill(100.0, SignalType.BUY, {}) == pytest.approx(100.1)


def test_fixed_cost_model_sell_entry_fill():
    model = FixedCostModel(_settings(base_slippage_rate=0.001))

    assert model.calculate_entry_fill(100.0, SignalType.SELL, {}) == pytest.approx(99.9)


def test_fixed_cost_model_buy_exit_fill():
    model = FixedCostModel(_settings(base_slippage_rate=0.001))

    assert model.calculate_exit_fill(100.0, SignalType.BUY, {}) == pytest.approx(99.9)


def test_fixed_cost_model_sell_exit_fill():
    model = FixedCostModel(_settings(base_slippage_rate=0.001))

    assert model.calculate_exit_fill(100.0, SignalType.SELL, {}) == pytest.approx(100.1)


def test_dynamic_slippage_is_capped():
    model = DynamicCostModel(
        _settings(
            base_slippage_rate=0.01,
            max_slippage_rate=0.02,
            atr_factor=1.0,
        )
    )

    assert model.calculate_entry_fill(
        100.0,
        SignalType.BUY,
        {"atr_percent": 1.0},
    ) == pytest.approx(102.0)


def test_high_slippage_multiplier_increases_slippage():
    model = HighSlippageCostModel(
        _settings(
            base_slippage_rate=0.002,
            high_slippage_multiplier=2.0,
            max_slippage_rate=0.01,
        )
    )

    assert model.calculate_entry_fill(100.0, SignalType.BUY, {}) == pytest.approx(100.4)


def test_stress_multiplier_increases_slippage():
    model = StressDynamicCostModel(
        _settings(
            base_slippage_rate=0.001,
            stress_multiplier=3.0,
            max_slippage_rate=0.01,
        )
    )

    assert model.calculate_entry_fill(100.0, SignalType.BUY, {}) == pytest.approx(100.3)


def test_volume_low_increases_dynamic_slippage():
    model = DynamicCostModel(
        _settings(
            base_slippage_rate=0.001,
            low_volume_threshold=0.7,
            low_volume_multiplier=2.0,
        )
    )

    normal = model.calculate_entry_fill(100.0, SignalType.BUY, {"volume_ratio": 1.2})
    low_volume = model.calculate_entry_fill(100.0, SignalType.BUY, {"volume_ratio": 0.5})

    assert low_volume > normal


def test_high_volatility_increases_dynamic_slippage():
    model = DynamicCostModel(
        _settings(
            base_slippage_rate=0.001,
            high_vol_multiplier=2.0,
        )
    )

    normal = model.calculate_entry_fill(100.0, SignalType.BUY, {"volatility_level": "NORMAL"})
    high = model.calculate_entry_fill(100.0, SignalType.BUY, {"volatility_level": "HIGH"})

    assert high > normal


def test_standard_cost_scenarios_are_available(settings):
    scenarios = scenario_cost_models(settings.backtest)

    assert list(scenarios) == [
        "zero_slippage_baseline",
        "normal",
        "high_slippage",
        "stress",
    ]


def test_stress_scenario_net_profit_not_above_baseline() -> None:
    baseline = ZeroSlippageBaselineCostModel(_settings())
    stress = StressDynamicCostModel(_settings(stress_multiplier=3.0))
    entry = 100.0
    exit_price = 110.0
    position_size = 1.0
    row = {"atr_percent": 0.03, "volume_ratio": 0.6, "volatility_level": "HIGH"}

    baseline_pnl = _trade_net_pnl(
        baseline,
        signal=SignalType.BUY,
        entry=entry,
        exit_price=exit_price,
        position_size=position_size,
        row=row,
    )
    stress_pnl = _trade_net_pnl(
        stress,
        signal=SignalType.BUY,
        entry=entry,
        exit_price=exit_price,
        position_size=position_size,
        row=row,
    )

    assert stress_pnl <= baseline_pnl


def test_fixed_model_keeps_backward_compatible_behavior():
    settings = _settings(base_slippage_rate=0.0005, fee_rate=0.001)
    model = FixedCostModel(settings)
    entry = model.calculate_entry_fill(100.0, SignalType.BUY, {})
    exit_price = model.calculate_exit_fill(130.0, SignalType.BUY, {})
    fees = model.calculate_fees(entry, exit_price, 2.0)

    assert entry == pytest.approx(100.0 * (1.0 + 0.0005))
    assert exit_price == pytest.approx(130.0 * (1.0 - 0.0005))
    assert fees == pytest.approx(abs(entry * 2.0) * 0.001 + abs(exit_price * 2.0) * 0.001)


def _settings(**overrides) -> ExecutionCostSettings:
    """Create execution cost settings for tests."""
    values = {
        "model": "fixed",
        "fee_rate": 0.001,
        "base_slippage_rate": 0.0005,
        "stress_multiplier": 3.0,
        "max_slippage_rate": 0.01,
        "volatility_multiplier": 10.0,
        "estimated_spread_rate": 0.0005,
        "atr_factor": 1.0,
        "low_volume_threshold": 0.7,
        "low_volume_multiplier": 1.4,
        "high_vol_multiplier": 1.6,
        "extreme_vol_multiplier": 2.3,
        "high_slippage_multiplier": 2.0,
    }
    values.update(overrides)
    return ExecutionCostSettings(**values)


def _trade_net_pnl(
    model,
    signal: SignalType,
    entry: float,
    exit_price: float,
    position_size: float,
    row: dict[str, object],
) -> float:
    entry_fill = model.calculate_entry_fill(entry, signal, row)
    exit_fill = model.calculate_exit_fill(exit_price, signal, row)
    gross = (exit_fill - entry_fill) * position_size if signal is SignalType.BUY else (entry_fill - exit_fill) * position_size
    fees = model.calculate_fees(entry_fill, exit_fill, position_size)
    return gross - fees
