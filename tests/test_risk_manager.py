"""Tests for risk management calculations."""

from __future__ import annotations

import pytest

from config.settings import Settings
from risk.risk_manager import RiskManager
from signals.models import SignalType


def test_risk_manager_calculates_buy_levels(settings: Settings):
    plan = RiskManager(settings.risk).build_plan(
        SignalType.BUY,
        {"close": 100.0, "atr_14": 10.0},
    )

    assert plan is not None
    assert plan.entry == 100.0
    assert plan.stop_loss == pytest.approx(85.0)
    assert plan.take_profit_1 == pytest.approx(120.0)
    assert plan.take_profit_2 == pytest.approx(130.0)
    assert plan.risk_reward == pytest.approx(2.0)


def test_risk_manager_calculates_sell_levels(settings: Settings):
    plan = RiskManager(settings.risk).build_plan(
        SignalType.SELL,
        {"close": 100.0, "atr_14": 10.0},
    )

    assert plan is not None
    assert plan.entry == 100.0
    assert plan.stop_loss == pytest.approx(115.0)
    assert plan.take_profit_1 == pytest.approx(80.0)
    assert plan.take_profit_2 == pytest.approx(70.0)
    assert plan.risk_reward == pytest.approx(2.0)


def test_risk_manager_calculates_position_size(settings: Settings):
    plan = RiskManager(settings.risk).build_plan(
        SignalType.BUY,
        {"close": 100.0, "atr_14": 10.0},
    )
    expected_risk_amount = settings.risk.account_balance * settings.risk.risk_per_trade_pct

    assert plan is not None
    assert plan.position_size == pytest.approx(expected_risk_amount / 15.0)


def test_risk_manager_rejects_zero_stop_distance(settings: Settings):
    manager = RiskManager(settings.risk)

    with pytest.raises(ValueError, match="positive atr_14"):
        manager.build_plan(SignalType.BUY, {"close": 100.0, "atr_14": 0.0})
