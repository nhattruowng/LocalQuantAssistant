"""Tests for soft strategy opinion ensemble."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

from config.settings import Settings
from regime.market_regime import MarketRegime
from signals.models import SignalContext, SignalType, StrategyOpinion, StrategyType
from signals.signal_engine import SignalEngine
from strategy.opinion import opinion_to_dict
from strategy.opinion_agents import (
    BreakoutOpinionAgent,
    MeanReversionOpinionAgent,
    TrendFollowingOpinionAgent,
)


def test_near_valid_trend_setup_has_valid_score(settings: Settings):
    opinion = TrendFollowingOpinionAgent(settings.signal).evaluate(
        _context(
            market_regime=MarketRegime.UPTREND,
            features={
                **_base_features(),
                "close": 103.0,
                "ema_20": 100.0,
                "ema_50": 96.0,
                "rsi_14": 55.0,
                "regime_scores": {"UPTREND": 0.72, "BREAKOUT_UP": 0.2},
            },
            probabilities={"BUY": 0.68, "SELL": 0.12, "WAIT": 0.20},
        )
    )

    assert opinion.suggested_signal is SignalType.BUY
    assert isinstance(opinion, StrategyOpinion)
    assert opinion.evidence
    assert 0.0 <= opinion.score <= 1.0
    assert opinion.score > 0.5


def test_minor_missing_condition_does_not_hard_fail_strategy(settings: Settings):
    opinion = TrendFollowingOpinionAgent(settings.signal).evaluate(
        _context(
            market_regime=MarketRegime.UPTREND,
            features={
                **_base_features(),
                "close": 104.0,
                "ema_20": 100.0,
                "ema_50": 96.0,
                "rsi_14": 85.0,
                "regime_scores": {"UPTREND": 0.70},
            },
            probabilities={"BUY": 0.70, "SELL": 0.10, "WAIT": 0.20},
        )
    )

    assert opinion.suggested_signal is SignalType.BUY
    assert opinion.failed_conditions
    assert opinion.score > 0.35


def test_weak_strategy_returns_wait(settings: Settings):
    opinion = TrendFollowingOpinionAgent(settings.signal).evaluate(
        _context(
            market_regime=MarketRegime.SIDEWAY,
            features={
                **_base_features(),
                "close": 100.0,
                "ema_20": 100.0,
                "ema_50": 100.0,
                "rsi_14": 50.0,
                "regime_scores": {"SIDEWAY": 0.75, "UPTREND": 0.05},
            },
            probabilities={"BUY": 0.05, "SELL": 0.05, "WAIT": 0.90},
        )
    )

    assert opinion.suggested_signal is SignalType.WAIT
    assert opinion.setup_grade.value == "D"
    assert opinion.evidence
    assert any(item.evidence_type.value == "WARNING" for item in opinion.evidence)


def test_all_strategy_agents_return_standard_opinion_payload(settings: Settings):
    opinions = [
        TrendFollowingOpinionAgent(settings.signal).evaluate(
            _context(
                market_regime=MarketRegime.UPTREND,
                features={
                    **_base_features(),
                    "close": 103.0,
                    "ema_20": 100.0,
                    "ema_50": 96.0,
                    "rsi_14": 55.0,
                    "regime_scores": {"UPTREND": 0.72},
                },
                probabilities={"BUY": 0.68, "SELL": 0.12, "WAIT": 0.20},
            )
        ),
        BreakoutOpinionAgent(settings.signal).evaluate(
            _context(
                market_regime=MarketRegime.BREAKOUT_UP,
                features={
                    **_base_features(),
                    "close": 130.0,
                    "rolling_high_20": 120.0,
                    "volume_ratio": 1.6,
                    "regime_scores": {"BREAKOUT_UP": 0.76},
                },
                probabilities={"BUY": 0.72, "SELL": 0.10, "WAIT": 0.18},
            )
        ),
        MeanReversionOpinionAgent(settings.signal).evaluate(
            _context(
                market_regime=MarketRegime.SIDEWAY,
                features={
                    **_base_features(),
                    "close": 119.5,
                    "rolling_high_20": 120.0,
                    "rolling_low_20": 80.0,
                    "rsi_14": 68.0,
                    "regime_scores": {"SIDEWAY": 0.70},
                },
                probabilities={"BUY": 0.15, "SELL": 0.66, "WAIT": 0.19},
            )
        ),
    ]

    required_keys = {
        "strategy_type",
        "suggested_signal",
        "score",
        "confidence",
        "setup_grade",
        "evidence",
        "reasons",
        "warnings",
        "suggested_size_multiplier",
    }
    for opinion in opinions:
        payload = opinion_to_dict(opinion)
        assert isinstance(opinion, StrategyOpinion)
        assert required_keys.issubset(payload)
        assert opinion.strategy_type in {
            StrategyType.TREND_FOLLOWING,
            StrategyType.BREAKOUT_CONFIRMATION,
            StrategyType.MEAN_REVERSION,
        }
        assert opinion.suggested_signal in {SignalType.BUY, SignalType.SELL, SignalType.WAIT}
        assert 0.0 <= opinion.score <= 1.0
        assert 0.0 <= opinion.confidence <= 1.0
        assert 0.0 <= opinion.suggested_size_multiplier <= 1.0
        assert isinstance(payload["evidence"], list)
        assert opinion.evidence


def test_mean_reversion_warns_when_breakout_danger(settings: Settings):
    opinion = MeanReversionOpinionAgent(settings.signal).evaluate(
        _context(
            market_regime=MarketRegime.SIDEWAY,
            features={
                **_base_features(),
                "close": 119.5,
                "rolling_high_20": 120.0,
                "rolling_low_20": 80.0,
                "rsi_14": 68.0,
                "volume_ratio": 2.4,
                "atr_percent_change": 0.35,
                "regime_scores": {"SIDEWAY": 0.65, "BREAKOUT_UP": 0.45},
            },
            probabilities={"BUY": 0.15, "SELL": 0.66, "WAIT": 0.19},
            higher_timeframe_regimes={"1h": MarketRegime.UPTREND},
        )
    )

    assert opinion.suggested_signal is SignalType.SELL
    assert any("Volume ratio" in warning for warning in opinion.warnings)
    assert any("ATR" in warning for warning in opinion.warnings)


def test_breakout_warns_when_fakeout_risk(settings: Settings):
    opinion = BreakoutOpinionAgent(settings.signal).evaluate(
        _context(
            market_regime=MarketRegime.BREAKOUT_UP,
            features={
                **_base_features(),
                "open": 125.0,
                "high": 150.0,
                "low": 124.0,
                "close": 130.0,
                "rolling_high_20": 120.0,
                "volume_ratio": 1.0,
                "atr_percent": 0.06,
                "regime_scores": {"BREAKOUT_UP": 0.70},
            },
            probabilities={"BUY": 0.70, "SELL": 0.10, "WAIT": 0.20},
        )
    )

    assert opinion.suggested_signal is SignalType.BUY
    assert any("rejection wick" in warning for warning in opinion.warnings)
    assert any("Volume" in warning for warning in opinion.warnings)
    assert any("fakeout" in warning for warning in opinion.warnings)


def test_adaptive_disabled_keeps_hard_mapping(settings: Settings):
    engine = SignalEngine(_adaptive_settings(settings, enabled=False))

    setup = engine.generate(
        symbol="BTC/USDT",
        timeframe="15m",
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        market_regime=MarketRegime.SIDEWAY,
        features={
            **_base_features(),
            "close": 119.5,
            "rolling_high_20": 120.0,
            "rsi_14": 68.0,
            "regime_scores": {"UPTREND": 0.8, "SIDEWAY": 0.2},
        },
        probabilities={"BUY": 0.75, "SELL": 0.66, "WAIT": 0.10},
    )

    assert setup.strategy is StrategyType.MEAN_REVERSION


def test_adaptive_enabled_uses_strategy_opinions(settings: Settings):
    engine = SignalEngine(_adaptive_settings(settings, enabled=True))

    setup = engine.generate(
        symbol="BTC/USDT",
        timeframe="15m",
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        market_regime=MarketRegime.SIDEWAY,
        features={
            **_base_features(),
            "close": 103.0,
            "ema_20": 100.0,
            "ema_50": 96.0,
            "rsi_14": 55.0,
            "regime_scores": {"UPTREND": 0.75, "SIDEWAY": 0.20},
        },
        probabilities={"BUY": 0.72, "SELL": 0.10, "WAIT": 0.18},
    )

    assert setup.signal is SignalType.BUY
    assert setup.strategy_diagnostics is not None
    assert setup.strategy_diagnostics["adaptive_strategy"] is True
    assert setup.strategy_diagnostics["strategy_opinions"]


def _context(
    market_regime: MarketRegime,
    features: dict[str, object],
    probabilities: dict[str, float],
    higher_timeframe_regimes: dict[str, MarketRegime] | None = None,
) -> SignalContext:
    """Build a signal context for opinion tests."""
    return SignalContext(
        symbol="BTC/USDT",
        timeframe="15m",
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        market_regime=market_regime,
        features=features,
        probabilities=probabilities,
        primary_timeframe="15m",
        primary_features=features,
        primary_regime=market_regime,
        higher_timeframes=tuple((higher_timeframe_regimes or {}).keys()),
        higher_timeframe_regimes=higher_timeframe_regimes or {},
        regime_scores=features.get("regime_scores", {}),
    )


def _base_features() -> dict[str, object]:
    """Return base feature values for opinion tests."""
    return {
        "open": 100.0,
        "high": 104.0,
        "low": 98.0,
        "close": 101.0,
        "atr_14": 10.0,
        "atr_percent": 0.02,
        "atr_percent_change": 0.0,
        "ema_20": 100.0,
        "ema_50": 96.0,
        "ema_20_slope": 0.2,
        "rsi_14": 55.0,
        "volume_ratio": 1.3,
        "rolling_high_20": 120.0,
        "rolling_low_20": 80.0,
        "trend_score": 1.0,
        "regime_confidence": 0.8,
    }


def _adaptive_settings(
    settings: Settings,
    enabled: bool,
) -> Settings:
    """Return settings with adaptive strategy toggled."""
    return replace(
        settings,
        market_regime=replace(
            settings.market_regime,
            adaptive_strategy_enabled=enabled,
        ),
    )
