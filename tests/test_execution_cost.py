"""Tests for execution cost models."""

from __future__ import annotations

import pytest

from backtest.execution_cost import (
    FixedCostModel,
    SpreadAwareCostModel,
    StressCostModel,
    VolatilityAdjustedCostModel,
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


def test_volatility_adjusted_slippage_is_capped():
    model = VolatilityAdjustedCostModel(
        _settings(
            base_slippage_rate=0.01,
            max_slippage_rate=0.02,
            volatility_multiplier=100.0,
        )
    )

    assert model.calculate_entry_fill(
        100.0,
        SignalType.BUY,
        {"atr_percent": 1.0},
    ) == pytest.approx(102.0)


def test_stress_multiplier_increases_slippage():
    model = StressCostModel(
        _settings(
            base_slippage_rate=0.001,
            stress_multiplier=3.0,
            max_slippage_rate=0.01,
        )
    )

    assert model.calculate_entry_fill(100.0, SignalType.BUY, {}) == pytest.approx(100.3)


def test_spread_aware_model_uses_observed_spread():
    model = SpreadAwareCostModel(_settings())

    assert model.calculate_entry_fill(
        100.0,
        SignalType.BUY,
        {"spread": 0.20},
    ) == pytest.approx(100.10)


def test_standard_cost_scenarios_are_available(settings):
    scenarios = scenario_cost_models(settings.backtest)

    assert list(scenarios) == ["normal", "high_slippage", "stress", "zero_slippage"]


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
    }
    values.update(overrides)
    return ExecutionCostSettings(**values)
