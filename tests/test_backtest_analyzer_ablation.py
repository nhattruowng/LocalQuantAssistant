"""Tests for multi-dimensional backtest analyzer and ablation study."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

from backtest.ablation import AblationStudy, apply_component_config, resolve_component_config
from backtest.analyzer import BacktestAnalyzer
from backtest.metrics import build_report
from backtest.models import BacktestReport, Trade, TradeResult
from config.settings import SafetyFilterSettings
from signals.models import SignalType, StrategyType


def test_analyzer_groups_by_regime_and_setup_type() -> None:
    report = BacktestAnalyzer().analyze(
        [
            _trade(10.0, TradeResult.WIN, market_regime="UPTREND", setup_type="CLEAN_BREAKOUT"),
            _trade(-5.0, TradeResult.LOSS, market_regime="DOWNTREND", setup_type="RANGE_REVERSION"),
            _trade(7.0, TradeResult.WIN, market_regime="UPTREND", setup_type="CLEAN_BREAKOUT"),
        ]
    )

    assert report.grouped["regime"]["UPTREND"].total_trades == 2
    assert report.grouped["setup_type"]["CLEAN_BREAKOUT"].total_trades == 2


def test_analyzer_wait_reason_distribution() -> None:
    report = BacktestAnalyzer().analyze(
        [
            _trade(1.0, TradeResult.WIN, wait_reason="WAIT_LOW_CONFIDENCE"),
            _trade(-1.0, TradeResult.LOSS, wait_reason="WAIT_LOW_CONFIDENCE"),
            _trade(2.0, TradeResult.WIN, wait_reason="WAIT_MTF_CONFLICT"),
        ]
    )

    assert report.wait_reason_distribution["WAIT_LOW_CONFIDENCE"] == 2
    assert report.wait_reason_distribution["WAIT_MTF_CONFLICT"] == 1


def test_analyzer_groups_all_requested_dimensions() -> None:
    report = BacktestAnalyzer().analyze(
        [
            _trade(
                8.0,
                TradeResult.WIN,
                market_regime="UPTREND",
                setup_type="CLEAN_BREAKOUT",
                setup_grade="A",
                wait_reason="NONE",
                safety_filter="breakout_fakeout",
                model_scope="regime",
                probability_source="calibrated",
                conflict_level="LOW",
                confluence_score=0.83,
            ),
            _trade(
                -3.0,
                TradeResult.LOSS,
                market_regime="SIDEWAY",
                setup_type="RANGE_REVERSION",
                setup_grade="C",
                wait_reason="WAIT_LOW_CONFIDENCE",
                safety_filter="NONE",
                model_scope="global",
                probability_source="raw",
                conflict_level="MEDIUM",
                confluence_score=0.52,
                direction=SignalType.SELL,
                strategy=StrategyType.MEAN_REVERSION,
            ),
        ]
    )

    assert set(report.grouped) == {
        "regime",
        "strategy",
        "setup_type",
        "setup_grade",
        "signal",
        "wait_reason",
        "safety_filter",
        "model_scope",
        "probability_source",
        "conflict_level",
        "confluence_bucket",
    }
    assert report.grouped["setup_grade"]["A"].total_trades == 1
    assert report.grouped["signal"]["SELL"].total_trades == 1
    assert report.grouped["safety_filter"]["breakout_fakeout"].total_trades == 1
    assert report.grouped["model_scope"]["regime"].total_trades == 1
    assert report.grouped["probability_source"]["raw"].total_trades == 1
    assert report.grouped["conflict_level"]["MEDIUM"].total_trades == 1
    assert report.grouped["confluence_bucket"]["0.80-1.00"].total_trades == 1
    assert report.grouped["confluence_bucket"]["0.40-0.55"].total_trades == 1


def test_analyzer_profit_factor_handles_zero_gross_loss() -> None:
    report = BacktestAnalyzer().analyze(
        [
            _trade(10.0, TradeResult.WIN),
            _trade(5.0, TradeResult.WIN),
        ]
    )

    assert report.overall.gross_loss == 0.0
    assert report.overall.profit_factor == float("inf")


def test_ablation_applies_component_config(settings) -> None:
    baseline = resolve_component_config(settings)
    scenario = dict(baseline)
    scenario["mtf"] = False
    scenario["model_probability"] = False
    updated = apply_component_config(settings, scenario)

    assert updated.signal.multi_timeframe is not None
    assert updated.signal.multi_timeframe.enabled is False
    assert updated.signal.model_score_weight == 0.0


def test_ablation_config_does_not_mutate_original(settings) -> None:
    baseline = resolve_component_config(settings)
    scenario = {key: False for key in baseline}

    updated = apply_component_config(settings, scenario)

    assert updated is not settings
    assert resolve_component_config(settings) == baseline
    assert resolve_component_config(updated) == {key: False for key in baseline}


def test_ablation_partial_config_preserves_omitted_components(settings) -> None:
    safety_disabled = replace(
        settings,
        safety_filters=SafetyFilterSettings(
            mean_reversion_danger_enabled=False,
            breakout_fakeout_defense_enabled=False,
            extreme_volatility_block=False,
            higher_timeframe_conflict_block=False,
            mean_reversion_danger_threshold=settings.safety_filters.mean_reversion_danger_threshold,
            breakout_fakeout_threshold=settings.safety_filters.breakout_fakeout_threshold,
        ),
    )
    baseline = resolve_component_config(safety_disabled)

    updated = apply_component_config(safety_disabled, {"mtf": False})

    updated_components = resolve_component_config(updated)
    assert updated_components["mtf"] is False
    assert updated_components["safety_filter"] is baseline["safety_filter"]
    assert updated_components["memory"] is baseline["memory"]
    assert resolve_component_config(safety_disabled) == baseline


def test_ablation_no_trade_report_is_valid(settings, tmp_path) -> None:
    study = AblationStudy(output_dir=tmp_path)

    def _evaluate(_cfg, scenario: str) -> BacktestReport:
        return build_report(
            symbol="BTC/USDT",
            timeframe="15m",
            mode=scenario,
            trades=[],
        )

    result = study.run(settings, _evaluate)

    assert result.scenarios
    assert result.scenarios[0].report_summary["total_trades"] == 0
    assert result.json_path is not None and result.json_path.exists()
    assert result.csv_path is not None and result.csv_path.exists()
    assert result.html_path is not None and result.html_path.exists()


def _trade(
    pnl: float,
    result: TradeResult,
    market_regime: str = "UPTREND",
    setup_type: str = "UNKNOWN",
    setup_grade: str = "B",
    wait_reason: str = "NONE",
    safety_filter: str = "NONE",
    model_scope: str = "global",
    probability_source: str = "calibrated",
    conflict_level: str = "NONE",
    confluence_score: float = 0.7,
    direction: SignalType = SignalType.BUY,
    strategy: StrategyType = StrategyType.TREND_FOLLOWING,
) -> Trade:
    opened = datetime(2026, 1, 1, tzinfo=UTC)
    return Trade(
        symbol="BTC/USDT",
        timeframe="15m",
        direction=direction,
        strategy=strategy,
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
        result=result,
        confidence=0.72,
        reasons=[],
        market_regime=market_regime,
        confidence_bucket="0.70-0.80",
        volatility_bucket="NORMAL",
        atr_percent=0.02,
        holding_bars=3,
        setup_type=setup_type,
        setup_grade=setup_grade,
        wait_reason=wait_reason,
        safety_filter=safety_filter,
        model_scope=model_scope,
        probability_source=probability_source,
        conflict_level=conflict_level,
        confluence_score=confluence_score,
    )
