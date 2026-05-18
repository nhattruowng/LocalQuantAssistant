"""Tests for risk guard and circuit breaker behavior."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

from config.loader import load_settings
from config.settings import RiskGuardSettings
from paper.account import PaperAccountSnapshot, PaperTrade
from risk.circuit_breaker import CircuitBreakerState
from risk.risk_guard import RiskGuard, RiskGuardContext
from risk.risk_manager import RiskManager
from signals.models import SignalType, StrategyType, TradeSetup
from signals.signal_engine import SignalEngine


NOW = datetime(2026, 1, 10, 12, tzinfo=UTC)


def test_risk_guard_blocks_daily_drawdown():
    guard = RiskGuard(_settings(max_daily_drawdown_pct=0.05))
    decision = guard.evaluate(
        _setup(),
        _context(
            equity=9_400.0,
            snapshots=[
                PaperAccountSnapshot(
                    timestamp=NOW - timedelta(hours=2),
                    initial_balance=10_000.0,
                    current_balance=10_000.0,
                    realized_pnl=0.0,
                    unrealized_pnl=0.0,
                    equity=10_000.0,
                    drawdown=0.0,
                )
            ],
        ),
    )

    assert decision.allowed is False
    assert decision.state is CircuitBreakerState.BLOCKED
    assert any("daily drawdown" in reason for reason in decision.reasons)


def test_risk_guard_blocks_consecutive_losses():
    guard = RiskGuard(_settings(max_consecutive_losses=2))
    decision = guard.evaluate(
        _setup(),
        _context(closed_trades=[_trade("LOSS", -10.0, 2), _trade("LOSS", -8.0, 1)]),
    )

    assert decision.allowed is False
    assert any("consecutive losses" in reason for reason in decision.reasons)


def test_risk_guard_cooldown_blocks_after_previous_block():
    guard = RiskGuard(_settings(cooldown_minutes_after_block=60))
    decision = guard.evaluate(
        _setup(),
        _context(last_blocked_at=NOW - timedelta(minutes=15)),
    )

    assert decision.allowed is False
    assert decision.state is CircuitBreakerState.COOLDOWN


def test_risk_guard_blocks_unstable_regime():
    guard = RiskGuard(_settings(block_low_regime_confidence=True))
    decision = guard.evaluate(
        _setup(
            strategy_diagnostics={
                "transition_warning": True,
                "regime_confidence": 0.4,
            }
        ),
        _context(),
    )

    assert decision.allowed is False
    assert any("regime" in reason for reason in decision.reasons)


def test_risk_guard_logs_event():
    events = []
    guard = RiskGuard(_settings(max_consecutive_losses=1), event_logger=events.append)

    decision = guard.evaluate(
        _setup(),
        _context(closed_trades=[_trade("LOSS", -10.0, 1)]),
    )

    assert decision.allowed is False
    assert len(events) == 1
    assert events[0].state is CircuitBreakerState.BLOCKED


def test_signal_engine_returns_wait_when_risk_guard_blocks():
    settings = replace(
        load_settings(),
        risk_guard=_settings(max_consecutive_losses=1),
    )
    engine = SignalEngine(
        settings,
        risk_manager=RiskManager(settings.risk),
        risk_guard=RiskGuard(settings.risk_guard),
        risk_guard_context=_context(closed_trades=[_trade("LOSS", -10.0, 1)]),
    )

    setup = engine.generate(
        symbol="BTC/USDT",
        timeframe="15m",
        timestamp=NOW,
        market_regime="UPTREND",
        features={
            "close": 101.0,
            "atr_14": 10.0,
            "ema_20": 100.0,
            "ema_50": 95.0,
            "rsi_14": 55.0,
            "volume_ratio": 1.3,
            "rolling_high_20": 120.0,
            "rolling_low_20": 80.0,
            "trend_score": 1.0,
        },
        probabilities={"BUY": 0.70, "SELL": 0.10, "WAIT": 0.20},
    )

    assert setup.signal is SignalType.WAIT
    assert any("risk guard" in reason for reason in setup.reasons)


def _settings(**overrides) -> RiskGuardSettings:
    values = {
        "enabled": True,
        "max_trades_per_day": 5,
        "max_consecutive_losses": 3,
        "max_daily_drawdown_pct": 0.05,
        "max_weekly_drawdown_pct": 0.10,
        "max_open_positions": 1,
        "min_time_between_trades_minutes": 0,
        "cooldown_minutes_after_block": 60,
        "require_calibrated_model": False,
        "block_low_regime_confidence": False,
    }
    values.update(overrides)
    return RiskGuardSettings(**values)


def _context(**overrides) -> RiskGuardContext:
    values = {
        "now": NOW,
        "initial_balance": 10_000.0,
        "equity": 10_000.0,
        "open_positions": [],
        "closed_trades": [],
        "snapshots": [],
        "last_blocked_at": None,
        "regime_confidence_threshold": 0.55,
    }
    values.update(overrides)
    return RiskGuardContext(**values)


def _setup(**overrides) -> TradeSetup:
    values = {
        "symbol": "BTC/USDT",
        "timeframe": "15m",
        "timestamp": NOW,
        "market_regime": "UPTREND",
        "signal": SignalType.BUY,
        "strategy": StrategyType.TREND_FOLLOWING,
        "confidence": 0.7,
        "entry": 100.0,
        "stop_loss": 90.0,
        "take_profit_1": 115.0,
        "take_profit_2": 120.0,
        "risk_reward": 2.0,
        "position_size": 1.0,
        "reasons": [],
        "risk_notes": [],
        "probability_source": "calibrated",
    }
    values.update(overrides)
    return TradeSetup(**values)


def _trade(result: str, pnl: float, hours_ago: int) -> PaperTrade:
    closed_at = NOW - timedelta(hours=hours_ago)
    return PaperTrade(
        id=None,
        symbol="BTC/USDT",
        timeframe="15m",
        direction="BUY",
        strategy="TREND_FOLLOWING",
        status="CLOSED",
        opened_at=closed_at - timedelta(hours=1),
        closed_at=closed_at,
        entry=100.0,
        stop_loss=90.0,
        take_profit_1=115.0,
        take_profit_2=120.0,
        position_size=1.0,
        confidence=0.7,
        pnl=pnl,
        result=result,
    )
