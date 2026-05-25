"""Tests for research scenario and what-if engines."""

from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd

from backtest.metrics import build_report
from backtest.models import BacktestReport, Trade, TradeResult
from backtest.scenario_engine import (
    ScenarioDefinition,
    ScenarioEngine,
    ScenarioType,
)
from backtest.what_if_engine import WhatIfChange, WhatIfEngine, apply_what_if_config
from signals.models import SignalType, StrategyType


def test_scenario_engine_runs_market_scenarios() -> None:
    features = _features()

    result = ScenarioEngine().run(
        features=features,
        evaluate_fn=_evaluate_features,
        scenarios=[
            ScenarioType.HIGH_VOLATILITY_PERIOD,
            ScenarioType.LOW_LIQUIDITY_PERIOD,
            ScenarioDefinition(
                ScenarioType.CUSTOM_DATE_RANGE,
                start="2026-01-02",
                end="2026-01-03",
            ),
        ],
    )

    assert result.baseline_result["total_trades"] == 5
    assert [item.scenario for item in result.scenarios] == [
        "high_volatility_period",
        "low_liquidity_period",
        "custom_date_range",
    ]
    assert result.scenarios[0].changed_config["row_count"] == 2
    assert result.scenarios[1].changed_config["row_count"] == 1
    assert result.scenarios[2].changed_config["row_count"] == 2
    assert result.best_scenario is not None
    assert result.worst_scenario is not None


def test_scenario_delta_vs_baseline_is_correct() -> None:
    features = _features()

    result = ScenarioEngine().run(
        features=features,
        evaluate_fn=_evaluate_features,
        scenarios=[ScenarioType.LOW_LIQUIDITY_PERIOD],
    )

    assert result.baseline_result["net_profit"] == 150.0
    assert result.scenarios[0].scenario_result["net_profit"] == 10.0
    assert result.scenarios[0].delta_vs_baseline["net_profit"] == -140.0


def test_scenario_no_trade_does_not_crash() -> None:
    features = _features()

    result = ScenarioEngine().run(
        features=features,
        evaluate_fn=_evaluate_features,
        scenarios=[
            ScenarioDefinition(
                ScenarioType.CUSTOM_DATE_RANGE,
                start="2030-01-01",
                end="2030-01-02",
            )
        ],
    )

    assert result.scenarios[0].scenario_result["total_trades"] == 0
    assert result.scenarios[0].scenario_result["net_profit"] == 0.0


def test_what_if_engine_does_not_mutate_original_config(settings) -> None:
    baseline_min_score = settings.reasoning_brain.min_confluence_score
    baseline_slippage = settings.backtest.execution_cost.model

    result = WhatIfEngine().run(
        settings=settings,
        evaluate_fn=_evaluate_settings,
        changes=[
            WhatIfChange(
                name="strict_reasoning_dynamic_cost",
                confluence_weights={"market_structure": 0.24},
                min_confluence_score=0.74,
                conflict_penalty=0.20,
                fakeout_penalty=0.30,
                slippage_mode="combined_stress",
                risk_per_trade=0.005,
                enable_price_action=True,
                enable_ict=False,
                enable_mtf=False,
                enable_memory=False,
                enable_model=False,
            )
        ],
    )

    scenario = result.scenarios[0]
    assert settings.reasoning_brain.min_confluence_score == baseline_min_score
    assert settings.backtest.execution_cost.model == baseline_slippage
    assert scenario.changed_config["min_confluence_score"] == 0.74
    assert scenario.changed_config["slippage_mode"] == "combined_stress"
    assert scenario.changed_config["ict"] is False
    assert scenario.changed_config["confluence_weights"] == {"market_structure": 0.24}


def test_what_if_delta_and_best_worst_are_correct(settings) -> None:
    result = WhatIfEngine().run(
        settings=settings,
        evaluate_fn=_evaluate_settings,
        changes=[
            WhatIfChange(name="better", risk_per_trade=0.02),
            WhatIfChange(name="worse", slippage_mode="combined_stress"),
        ],
    )

    assert result.baseline_result["net_profit"] == 10.0
    assert result.scenarios[0].scenario_result["net_profit"] == 20.0
    assert result.scenarios[0].delta_vs_baseline["net_profit"] == 10.0
    assert result.best_scenario is not None
    assert result.best_scenario.scenario == "better"
    assert result.worst_scenario is not None
    assert result.worst_scenario.scenario == "worse"


def test_apply_what_if_config_returns_new_settings(settings) -> None:
    applied = apply_what_if_config(
        settings,
        WhatIfChange(
            name="toggle_components",
            enable_price_action=False,
            enable_ict=False,
            enable_mtf=False,
            enable_memory=False,
            enable_model=False,
        ),
    )

    assert applied.settings is not settings
    assert settings.feature_toggles.price_action is True
    assert applied.settings.feature_toggles.price_action is False
    assert applied.settings.signal.model_score_weight == 0.0


def _features() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "timestamp": "2026-01-01",
                "market_regime": "UPTREND",
                "volatility_level": "NORMAL",
                "volume_ratio": 1.1,
                "atr_percent": 0.015,
                "trend_score": 0.8,
                "close": 100.0,
            },
            {
                "timestamp": "2026-01-02",
                "market_regime": "UPTREND",
                "volatility_level": "HIGH",
                "volume_ratio": 1.9,
                "atr_percent": 0.035,
                "trend_score": 0.7,
                "close": 105.0,
            },
            {
                "timestamp": "2026-01-03",
                "market_regime": "SIDEWAY",
                "volatility_level": "NORMAL",
                "volume_ratio": 0.5,
                "atr_percent": 0.010,
                "trend_score": 0.1,
                "close": 103.0,
            },
            {
                "timestamp": "2026-01-04",
                "market_regime": "DOWNTREND",
                "volatility_level": "EXTREME",
                "volume_ratio": 2.2,
                "atr_percent": 0.050,
                "trend_score": -0.9,
                "close": 94.0,
            },
            {
                "timestamp": "2026-01-05",
                "market_regime": "SIDEWAY",
                "volatility_level": "NORMAL",
                "volume_ratio": 1.0,
                "atr_percent": 0.012,
                "trend_score": 0.0,
                "close": 95.0,
            },
        ]
    )


def _evaluate_features(features: pd.DataFrame, scenario: str) -> BacktestReport:
    trades = [
        _trade(float(index + 1) * 10.0)
        for index in range(len(features))
    ]
    return build_report(
        symbol="BTC/USDT",
        timeframe="15m",
        mode=scenario,
        trades=trades,
    )


def _evaluate_settings(_settings, changed_config, scenario: str) -> BacktestReport:
    if scenario == "baseline":
        pnl = 10.0
    elif scenario == "better":
        pnl = 20.0
    elif changed_config.get("slippage_mode") == "combined_stress":
        pnl = -5.0
    else:
        pnl = 7.0
    trades = [] if pnl == 0.0 else [_trade(pnl)]
    return build_report(
        symbol="BTC/USDT",
        timeframe="15m",
        mode=scenario,
        trades=trades,
    )


def _trade(pnl: float) -> Trade:
    opened = datetime(2026, 1, 1, tzinfo=UTC)
    return Trade(
        symbol="BTC/USDT",
        timeframe="15m",
        direction=SignalType.BUY,
        strategy=StrategyType.TREND_FOLLOWING,
        opened_at=opened,
        closed_at=opened,
        entry=100.0,
        stop_loss=95.0,
        take_profit_1=110.0,
        take_profit_2=120.0,
        exit_price=105.0,
        position_size=1.0,
        gross_pnl=pnl,
        fees=0.0,
        slippage=0.0,
        pnl=pnl,
        risk_reward=2.0,
        result=TradeResult.WIN if pnl > 0 else TradeResult.LOSS,
        confidence=0.72,
        reasons=[],
    )
