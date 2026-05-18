"""Tests for signal engine decisions."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

from config.loader import load_settings
from config.settings import Settings
from regime.market_regime import MarketRegime
from signals.models import SignalType, StrategyType
from signals.signal_engine import SignalEngine


def test_signal_engine_generates_trend_following_buy():
    engine = SignalEngine(load_settings())

    setup = engine.generate(
        symbol="BTC/USDT",
        timeframe="15m",
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        market_regime=MarketRegime.UPTREND,
        features={
            **_base_features(),
            "close": 101.0,
            "ema_20": 100.0,
            "ema_50": 95.0,
            "rsi_14": 55.0,
        },
        probabilities={"BUY": 0.70, "SELL": 0.10, "WAIT": 0.20},
    )

    assert setup.signal is SignalType.BUY
    assert setup.strategy is StrategyType.TREND_FOLLOWING
    assert setup.risk_reward == 2.0
    assert setup.position_size is not None
    assert setup.confidence > 0.0


def test_signal_engine_generates_trend_following_sell():
    engine = SignalEngine(load_settings())

    setup = engine.generate(
        symbol="BTC/USDT",
        timeframe="15m",
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        market_regime=MarketRegime.DOWNTREND,
        features={
            **_base_features(),
            "close": 99.0,
            "ema_20": 100.0,
            "ema_50": 105.0,
            "rsi_14": 45.0,
        },
        probabilities={"BUY": 0.10, "SELL": 0.70, "WAIT": 0.20},
    )

    assert setup.signal is SignalType.SELL
    assert setup.strategy is StrategyType.TREND_FOLLOWING
    assert setup.stop_loss is not None
    assert setup.stop_loss > setup.entry
    assert setup.take_profit_2 < setup.entry


def test_signal_engine_returns_wait_when_probability_is_low():
    engine = SignalEngine(load_settings())

    setup = engine.generate(
        symbol="BTC/USDT",
        timeframe="15m",
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        market_regime=MarketRegime.UPTREND,
        features={
            **_base_features(),
            "close": 101.0,
            "ema_20": 100.0,
            "ema_50": 95.0,
            "rsi_14": 55.0,
        },
        probabilities={"BUY": 0.50, "SELL": 0.10, "WAIT": 0.40},
    )

    assert setup.signal is SignalType.WAIT
    assert setup.entry is None
    assert any("probability" in reason for reason in setup.reasons)


def test_signal_engine_returns_wait_when_risk_reward_is_too_low(
    settings: Settings,
    trend_buy_features: dict[str, float],
):
    strict_settings = replace(
        settings,
        signal=replace(settings.signal, min_risk_reward=3.0),
    )
    engine = SignalEngine(strict_settings)

    setup = engine.generate(
        symbol="BTC/USDT",
        timeframe="15m",
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        market_regime=MarketRegime.UPTREND,
        features=trend_buy_features,
        probabilities={"BUY": 0.70, "SELL": 0.10, "WAIT": 0.20},
    )

    assert setup.signal is SignalType.WAIT
    assert setup.risk_reward == 2.0
    assert any("Risk/reward" in reason for reason in setup.reasons)


def test_strategy_ensemble_clear_uptrend_selects_trend_following(settings: Settings):
    engine = SignalEngine(_ensemble_settings(settings))

    setup = engine.generate(
        symbol="BTC/USDT",
        timeframe="15m",
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        market_regime=MarketRegime.UPTREND,
        features={
            **_base_features(),
            "close": 101.0,
            "ema_20": 100.0,
            "ema_50": 95.0,
            "rsi_14": 55.0,
            "regime_confidence": 0.9,
        },
        probabilities={"BUY": 0.70, "SELL": 0.10, "WAIT": 0.20},
    )

    assert setup.signal is SignalType.BUY
    assert setup.strategy is StrategyType.TREND_FOLLOWING
    assert setup.strategy_diagnostics is not None


def test_strategy_ensemble_clear_sideway_selects_mean_reversion(settings: Settings):
    engine = SignalEngine(_ensemble_settings(settings))

    setup = engine.generate(
        symbol="BTC/USDT",
        timeframe="15m",
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        market_regime=MarketRegime.SIDEWAY,
        features={
            **_base_features(),
            "close": 80.5,
            "ema_20": 100.0,
            "ema_50": 100.0,
            "rsi_14": 30.0,
            "rolling_low_20": 80.0,
            "regime_confidence": 0.9,
        },
        probabilities={"BUY": 0.62, "SELL": 0.10, "WAIT": 0.28},
    )

    assert setup.signal is SignalType.BUY
    assert setup.strategy is StrategyType.MEAN_REVERSION


def test_strategy_ensemble_clear_breakout_selects_breakout(settings: Settings):
    engine = SignalEngine(_ensemble_settings(settings))

    setup = engine.generate(
        symbol="BTC/USDT",
        timeframe="15m",
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        market_regime=MarketRegime.BREAKOUT_UP,
        features={
            **_base_features(),
            "close": 125.0,
            "ema_20": 100.0,
            "ema_50": 105.0,
            "rsi_14": 55.0,
            "volume_ratio": 2.0,
            "rolling_high_20": 120.0,
            "trend_score": 0.1,
            "regime_confidence": 0.9,
        },
        probabilities={"BUY": 0.70, "SELL": 0.10, "WAIT": 0.20},
    )

    assert setup.signal is SignalType.BUY
    assert setup.strategy is StrategyType.BREAKOUT_CONFIRMATION


def test_strategy_ensemble_low_regime_confidence_reduces_confidence(settings: Settings):
    engine = SignalEngine(
        _ensemble_settings(settings, low_regime_confidence_threshold=0.8)
    )

    setup = engine.generate(
        symbol="BTC/USDT",
        timeframe="15m",
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        market_regime=MarketRegime.UPTREND,
        features={
            **_base_features(),
            "close": 101.0,
            "ema_20": 100.0,
            "ema_50": 95.0,
            "rsi_14": 55.0,
            "regime_confidence": 0.4,
        },
        probabilities={"BUY": 0.70, "SELL": 0.10, "WAIT": 0.20},
    )

    assert setup.signal is SignalType.BUY
    assert setup.confidence < 0.7
    assert any("Regime confidence" in reason for reason in setup.reasons)


def test_strategy_ensemble_conflicting_buy_sell_returns_wait(settings: Settings):
    engine = SignalEngine(
        _ensemble_settings(settings, conflict_margin=0.2)
    )

    setup = engine.generate(
        symbol="BTC/USDT",
        timeframe="15m",
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        market_regime=MarketRegime.UPTREND,
        features={
            **_base_features(),
            "close": 100.0,
            "ema_20": 99.0,
            "ema_50": 95.0,
            "rsi_14": 55.0,
            "volume_ratio": 2.0,
            "rolling_low_20": 120.0,
            "trend_score": 1.0,
            "regime_confidence": 0.9,
        },
        probabilities={"BUY": 0.70, "SELL": 0.70, "WAIT": 0.10},
    )

    assert setup.signal is SignalType.WAIT
    assert any("conflict" in reason for reason in setup.reasons)


def test_strategy_ensemble_disabled_keeps_hard_mapping(settings: Settings):
    engine = SignalEngine(_ensemble_settings(settings, enabled=False))

    setup = engine.generate(
        symbol="BTC/USDT",
        timeframe="15m",
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        market_regime=MarketRegime.UPTREND,
        features={
            **_base_features(),
            "close": 100.0,
            "ema_20": 99.0,
            "ema_50": 95.0,
            "rsi_14": 55.0,
            "volume_ratio": 2.0,
            "rolling_low_20": 120.0,
            "trend_score": 1.0,
        },
        probabilities={"BUY": 0.70, "SELL": 0.70, "WAIT": 0.10},
    )

    assert setup.signal is SignalType.BUY
    assert setup.strategy is StrategyType.TREND_FOLLOWING


def test_multi_timeframe_buy_conflict_reduces_confidence(settings: Settings):
    engine = SignalEngine(_multi_timeframe_settings(settings, conflict_penalty=0.5))
    timestamp = datetime(2026, 1, 1, tzinfo=UTC)
    features = {
        **_base_features(),
        "close": 101.0,
        "ema_20": 100.0,
        "ema_50": 95.0,
        "rsi_14": 55.0,
        "regime_confidence": 0.9,
    }

    baseline = SignalEngine(_multi_timeframe_settings(settings, enabled=False)).generate(
        symbol="BTC/USDT",
        timeframe="15m",
        timestamp=timestamp,
        market_regime=MarketRegime.UPTREND,
        features=features,
        probabilities={"BUY": 0.70, "SELL": 0.10, "WAIT": 0.20},
        multi_timeframe_enabled=False,
    )
    setup = engine.generate(
        symbol="BTC/USDT",
        timeframe="15m",
        timestamp=timestamp,
        market_regime=MarketRegime.UPTREND,
        features=features,
        probabilities={"BUY": 0.70, "SELL": 0.10, "WAIT": 0.20},
        higher_timeframe_features={
            "1h": {
                **features,
                "market_regime": "DOWNTREND",
                "regime_confidence": 0.9,
            }
        },
    )

    assert setup.signal is SignalType.BUY
    assert setup.confidence < baseline.confidence
    assert any("Multi-timeframe conflict" in reason for reason in setup.reasons)


def test_multi_timeframe_buy_alignment_keeps_confidence(settings: Settings):
    engine = SignalEngine(_multi_timeframe_settings(settings, conflict_penalty=0.5))
    features = {
        **_base_features(),
        "close": 101.0,
        "ema_20": 100.0,
        "ema_50": 95.0,
        "rsi_14": 55.0,
        "regime_confidence": 0.9,
    }

    setup = engine.generate(
        symbol="BTC/USDT",
        timeframe="15m",
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        market_regime=MarketRegime.UPTREND,
        features=features,
        probabilities={"BUY": 0.70, "SELL": 0.10, "WAIT": 0.20},
        higher_timeframe_features={
            "1h": {
                **features,
                "market_regime": "UPTREND",
                "regime_confidence": 0.9,
            }
        },
    )

    assert setup.signal is SignalType.BUY
    assert any("aligns" in reason for reason in setup.reasons)
    assert setup.strategy_diagnostics["multi_timeframe"]["confidence_multiplier"] == 1.0


def test_multi_timeframe_missing_higher_data_does_not_crash(settings: Settings):
    engine = SignalEngine(_multi_timeframe_settings(settings))

    setup = engine.generate(
        symbol="BTC/USDT",
        timeframe="15m",
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        market_regime=MarketRegime.UPTREND,
        features={
            **_base_features(),
            "close": 101.0,
            "ema_20": 100.0,
            "ema_50": 95.0,
            "rsi_14": 55.0,
        },
        probabilities={"BUY": 0.70, "SELL": 0.10, "WAIT": 0.20},
        higher_timeframe_features={},
    )

    assert setup.signal is SignalType.BUY
    assert setup.explanation_v2 is not None
    assert setup.explanation_v2["multi_timeframe"]["missing_timeframes"] == ["1h"]


def test_explanation_v2_contains_decision_layers(settings: Settings):
    engine = SignalEngine(_multi_timeframe_settings(settings))

    setup = engine.generate(
        symbol="BTC/USDT",
        timeframe="15m",
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        market_regime=MarketRegime.UPTREND,
        features={
            **_base_features(),
            "close": 101.0,
            "ema_20": 100.0,
            "ema_50": 95.0,
            "rsi_14": 55.0,
        },
        probabilities={"BUY": 0.70, "SELL": 0.10, "WAIT": 0.20},
        higher_timeframe_features={"1h": {"market_regime": "UPTREND", "regime_confidence": 0.8}},
    )

    assert setup.explanation_v2 is not None
    assert set(setup.explanation_v2) >= {
        "final_decision",
        "regime",
        "strategy",
        "risk",
        "model",
        "multi_timeframe",
        "final_decision_summary",
    }


def test_multi_timeframe_disabled_keeps_old_behavior(settings: Settings):
    engine = SignalEngine(_multi_timeframe_settings(settings, enabled=False))

    setup = engine.generate(
        symbol="BTC/USDT",
        timeframe="15m",
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        market_regime=MarketRegime.UPTREND,
        features={
            **_base_features(),
            "close": 101.0,
            "ema_20": 100.0,
            "ema_50": 95.0,
            "rsi_14": 55.0,
        },
        probabilities={"BUY": 0.70, "SELL": 0.10, "WAIT": 0.20},
        higher_timeframe_features={
            "1h": {
                "market_regime": "DOWNTREND",
                "regime_confidence": 0.9,
            }
        },
    )

    assert setup.signal is SignalType.BUY
    assert not any("Multi-timeframe conflict" in reason for reason in setup.reasons)
    assert setup.explanation_v2["multi_timeframe"]["enabled"] is False


def _base_features() -> dict[str, float]:
    """Return common technical feature values for signal tests."""
    return {
        "atr_14": 10.0,
        "volume_ratio": 1.3,
        "rolling_high_20": 120.0,
        "rolling_low_20": 80.0,
        "trend_score": 1.0,
    }


def _ensemble_settings(
    settings: Settings,
    enabled: bool = True,
    min_strategy_score: float = 0.55,
    conflict_margin: float = 0.10,
    low_regime_confidence_threshold: float = 0.55,
) -> Settings:
    """Return settings with strategy ensemble overrides."""
    assert settings.signal.strategy_ensemble is not None
    return replace(
        settings,
        signal=replace(
            settings.signal,
            strategy_ensemble=replace(
                settings.signal.strategy_ensemble,
                enabled=enabled,
                min_strategy_score=min_strategy_score,
                conflict_margin=conflict_margin,
                low_regime_confidence_threshold=low_regime_confidence_threshold,
            ),
        ),
    )


def _multi_timeframe_settings(
    settings: Settings,
    enabled: bool = True,
    conflict_penalty: float = 0.35,
    require_higher_tf_alignment: bool = False,
) -> Settings:
    """Return settings with multi-timeframe confirmation overrides."""
    assert settings.signal.multi_timeframe is not None
    return replace(
        settings,
        signal=replace(
            settings.signal,
            multi_timeframe=replace(
                settings.signal.multi_timeframe,
                enabled=enabled,
                primary_timeframe="15m",
                confirmation_timeframes=("1h",),
                conflict_penalty=conflict_penalty,
                require_higher_tf_alignment=require_higher_tf_alignment,
            ),
        ),
    )
