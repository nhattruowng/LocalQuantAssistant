"""Tests for market reasoning brain skeleton."""

from __future__ import annotations

from config.settings import ReasoningBrainSettings
from reasoning.market_reasoning_brain import MarketReasoningBrain, MarketReasoningContext
from signals.models import RiskPlan, SignalType, StrategyType
from signals.wait_reason import WaitReason


def test_consensus_evidence_returns_actionable_buy() -> None:
    brain = MarketReasoningBrain(
        ReasoningBrainSettings(
            enabled=True,
            min_confluence_score=0.55,
            medium_score_threshold=0.45,
            strong_conflict_threshold=0.30,
            allow_reduced_size_for_medium_score=True,
            max_conflict_penalty=0.30,
        )
    )
    decision = brain.decide(
        _context(
            regime="UPTREND",
            primary_signal=SignalType.BUY,
            probabilities={"BUY": 0.82, "SELL": 0.08, "WAIT": 0.10},
            diagnostics={
                "strategy_opinions": [
                    {
                        "strategy_type": "TREND_FOLLOWING",
                        "suggested_signal": "BUY",
                        "score": 0.84,
                        "confidence": 0.78,
                    },
                    {
                        "strategy_type": "BREAKOUT_CONFIRMATION",
                        "suggested_signal": "BUY",
                        "score": 0.76,
                        "confidence": 0.72,
                    },
                ],
                "multi_timeframe": {"conflict": False, "confidence_multiplier": 1.0},
            },
        )
    )

    assert decision.final_signal is SignalType.BUY
    assert decision.confluence_score >= 0.55
    assert decision.wait_reason is None


def test_high_conflict_returns_wait() -> None:
    brain = MarketReasoningBrain(ReasoningBrainSettings(enabled=True))
    decision = brain.decide(
        _context(
            regime="SIDEWAY",
            primary_signal=SignalType.BUY,
            probabilities={"BUY": 0.45, "SELL": 0.46, "WAIT": 0.09},
            diagnostics={
                "strategy_opinions": [
                    {
                        "strategy_type": "TREND_FOLLOWING",
                        "suggested_signal": "BUY",
                        "score": 0.75,
                        "confidence": 0.75,
                    },
                    {
                        "strategy_type": "MEAN_REVERSION",
                        "suggested_signal": "SELL",
                        "score": 0.75,
                        "confidence": 0.75,
                    },
                ],
                "multi_timeframe": {"conflict": True, "confidence_multiplier": 0.1},
            },
        )
    )

    assert decision.final_signal is SignalType.WAIT
    assert decision.wait_reason == WaitReason.WAIT_STRATEGY_CONFLICT.value


def test_medium_score_allows_reduced_size() -> None:
    brain = MarketReasoningBrain(
        ReasoningBrainSettings(
            enabled=True,
            min_confluence_score=0.80,
            medium_score_threshold=0.50,
            strong_conflict_threshold=0.30,
            allow_reduced_size_for_medium_score=True,
            max_conflict_penalty=0.30,
        )
    )
    decision = brain.decide(
        _context(
            regime="UPTREND",
            primary_signal=SignalType.BUY,
            probabilities={"BUY": 0.70, "SELL": 0.20, "WAIT": 0.10},
            diagnostics={
                "strategy_opinions": [
                    {
                        "strategy_type": "TREND_FOLLOWING",
                        "suggested_signal": "BUY",
                        "score": 0.76,
                        "confidence": 0.72,
                    },
                    {
                        "strategy_type": "BREAKOUT_CONFIRMATION",
                        "suggested_signal": "BUY",
                        "score": 0.66,
                        "confidence": 0.64,
                    },
                ],
                "multi_timeframe": {"conflict": False, "confidence_multiplier": 0.85},
            },
            risk_reward=2.2,
        )
    )

    assert decision.final_signal is SignalType.BUY
    assert decision.position_size_multiplier < 1.0
    assert decision.position_size_multiplier > 0.0


def test_risk_guard_fail_forces_wait_risk_block() -> None:
    brain = MarketReasoningBrain(ReasoningBrainSettings(enabled=True))
    decision = brain.decide(
        _context(
            regime="UPTREND",
            primary_signal=SignalType.BUY,
            probabilities={"BUY": 0.80, "SELL": 0.10, "WAIT": 0.10},
            diagnostics={},
            risk_guard_failed=True,
        )
    )

    assert decision.final_signal is SignalType.WAIT
    assert decision.wait_reason == WaitReason.WAIT_RISK_BLOCK.value


def test_ict_disabled_still_runs_without_crash() -> None:
    brain = MarketReasoningBrain(ReasoningBrainSettings(enabled=True))
    decision = brain.decide(
        _context(
            regime="UPTREND",
            primary_signal=SignalType.BUY,
            probabilities={"BUY": 0.78, "SELL": 0.10, "WAIT": 0.12},
            diagnostics={"ict": {"enabled": False}},
        )
    )

    assert decision.final_signal in {SignalType.BUY, SignalType.WAIT}
    assert any(step["step_name"] == "ict_confluence" for step in decision.decision_trace["steps"])


def _context(
    regime: str,
    primary_signal: SignalType,
    probabilities: dict[str, float],
    diagnostics: dict[str, object],
    risk_reward: float = 2.4,
    risk_guard_failed: bool = False,
) -> MarketReasoningContext:
    return MarketReasoningContext(
        symbol="BTC/USDT",
        timeframe="15m",
        market_regime=regime,
        features={
            "regime_confidence": 0.82,
            "volume_ratio": 1.5,
        },
        probabilities=probabilities,
        primary_signal=primary_signal,
        strategy=StrategyType.TREND_FOLLOWING,
        risk_plan=RiskPlan(
            entry=100.0,
            stop_loss=95.0,
            take_profit_1=110.0,
            take_profit_2=120.0,
            risk_reward=risk_reward,
            position_size=100.0,
            risk_notes=[],
        ),
        diagnostics=diagnostics,
        model_version="v-test",
        risk_guard_failed=risk_guard_failed,
    )
