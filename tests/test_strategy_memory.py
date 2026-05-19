"""Tests for strategy memory feedback and adaptive adjustments."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

from config.settings import Settings
from paper.account import PaperTrade
from signals.adaptive_decision_engine import AdaptiveDecisionEngine
from signals.models import (
    AdaptiveThresholdContext,
    SetupGrade,
    SignalType,
    StrategyOpinion,
    StrategyType,
)
from signals.signal_engine import SignalEngine
from strategy.memory import (
    StrategyMemoryBuilder,
    StrategyMemorySnapshot,
    StrategyPerformanceMemory,
    memory_key,
)


def test_consecutive_losses_reduce_strategy_score(settings: Settings):
    config = _memory_settings(settings)
    memory = _memory(consecutive_losses=2)

    decision = AdaptiveDecisionEngine(config).decide(
        [_opinion(score=0.80)],
        _context(),
        strategy_memory=memory,
    )

    assert decision.selected_opinion is not None
    assert decision.selected_opinion.score < 0.80
    assert decision.memory_adjustments[0].score_penalty > 0


def test_three_consecutive_losses_block_strategy_when_enabled(settings: Settings):
    config = _memory_settings(settings)
    memory = _memory(consecutive_losses=3)

    decision = AdaptiveDecisionEngine(config).decide(
        [_opinion(score=0.88)],
        _context(),
        strategy_memory=memory,
    )

    assert decision.final_signal is SignalType.WAIT
    assert decision.memory_adjustments[0].blocked is True


def test_memory_does_not_intervene_before_min_samples(settings: Settings):
    config = _memory_settings(settings, memory_min_trades_required=10)
    memory = _memory(recent_trades_count=3, consecutive_losses=3)

    decision = AdaptiveDecisionEngine(config).decide(
        [_opinion(score=0.80)],
        _context(),
        strategy_memory=memory,
    )

    assert decision.memory_adjustments == []
    assert decision.selected_opinion is not None
    assert decision.selected_opinion.score == 0.80


def test_fakeout_count_penalizes_breakout_strategy(settings: Settings):
    config = _memory_settings(settings)
    memory = _memory(
        strategy_type=StrategyType.BREAKOUT_CONFIRMATION,
        regime="BREAKOUT_UP",
        recent_trades_count=12,
        consecutive_losses=1,
        fakeout_count=4,
    )

    decision = AdaptiveDecisionEngine(config).decide(
        [
            _opinion(
                score=0.78,
                strategy=StrategyType.BREAKOUT_CONFIRMATION,
            )
        ],
        _context(regime="BREAKOUT_UP"),
        strategy_memory=memory,
    )

    assert decision.memory_adjustments
    assert decision.memory_adjustments[0].score_penalty > 0
    assert "fakeouts" in " ".join(decision.memory_adjustments[0].warnings)


def test_drawdown_reduces_size_multiplier(settings: Settings):
    config = _memory_settings(settings)
    memory = _memory(recent_drawdown=120.0, recent_profit_factor=0.7)

    decision = AdaptiveDecisionEngine(config).decide(
        [_opinion(score=0.86)],
        _context(),
        strategy_memory=memory,
    )

    assert decision.selected_opinion is not None
    assert decision.selected_opinion.suggested_size_multiplier < 1.0
    assert decision.memory_adjustments[0].size_multiplier < 1.0


def test_signal_explanation_contains_memory_adjustments(settings: Settings):
    config = replace(
        settings,
        adaptive_strategy=_memory_settings(settings, memory_min_trades_required=1),
    )
    memory = _memory(recent_trades_count=5, consecutive_losses=2)
    setup = SignalEngine(settings=config, strategy_memory=memory).generate(
        symbol="BTC/USDT",
        timeframe="15m",
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        market_regime="UPTREND",
        features={
            "close": 101.0,
            "high": 102.0,
            "low": 99.0,
            "open": 100.0,
            "atr_14": 1.0,
            "atr_percent": 0.01,
            "ema_20": 100.0,
            "ema_50": 95.0,
            "rsi_14": 55.0,
            "volume_ratio": 1.3,
            "rolling_high_20": 120.0,
            "rolling_low_20": 80.0,
            "trend_score": 1.0,
            "regime_confidence": 0.85,
            "regime_scores": {"UPTREND": 0.85},
            "volatility_level": "NORMAL",
        },
        probabilities={"BUY": 0.80, "SELL": 0.10, "WAIT": 0.10},
        probability_source="calibrated",
    )

    assert setup.explanation_v2 is not None
    assert setup.explanation_v2["strategy"]["memory_adjustments"]


def test_memory_builder_computes_recent_metrics():
    started = datetime(2026, 1, 1, tzinfo=UTC)
    trades = [
        _trade(1, "WIN", 20.0, started),
        _trade(2, "LOSS", -10.0, started + timedelta(minutes=15)),
        _trade(3, "LOSS", -15.0, started + timedelta(minutes=30)),
    ]
    memory = StrategyMemoryBuilder().build(trades, lookback_trades=30)
    snapshot = next(iter(memory.snapshots.values()))

    assert snapshot.recent_trades_count == 3
    assert snapshot.recent_winrate == 0.3333
    assert snapshot.recent_profit_factor == 0.8
    assert snapshot.consecutive_losses == 2
    assert snapshot.recent_drawdown == 25.0


def _memory_settings(settings: Settings, **overrides):
    """Return adaptive settings tuned for memory tests."""
    return replace(
        settings.adaptive_strategy,
        enabled=True,
        base_threshold=0.65,
        min_opinion_score=0.55,
        allow_grade_c_signal=True,
        memory_min_trades_required=overrides.pop("memory_min_trades_required", 1),
        memory_max_score_penalty=overrides.pop("memory_max_score_penalty", 0.20),
        memory_max_size_penalty=overrides.pop("memory_max_size_penalty", 0.50),
        memory_block_after_consecutive_losses=overrides.pop(
            "memory_block_after_consecutive_losses",
            True,
        ),
        **overrides,
    )


def _context(regime: str = "UPTREND") -> AdaptiveThresholdContext:
    """Build memory-aware threshold context."""
    return AdaptiveThresholdContext(
        symbol="BTC/USDT",
        timeframe="15m",
        regime=regime,
        regime_confidence=0.85,
        uncertainty_score=0.1,
        volatility_level="NORMAL",
        probability_source="calibrated",
        volume_quality=0.5,
        trend_alignment=0.5,
    )


def _opinion(
    score: float,
    strategy: StrategyType = StrategyType.TREND_FOLLOWING,
) -> StrategyOpinion:
    """Build a test opinion."""
    return StrategyOpinion(
        strategy_type=strategy,
        suggested_signal=SignalType.BUY,
        score=score,
        confidence=0.80,
        setup_grade=SetupGrade.B,
        reasons=["test opinion"],
        warnings=[],
        passed_conditions=["passed"],
        failed_conditions=[],
        suggested_size_multiplier=1.0,
    )


def _memory(
    strategy_type: StrategyType = StrategyType.TREND_FOLLOWING,
    regime: str = "UPTREND",
    direction: SignalType = SignalType.BUY,
    recent_trades_count: int = 12,
    recent_winrate: float = 0.35,
    recent_profit_factor: float | None = 0.8,
    recent_expectancy: float = -5.0,
    recent_drawdown: float = 40.0,
    consecutive_losses: int = 2,
    fakeout_count: int = 0,
    timeout_count: int = 0,
) -> StrategyPerformanceMemory:
    """Build a memory lookup with one snapshot."""
    snapshot = StrategyMemorySnapshot(
        symbol="BTC/USDT",
        timeframe="15m",
        strategy_type=strategy_type.value,
        regime=regime,
        direction=direction.value,
        recent_trades_count=recent_trades_count,
        recent_winrate=recent_winrate,
        recent_profit_factor=recent_profit_factor,
        recent_expectancy=recent_expectancy,
        recent_drawdown=recent_drawdown,
        consecutive_losses=consecutive_losses,
        average_r_multiple=-0.2,
        fakeout_count=fakeout_count,
        timeout_count=timeout_count,
        last_updated_at=datetime(2026, 1, 1, tzinfo=UTC),
        recent_trades=[],
    )
    return StrategyPerformanceMemory(
        snapshots={
            memory_key("BTC/USDT", "15m", strategy_type, regime, direction): snapshot
        }
    )


def _trade(
    trade_id: int,
    result: str,
    pnl: float,
    opened_at: datetime,
) -> PaperTrade:
    """Build a closed paper trade."""
    return PaperTrade(
        id=trade_id,
        symbol="BTC/USDT",
        timeframe="15m",
        direction="BUY",
        strategy=StrategyType.TREND_FOLLOWING.value,
        status="CLOSED",
        opened_at=opened_at,
        closed_at=opened_at + timedelta(minutes=15),
        entry=100.0,
        stop_loss=99.0,
        take_profit_1=102.0,
        take_profit_2=103.0,
        position_size=10.0,
        confidence=0.7,
        market_regime="UPTREND",
        exit_price=103.0 if result == "WIN" else 99.0,
        pnl=pnl,
        result=result,
    )
