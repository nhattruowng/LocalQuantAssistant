"""Tests for ICT causal detectors and context builder integration."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

pd = pytest.importorskip("pandas")

from config.settings import ReasoningBrainSettings
from ict.fvg_detector import FVGDetector
from ict.ict_context_builder import ICTContextBuilder
from ict.liquidity_sweep_detector import LiquiditySweepDetector
from ict.order_block_detector import OrderBlockDetector
from reasoning.market_reasoning_brain import MarketReasoningBrain, MarketReasoningContext
from signals.models import RiskPlan, SignalType, StrategyType


def test_detect_liquidity_sweep() -> None:
    detector = LiquiditySweepDetector()
    candles = _base_candles(8)
    candles.loc[:, "high"] = [101.0, 102.0, 105.0, 103.0, 105.0, 104.0, 103.5, 106.0]
    candles.loc[:, "low"] = [99.0, 100.0, 102.0, 101.0, 102.0, 101.0, 100.5, 103.2]
    candles.loc[:, "open"] = [100.0, 101.0, 103.0, 102.0, 103.0, 102.0, 102.8, 103.8]
    candles.loc[:, "close"] = [100.5, 101.5, 104.0, 102.3, 103.8, 102.1, 102.0, 103.6]
    candles.loc[:, "volume"] = [100.0] * 7 + [180.0]

    result = detector.analyze(candles)

    assert result.detected is True
    assert result.liquidity_sweep_detected is True
    assert result.direction == "SELL"
    assert result.sweep_direction == "SELL"
    assert result.swept_level is not None
    assert result.volume_confirmed is True
    assert result.warning is None
    assert result.fakeout_risk_score < 0.55
    assert any(item.name == "Liquidity Sweep" for item in result.evidence)


def test_detect_sweep_previous_swing_low() -> None:
    detector = LiquiditySweepDetector()
    candles = _base_candles(8)
    candles.loc[:, "high"] = [109.0, 108.0, 106.0, 107.0, 105.5, 107.5, 108.0, 104.2]
    candles.loc[:, "low"] = [105.0, 103.0, 100.0, 102.0, 101.0, 102.2, 103.0, 99.0]
    candles.loc[:, "open"] = [108.0, 107.0, 104.0, 101.0, 104.0, 103.0, 104.0, 103.8]
    candles.loc[:, "close"] = [107.0, 104.0, 101.0, 106.0, 102.0, 107.0, 104.5, 103.6]
    candles.loc[:, "volume"] = [100.0] * 7 + [180.0]

    result = detector.analyze(candles)

    assert result.detected is True
    assert result.direction == "BUY"
    assert result.swept_level is not None
    assert result.rejection_score >= 0.55


def test_sweep_rejection_detected() -> None:
    detector = LiquiditySweepDetector()
    candles = _base_candles(8)
    candles.loc[:, "high"] = [101.0, 102.0, 105.0, 103.0, 105.0, 104.0, 103.5, 106.0]
    candles.loc[:, "low"] = [99.0, 100.0, 102.0, 101.0, 102.0, 101.0, 100.5, 103.2]
    candles.loc[:, "open"] = [100.0, 101.0, 103.0, 102.0, 103.0, 102.0, 102.8, 103.8]
    candles.loc[:, "close"] = [100.5, 101.5, 104.0, 102.3, 103.8, 102.1, 102.0, 103.6]
    candles.loc[:, "volume"] = [100.0] * 7 + [180.0]

    result = detector.analyze(candles)

    assert result.detected is True
    assert result.rejection_score >= 0.55


def test_sweep_with_weak_volume_creates_warning() -> None:
    detector = LiquiditySweepDetector()
    candles = _base_candles(8)
    candles.loc[:, "high"] = [101.0, 102.0, 105.0, 103.0, 105.0, 104.0, 103.5, 106.0]
    candles.loc[:, "low"] = [99.0, 100.0, 102.0, 101.0, 102.0, 101.0, 100.5, 103.2]
    candles.loc[:, "open"] = [100.0, 101.0, 103.0, 102.0, 103.0, 102.0, 102.8, 103.8]
    candles.loc[:, "close"] = [100.5, 101.5, 104.0, 102.3, 103.8, 102.1, 102.0, 103.6]
    candles.loc[:, "volume"] = [100.0] * 7 + [70.0]

    result = detector.analyze(candles)

    assert result.direction == "SELL"
    assert result.volume_confirmed is False
    assert result.warning is not None
    assert any(item.evidence_type.value == "WARNING" for item in result.evidence)
    assert result.fakeout_risk_score >= 0.55


def test_liquidity_sweep_detector_is_strictly_causal() -> None:
    detector = LiquiditySweepDetector()
    candles = _base_candles(10)
    candles.loc[:, "high"] = [101.0, 102.0, 105.0, 103.0, 105.0, 104.0, 103.5, 106.0, 130.0, 131.0]
    candles.loc[:, "low"] = [99.0, 100.0, 102.0, 101.0, 102.0, 101.0, 100.5, 103.2, 99.0, 98.0]
    candles.loc[:, "open"] = [100.0, 101.0, 103.0, 102.0, 103.0, 102.0, 102.8, 103.8, 110.0, 111.0]
    candles.loc[:, "close"] = [100.5, 101.5, 104.0, 102.3, 103.8, 102.1, 102.0, 103.6, 105.0, 104.0]
    candles.loc[:, "volume"] = [100.0] * 7 + [180.0, 400.0, 500.0]
    check_index = 7

    from_full = detector.analyze_at(candles, check_index)
    from_truncated = detector.analyze(candles.iloc[: check_index + 1])

    assert from_full.to_dict() == from_truncated.to_dict()


def test_detect_bullish_and_bearish_fvg() -> None:
    detector = FVGDetector()
    bullish = _base_candles(3)
    bullish.loc[:, ["open", "high", "low", "close"]] = [
        [99.0, 100.0, 98.0, 99.5],
        [99.5, 101.0, 99.0, 100.5],
        [102.1, 103.0, 102.0, 102.8],
    ]
    bearish = _base_candles(3)
    bearish.loc[:, ["open", "high", "low", "close"]] = [
        [101.0, 102.0, 100.0, 101.5],
        [101.2, 101.8, 100.8, 101.0],
        [98.5, 99.0, 98.0, 98.2],
    ]

    bullish_result = detector.analyze(bullish)
    bearish_result = detector.analyze(bearish)

    assert bullish_result.fvg_detected is True
    assert bullish_result.direction == "BUY"
    assert bearish_result.fvg_detected is True
    assert bearish_result.direction == "SELL"


def test_detect_basic_order_block() -> None:
    detector = OrderBlockDetector()
    candles = _base_candles(5)
    candles.loc[:, ["open", "high", "low", "close"]] = [
        [100.0, 101.0, 99.0, 100.4],
        [100.4, 101.2, 99.8, 100.0],
        [100.0, 100.8, 97.0, 98.0],   # last bearish candle
        [98.0, 103.0, 97.8, 102.4],   # impulse up
        [102.4, 103.5, 101.6, 103.0],
    ]

    result = detector.analyze(candles)

    assert result.nearest_order_block is not None
    assert result.nearest_order_block["direction"] == "BUY"
    assert result.distance_to_nearest_ob >= 0.0


def test_ict_builder_is_strictly_causal() -> None:
    builder = ICTContextBuilder(enabled=True)
    candles = _base_candles(14)
    candles.loc[:, "open"] = [100.0, 100.2, 101.0, 102.0, 102.5, 103.0, 104.5, 104.0, 104.8, 105.2, 106.2, 105.0, 104.0, 103.5]
    candles.loc[:, "high"] = [101.0, 101.6, 102.8, 103.2, 103.5, 105.0, 105.5, 104.8, 105.4, 106.8, 106.5, 105.2, 104.5, 104.2]
    candles.loc[:, "low"] = [99.0, 99.8, 100.8, 101.4, 102.0, 102.8, 103.9, 103.5, 103.9, 104.6, 104.8, 103.8, 103.2, 102.8]
    candles.loc[:, "close"] = [100.2, 101.1, 102.4, 102.8, 103.0, 104.6, 104.1, 104.6, 105.0, 106.1, 105.1, 104.2, 103.6, 103.0]
    check_index = 10

    from_full = builder.build(candles, index=check_index)
    from_truncated = builder.build(candles.iloc[: check_index + 1])

    assert from_full.to_dict() == from_truncated.to_dict()


def test_ict_disabled_still_runs() -> None:
    builder = ICTContextBuilder(enabled=False)
    context = builder.build(_base_candles(5))

    assert context.ict_score == 0.0
    assert context.evidence == []


def test_market_reasoning_brain_accepts_ict_evidence_and_trace_step() -> None:
    brain = MarketReasoningBrain(
        ReasoningBrainSettings(
            enabled=True,
            min_confluence_score=0.20,
            medium_score_threshold=0.10,
            strong_conflict_threshold=0.35,
            allow_reduced_size_for_medium_score=True,
            max_conflict_penalty=0.30,
        )
    )
    candles = _base_candles(8)
    candles.loc[:, "high"] = [101.0, 102.0, 105.0, 103.0, 105.0, 104.0, 103.5, 106.0]
    candles.loc[:, "low"] = [99.0, 100.0, 102.0, 101.0, 102.0, 101.0, 100.5, 103.2]
    candles.loc[:, "open"] = [100.0, 101.0, 103.0, 102.0, 103.0, 102.0, 102.8, 103.8]
    candles.loc[:, "close"] = [100.5, 101.5, 104.0, 102.3, 103.8, 102.1, 102.0, 103.6]
    candles.loc[:, "volume"] = [100.0] * 7 + [180.0]

    decision = brain.decide(
        MarketReasoningContext(
            symbol="BTC/USDT",
            timeframe="15m",
            market_regime="UPTREND",
            features={"regime_confidence": 0.8, "volume_ratio": 1.4},
            probabilities={"BUY": 0.74, "SELL": 0.10, "WAIT": 0.16},
            primary_signal=SignalType.BUY,
            strategy=StrategyType.TREND_FOLLOWING,
            risk_plan=_risk_plan(),
            diagnostics={"candles": candles},
            model_version="v-test",
            risk_guard_failed=False,
        )
    )

    trace_steps = decision.decision_trace["steps"]
    assert any(step["step_name"] == "ict_confluence" for step in trace_steps)
    assert any(item.source == "ict" for item in decision.evidence_for + decision.evidence_against)


def _risk_plan() -> RiskPlan:
    return RiskPlan(
        entry=100.0,
        stop_loss=95.0,
        take_profit_1=108.0,
        take_profit_2=112.0,
        risk_reward=2.4,
        position_size=100.0,
        risk_notes=[],
    )


def _base_candles(rows: int) -> pd.DataFrame:
    timestamps = pd.date_range(
        datetime(2026, 1, 1, tzinfo=UTC),
        periods=rows,
        freq="h",
    )
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": [100.0] * rows,
            "high": [101.0] * rows,
            "low": [99.0] * rows,
            "close": [100.2] * rows,
            "volume": [100.0] * rows,
            "ema_20": [100.0] * rows,
            "atr_14": [2.0] * rows,
        }
    )
