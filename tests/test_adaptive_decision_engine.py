"""Tests for adaptive decision thresholding and conflict handling."""

from __future__ import annotations

from dataclasses import replace

from config.settings import Settings
from signals.adaptive_decision_engine import AdaptiveDecisionEngine
from signals.models import (
    AdaptiveThresholdContext,
    SetupGrade,
    SetupQualityGrade,
    SignalType,
    StrategyOpinion,
    StrategyType,
)


def test_high_score_above_threshold_returns_signal(settings: Settings):
    decision = AdaptiveDecisionEngine(_adaptive(settings).adaptive_strategy).decide(
        [_opinion(SignalType.BUY, 0.78, 0.72)],
        _context(),
    )

    assert decision.final_signal is SignalType.BUY
    assert decision.selected_strategy is StrategyType.TREND_FOLLOWING
    assert decision.adaptive_threshold <= decision.final_score


def test_score_below_threshold_returns_wait(settings: Settings):
    decision = AdaptiveDecisionEngine(_adaptive(settings).adaptive_strategy).decide(
        [_opinion(SignalType.BUY, 0.60, 0.60)],
        _context(),
    )

    assert decision.final_signal is SignalType.WAIT
    assert "below adaptive threshold" in " ".join(decision.decision_reasons)


def test_buy_sell_conflict_small_gap_returns_wait(settings: Settings):
    config = replace(_adaptive(settings).adaptive_strategy, conflict_margin=0.12)
    decision = AdaptiveDecisionEngine(config).decide(
        [
            _opinion(SignalType.BUY, 0.76, 0.70),
            _opinion(SignalType.SELL, 0.70, 0.68, StrategyType.BREAKOUT_CONFIRMATION),
        ],
        _context(),
    )

    assert decision.final_signal is SignalType.WAIT
    assert decision.conflict_result.has_conflict is True


def test_high_uncertainty_increases_threshold(settings: Settings):
    config = _adaptive(settings).adaptive_strategy
    engine = AdaptiveDecisionEngine(config)

    stable = engine.decide([_opinion(SignalType.BUY, 0.66, 0.70)], _context())
    uncertain = engine.decide(
        [_opinion(SignalType.BUY, 0.66, 0.70)],
        _context(uncertainty_score=0.75),
    )

    assert uncertain.adaptive_threshold > stable.adaptive_threshold
    assert uncertain.final_signal is SignalType.WAIT


def test_high_volatility_increases_threshold(settings: Settings):
    config = _adaptive(settings).adaptive_strategy
    engine = AdaptiveDecisionEngine(config)

    normal = engine.decide([_opinion(SignalType.BUY, 0.70, 0.70)], _context())
    high_vol = engine.decide(
        [_opinion(SignalType.BUY, 0.70, 0.70)],
        _context(volatility_level="HIGH"),
    )

    assert high_vol.adaptive_threshold > normal.adaptive_threshold


def test_missing_calibration_increases_threshold_when_required(settings: Settings):
    config = replace(
        _adaptive(settings).adaptive_strategy,
        require_calibrated_probability=True,
    )
    engine = AdaptiveDecisionEngine(config)

    raw = engine.decide(
        [_opinion(SignalType.BUY, 0.69, 0.70)],
        _context(probability_source="raw"),
    )
    calibrated = engine.decide(
        [_opinion(SignalType.BUY, 0.69, 0.70)],
        _context(probability_source="calibrated"),
    )

    assert raw.adaptive_threshold > calibrated.adaptive_threshold


def test_grade_c_waits_when_grade_c_disabled(settings: Settings):
    config = replace(
        _adaptive(settings).adaptive_strategy,
        base_threshold=0.55,
        allow_grade_c_signal=False,
    )
    decision = AdaptiveDecisionEngine(config).decide(
        [_opinion(SignalType.BUY, 0.60, 0.62)],
        _context(),
    )

    assert decision.setup_quality is SetupQualityGrade.C
    assert decision.final_signal is SignalType.WAIT
    assert "Setup quality C" in decision.decision_reasons[-1]


def _adaptive(settings: Settings) -> Settings:
    """Return settings with adaptive strategy enabled."""
    return replace(
        settings,
        adaptive_strategy=replace(
            settings.adaptive_strategy,
            enabled=True,
            base_threshold=0.65,
            min_opinion_score=0.55,
            conflict_margin=0.12,
            high_uncertainty_threshold=0.45,
            require_calibrated_probability=False,
            allow_grade_c_signal=False,
        ),
    )


def _opinion(
    signal: SignalType,
    score: float,
    confidence: float,
    strategy: StrategyType = StrategyType.TREND_FOLLOWING,
) -> StrategyOpinion:
    """Build a test strategy opinion."""
    return StrategyOpinion(
        strategy_type=strategy,
        suggested_signal=signal,
        score=score,
        confidence=confidence,
        setup_grade=SetupGrade.B if score >= 0.65 else SetupGrade.C,
        reasons=["test opinion"],
        warnings=[],
        passed_conditions=["passed"],
        failed_conditions=[],
        suggested_size_multiplier=0.8,
    )


def _context(
    regime_confidence: float = 0.85,
    uncertainty_score: float = 0.10,
    volatility_level: str = "NORMAL",
    probability_source: str = "calibrated",
) -> AdaptiveThresholdContext:
    """Build a threshold context."""
    return AdaptiveThresholdContext(
        regime_confidence=regime_confidence,
        uncertainty_score=uncertainty_score,
        volatility_level=volatility_level,
        higher_timeframe_conflict=False,
        recent_strategy_performance=None,
        probability_source=probability_source,
        volume_quality=0.6,
        trend_alignment=0.6,
    )
