"""YAML configuration loader."""

from __future__ import annotations

from pathlib import Path
import os
from typing import Any

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover - exercised only without PyYAML
    yaml = None  # type: ignore[assignment]

from config.settings import (
    AppSettings,
    AdaptiveStrategySettings,
    BacktestSettings,
    CollectorSettings,
    DatabaseSettings,
    DataSettings,
    ExecutionCostSettings,
    FeatureSettings,
    FeatureToggleSettings,
    LabelingSettings,
    LoggingSettings,
    MarketRegimeSettings,
    ModelSettings,
    NotificationSettings,
    PaperTradingSettings,
    ModelRegistrySettings,
    MultiTimeframeSettings,
    RegimeSpecificTrainingSettings,
    RiskGuardSettings,
    RiskSettings,
    SafetyFilterSettings,
    Settings,
    SignalSettings,
    StrategyEnsembleSettings,
    TrainingCalibrationSettings,
    TrainingSettings,
    TrainingValidationSettings,
)
from config.reasoning_config import (
    parse_reasoning_brain_config,
    parse_trace_config,
    validate_reasoning_brain_settings,
)


DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent / "settings.yaml"


def load_settings(config_path: str | Path | None = None) -> Settings:
    """Load application settings from YAML and environment overrides."""
    selected_path = Path(
        config_path or os.getenv("APP_CONFIG_PATH", str(DEFAULT_CONFIG_PATH))
    )
    if not selected_path.exists():
        raise FileNotFoundError(f"Config file not found: {selected_path}")

    raw_config = _read_yaml(selected_path)
    base_dir = _resolve_base_dir(selected_path)

    app_config = raw_config.get("app", {})
    database_config = raw_config.get("database", {})
    logging_config = raw_config.get("logging", {})
    data_config = raw_config.get("data", {})
    collector_config = raw_config.get("collector", {})
    features_config = raw_config.get("features", {})
    feature_toggles_config = raw_config.get("feature_toggles", {})
    regime_config = raw_config.get("market_regime", {})
    adaptive_strategy_config = raw_config.get("adaptive_strategy", {})
    if not isinstance(adaptive_strategy_config, dict):
        adaptive_strategy_config = {}
    reasoning_brain_config = raw_config.get("reasoning_brain", {})
    trace_config = raw_config.get("trace", {})
    model_config = raw_config.get("model", {})
    risk_config = raw_config.get("risk", {})
    safety_filter_config = raw_config.get("safety_filters", {})
    if not isinstance(safety_filter_config, dict):
        safety_filter_config = {}
    risk_guard_config = raw_config.get("risk_guard", {})
    if not isinstance(risk_guard_config, dict):
        risk_guard_config = {}
    signal_config = raw_config.get("signal", {})
    strategy_ensemble_config = signal_config.get("strategy_ensemble", {})
    if not isinstance(strategy_ensemble_config, dict):
        strategy_ensemble_config = {}
    multi_timeframe_config = signal_config.get("multi_timeframe", {})
    if not isinstance(multi_timeframe_config, dict):
        multi_timeframe_config = {}
    labeling_config = raw_config.get("labeling", {})
    training_config = raw_config.get("training", {})
    training_validation_config = training_config.get("validation", {})
    if not isinstance(training_validation_config, dict):
        training_validation_config = training_config
    training_calibration_config = training_config.get("calibration", {})
    if not isinstance(training_calibration_config, dict):
        training_calibration_config = {}
    regime_specific_config = training_config.get("regime_specific", {})
    if not isinstance(regime_specific_config, dict):
        regime_specific_config = {}
    training_registry_config = training_config.get("registry", {})
    if not isinstance(training_registry_config, dict):
        training_registry_config = {}
    backtest_config = raw_config.get("backtest", {})
    execution_cost_config = backtest_config.get("execution_cost", {})
    if not isinstance(execution_cost_config, dict):
        execution_cost_config = backtest_config
    notification_config = raw_config.get("notification", {})
    paper_trading_config = raw_config.get("paper_trading", {})

    database_path = os.getenv("LOCALQUANT_DB_PATH", database_config.get("path"))
    log_level = os.getenv("LOG_LEVEL", logging_config.get("level", "INFO"))
    resolved_database_path = _resolve_path(database_path or "data/localquant.db", base_dir)
    model_path = model_config.get("path")

    settings = Settings(
        app=AppSettings(
            name=app_config.get("name", "LocalQuant Assistant"),
            environment=os.getenv("LOCALQUANT_ENV", app_config.get("environment", "local")),
        ),
        database=DatabaseSettings(
            driver=database_config.get("driver", "sqlite"),
            path=resolved_database_path,
        ),
        logging=LoggingSettings(
            level=log_level,
            serialize=bool(logging_config.get("serialize", False)),
        ),
        data=DataSettings(
            min_bars=int(data_config.get("min_bars", 60)),
        ),
        collector=CollectorSettings(
            exchange=str(collector_config.get("exchange", "binance")),
            symbols=_as_tuple(collector_config.get("symbols", ["BTC/USDT", "ETH/USDT"])),
            timeframes=_as_tuple(collector_config.get("timeframes", ["15m", "1h", "4h"])),
            candles_limit=int(collector_config.get("candles_limit", 200)),
            retry_attempts=int(collector_config.get("retry_attempts", 3)),
            retry_delay_seconds=float(collector_config.get("retry_delay_seconds", 1.0)),
        ),
        features=FeatureSettings(
            fast_ma_window=int(features_config.get("fast_ma_window", 10)),
            slow_ma_window=int(features_config.get("slow_ma_window", 30)),
            volatility_window=int(features_config.get("volatility_window", 14)),
            breakout_lookback=int(features_config.get("breakout_lookback", 20)),
            output_dir=_resolve_path(
                features_config.get("output_dir", "data/processed"),
                base_dir,
            ),
            drop_warmup_rows=bool(features_config.get("drop_warmup_rows", True)),
        ),
        feature_toggles=FeatureToggleSettings(
            price_action=bool(feature_toggles_config.get("price_action", True)),
            trend=bool(feature_toggles_config.get("trend", True)),
            momentum=bool(feature_toggles_config.get("momentum", True)),
            volatility=bool(feature_toggles_config.get("volatility", True)),
            volume=bool(feature_toggles_config.get("volume", True)),
        ),
        market_regime=MarketRegimeSettings(
            trend_strength_threshold=float(
                regime_config.get("trend_strength_threshold", 0.01)
            ),
            high_volatility_threshold=float(
                regime_config.get("high_volatility_threshold", 0.04)
            ),
            breakout_buffer_pct=float(regime_config.get("breakout_buffer_pct", 0.002)),
            sideway_trend_threshold=float(
                regime_config.get("sideway_trend_threshold", 0.005)
            ),
            sideway_bollinger_width_threshold=float(
                regime_config.get("sideway_bollinger_width_threshold", 0.04)
            ),
            sideway_atr_percent_threshold=float(
                regime_config.get("sideway_atr_percent_threshold", 0.02)
            ),
            breakout_window=int(regime_config.get("breakout_window", 20)),
            breakout_volume_ratio_threshold=float(
                regime_config.get("breakout_volume_ratio_threshold", 1.5)
            ),
            breakout_atr_percent_threshold=float(
                regime_config.get("breakout_atr_percent_threshold", 0.015)
            ),
            high_volatility_percentile=float(
                regime_config.get("high_volatility_percentile", 0.8)
            ),
            low_volatility_percentile=float(
                regime_config.get("low_volatility_percentile", 0.2)
            ),
            volatility_percentile_window=int(
                regime_config.get("volatility_percentile_window", 100)
            ),
            adaptive_strategy_enabled=bool(
                adaptive_strategy_config.get("enabled", regime_config.get("adaptive_strategy_enabled", False))
            ),
        ),
        adaptive_strategy=AdaptiveStrategySettings(
            enabled=bool(adaptive_strategy_config.get("enabled", False)),
            base_threshold=float(adaptive_strategy_config.get("base_threshold", 0.65)),
            min_opinion_score=float(
                adaptive_strategy_config.get("min_opinion_score", 0.55)
            ),
            conflict_margin=float(
                adaptive_strategy_config.get("conflict_margin", 0.12)
            ),
            high_uncertainty_threshold=float(
                adaptive_strategy_config.get("high_uncertainty_threshold", 0.45)
            ),
            require_calibrated_probability=bool(
                adaptive_strategy_config.get("require_calibrated_probability", False)
            ),
            allow_grade_c_signal=bool(
                adaptive_strategy_config.get("allow_grade_c_signal", False)
            ),
            memory_lookback_trades=int(
                adaptive_strategy_config.get("memory_lookback_trades", 30)
            ),
            memory_lookback_bars=int(
                adaptive_strategy_config.get("memory_lookback_bars", 200)
            ),
            memory_min_trades_required=int(
                adaptive_strategy_config.get("memory_min_trades_required", 10)
            ),
            memory_max_score_penalty=float(
                adaptive_strategy_config.get("memory_max_score_penalty", 0.20)
            ),
            memory_max_size_penalty=float(
                adaptive_strategy_config.get("memory_max_size_penalty", 0.50)
            ),
            memory_block_after_consecutive_losses=bool(
                adaptive_strategy_config.get(
                    "memory_block_after_consecutive_losses",
                    True,
                )
            ),
        ),
        reasoning_brain=parse_reasoning_brain_config(reasoning_brain_config),
        trace=parse_trace_config(trace_config),
        model=ModelSettings(
            path=_resolve_path(model_path, base_dir) if model_path else None,
            fallback_action_probability=float(
                model_config.get("fallback_action_probability", 0.62)
            ),
            fallback_wait_probability=float(
                model_config.get("fallback_wait_probability", 0.23)
            ),
            fallback_opposite_probability=float(
                model_config.get("fallback_opposite_probability", 0.15)
            ),
        ),
        risk=RiskSettings(
            account_balance=float(risk_config.get("account_balance", 10_000.0)),
            risk_per_trade_pct=float(risk_config.get("risk_per_trade_pct", 0.01)),
            stop_loss_pct=float(risk_config.get("stop_loss_pct", 0.01)),
            take_profit_pct=float(risk_config.get("take_profit_pct", 0.02)),
            stop_loss_atr_multiplier=float(
                risk_config.get("stop_loss_atr_multiplier", 1.5)
            ),
            take_profit_1_atr_multiplier=float(
                risk_config.get("take_profit_1_atr_multiplier", 2.0)
            ),
            take_profit_2_atr_multiplier=float(
                risk_config.get("take_profit_2_atr_multiplier", 3.0)
            ),
            dynamic_sizing_enabled=bool(
                risk_config.get("dynamic_sizing_enabled", True)
            ),
            max_risk_per_trade_pct=float(
                risk_config.get("max_risk_per_trade_pct", 1.0)
            ),
            min_risk_reward=float(risk_config.get("min_risk_reward", 2.0)),
        ),
        safety_filters=SafetyFilterSettings(
            mean_reversion_danger_enabled=bool(
                safety_filter_config.get("mean_reversion_danger_enabled", True)
            ),
            breakout_fakeout_defense_enabled=bool(
                safety_filter_config.get("breakout_fakeout_defense_enabled", True)
            ),
            extreme_volatility_block=bool(
                safety_filter_config.get("extreme_volatility_block", True)
            ),
            higher_timeframe_conflict_block=bool(
                safety_filter_config.get("higher_timeframe_conflict_block", True)
            ),
            mean_reversion_danger_threshold=float(
                safety_filter_config.get("mean_reversion_danger_threshold", 0.70)
            ),
            breakout_fakeout_threshold=float(
                safety_filter_config.get("breakout_fakeout_threshold", 0.55)
            ),
        ),
        risk_guard=RiskGuardSettings(
            enabled=bool(risk_guard_config.get("enabled", False)),
            max_trades_per_day=int(risk_guard_config.get("max_trades_per_day", 5)),
            max_consecutive_losses=int(
                risk_guard_config.get("max_consecutive_losses", 3)
            ),
            max_daily_drawdown_pct=float(
                risk_guard_config.get("max_daily_drawdown_pct", 0.05)
            ),
            max_weekly_drawdown_pct=float(
                risk_guard_config.get("max_weekly_drawdown_pct", 0.10)
            ),
            max_open_positions=int(risk_guard_config.get("max_open_positions", 1)),
            min_time_between_trades_minutes=int(
                risk_guard_config.get("min_time_between_trades_minutes", 30)
            ),
            cooldown_minutes_after_block=int(
                risk_guard_config.get("cooldown_minutes_after_block", 60)
            ),
            require_calibrated_model=bool(
                risk_guard_config.get("require_calibrated_model", False)
            ),
            block_low_regime_confidence=bool(
                risk_guard_config.get("block_low_regime_confidence", False)
            ),
            hard_block_data_quality_fail=bool(
                risk_guard_config.get("hard_block_data_quality_fail", True)
            ),
            hard_block_extreme_volatility=bool(
                risk_guard_config.get("hard_block_extreme_volatility", True)
            ),
            hard_block_daily_drawdown=bool(
                risk_guard_config.get("hard_block_daily_drawdown", True)
            ),
            hard_block_risk_reward_fail=bool(
                risk_guard_config.get("hard_block_risk_reward_fail", True)
            ),
        ),
        signal=SignalSettings(
            min_confidence=float(signal_config.get("min_confidence", 0.55)),
            min_risk_reward=float(signal_config.get("min_risk_reward", 2.0)),
            use_calibrated_probability=bool(
                signal_config.get("use_calibrated_probability", True)
            ),
            trend_probability_threshold=float(
                signal_config.get("trend_probability_threshold", 0.65)
            ),
            breakout_probability_threshold=float(
                signal_config.get("breakout_probability_threshold", 0.65)
            ),
            mean_reversion_probability_threshold=float(
                signal_config.get("mean_reversion_probability_threshold", 0.60)
            ),
            ema_near_pct=float(signal_config.get("ema_near_pct", 0.01)),
            breakout_volume_ratio_threshold=float(
                signal_config.get("breakout_volume_ratio_threshold", 1.2)
            ),
            support_resistance_near_pct=float(
                signal_config.get("support_resistance_near_pct", 0.01)
            ),
            trend_buy_rsi_min=float(signal_config.get("trend_buy_rsi_min", 40.0)),
            trend_buy_rsi_max=float(signal_config.get("trend_buy_rsi_max", 70.0)),
            trend_sell_rsi_min=float(signal_config.get("trend_sell_rsi_min", 30.0)),
            trend_sell_rsi_max=float(signal_config.get("trend_sell_rsi_max", 60.0)),
            mean_reversion_buy_rsi_max=float(
                signal_config.get("mean_reversion_buy_rsi_max", 35.0)
            ),
            mean_reversion_sell_rsi_min=float(
                signal_config.get("mean_reversion_sell_rsi_min", 65.0)
            ),
            model_score_weight=float(signal_config.get("model_score_weight", 0.40)),
            trend_score_weight=float(signal_config.get("trend_score_weight", 0.25)),
            indicator_score_weight=float(
                signal_config.get("indicator_score_weight", 0.20)
            ),
            volume_score_weight=float(signal_config.get("volume_score_weight", 0.10)),
            risk_reward_score_weight=float(
                signal_config.get("risk_reward_score_weight", 0.05)
            ),
            strategy_ensemble=StrategyEnsembleSettings(
                enabled=bool(strategy_ensemble_config.get("enabled", False)),
                min_strategy_score=float(
                    strategy_ensemble_config.get("min_strategy_score", 0.55)
                ),
                conflict_margin=float(
                    strategy_ensemble_config.get("conflict_margin", 0.10)
                ),
                low_regime_confidence_threshold=float(
                    strategy_ensemble_config.get(
                        "low_regime_confidence_threshold",
                        0.55,
                    )
                ),
            ),
            multi_timeframe=MultiTimeframeSettings(
                enabled=bool(multi_timeframe_config.get("enabled", False)),
                primary_timeframe=str(
                    multi_timeframe_config.get("primary_timeframe", "15m")
                ),
                confirmation_timeframes=_as_tuple(
                    multi_timeframe_config.get(
                        "confirmation_timeframes",
                        ["1h", "4h"],
                    )
                ),
                conflict_penalty=float(
                    multi_timeframe_config.get("conflict_penalty", 0.35)
                ),
                require_higher_tf_alignment=bool(
                    multi_timeframe_config.get(
                        "require_higher_tf_alignment",
                        False,
                    )
                ),
            ),
        ),
        labeling=LabelingSettings(
            lookahead_bars=int(labeling_config.get("lookahead_bars", 10)),
            stop_loss_atr_multiplier=float(
                labeling_config.get("stop_loss_atr_multiplier", 1.5)
            ),
            take_profit_atr_multiplier=float(
                labeling_config.get("take_profit_atr_multiplier", 3.0)
            ),
        ),
        training=TrainingSettings(
            train_ratio=float(training_config.get("train_ratio", 0.70)),
            validation_ratio=float(training_config.get("validation_ratio", 0.15)),
            test_ratio=float(training_config.get("test_ratio", 0.15)),
            random_state=int(training_config.get("random_state", 42)),
            n_estimators=int(training_config.get("n_estimators", 300)),
            max_depth=_optional_int(training_config.get("max_depth", None)),
            model_dir=_resolve_path(training_config.get("model_dir", "models"), base_dir),
            validation=TrainingValidationSettings(
                method=str(training_validation_config.get("method", "time_split")),
                n_splits=int(training_validation_config.get("n_splits", 5)),
                train_window_bars=int(
                    training_validation_config.get("train_window_bars", 500)
                ),
                validation_window_bars=int(
                    training_validation_config.get("validation_window_bars", 100)
                ),
                test_window_bars=int(
                    training_validation_config.get("test_window_bars", 0)
                ),
                expanding_window=bool(
                    training_validation_config.get("expanding_window", True)
                ),
                purge_size=int(training_validation_config.get("purge_size", 0)),
                embargo_size=int(training_validation_config.get("embargo_size", 0)),
            ),
            calibration=TrainingCalibrationSettings(
                enabled=bool(training_calibration_config.get("enabled", False)),
                method=str(training_calibration_config.get("method", "sigmoid")),
                cv=_parse_calibration_cv(
                    training_calibration_config.get("cv", "prefit")
                ),
            ),
            regime_specific=RegimeSpecificTrainingSettings(
                enabled=bool(regime_specific_config.get("enabled", False)),
                min_samples_per_regime=int(
                    regime_specific_config.get("min_samples_per_regime", 200)
                ),
                allowed_regimes=_as_tuple(
                    regime_specific_config.get(
                        "allowed_regimes",
                        [
                            "UPTREND",
                            "DOWNTREND",
                            "SIDEWAY",
                            "BREAKOUT_UP",
                            "BREAKOUT_DOWN",
                        ],
                    )
                ),
                min_validation_accuracy=float(
                    regime_specific_config.get("min_validation_accuracy", 0.0)
                ),
            ),
            registry=ModelRegistrySettings(
                auto_promote_champion=bool(
                    training_registry_config.get("auto_promote_champion", True)
                ),
            ),
        ),
        backtest=BacktestSettings(
            fee_rate=float(backtest_config.get("fee_rate", 0.001)),
            slippage_rate=float(backtest_config.get("slippage_rate", 0.0005)),
            cooldown_bars_after_loss=int(
                backtest_config.get("cooldown_bars_after_loss", 3)
            ),
            max_holding_bars=int(backtest_config.get("max_holding_bars", 10)),
            output_dir=_resolve_path(backtest_config.get("output_dir", "data/backtest"), base_dir),
            volatility_low_max=float(backtest_config.get("volatility_low_max", 0.01)),
            volatility_normal_max=float(backtest_config.get("volatility_normal_max", 0.025)),
            volatility_high_max=float(backtest_config.get("volatility_high_max", 0.05)),
            execution_cost=ExecutionCostSettings(
                model=str(execution_cost_config.get("model", "fixed")),
                fee_rate=float(
                    execution_cost_config.get(
                        "fee_rate",
                        backtest_config.get("fee_rate", 0.001),
                    )
                ),
                base_slippage_rate=float(
                    execution_cost_config.get(
                        "base_slippage_rate",
                        backtest_config.get("slippage_rate", 0.0005),
                    )
                ),
                stress_multiplier=float(
                    execution_cost_config.get("stress_multiplier", 3.0)
                ),
                max_slippage_rate=float(
                    execution_cost_config.get("max_slippage_rate", 0.01)
                ),
                volatility_multiplier=float(
                    execution_cost_config.get("volatility_multiplier", 10.0)
                ),
                estimated_spread_rate=float(
                    execution_cost_config.get(
                        "estimated_spread_rate",
                        execution_cost_config.get(
                            "base_slippage_rate",
                            backtest_config.get("slippage_rate", 0.0005),
                        ),
                    )
                ),
                atr_factor=float(execution_cost_config.get("atr_factor", 1.0)),
                low_volume_threshold=float(
                    execution_cost_config.get("low_volume_threshold", 0.7)
                ),
                low_volume_multiplier=float(
                    execution_cost_config.get("low_volume_multiplier", 1.4)
                ),
                high_vol_multiplier=float(
                    execution_cost_config.get("high_vol_multiplier", 1.6)
                ),
                extreme_vol_multiplier=float(
                    execution_cost_config.get("extreme_vol_multiplier", 2.3)
                ),
                high_slippage_multiplier=float(
                    execution_cost_config.get("high_slippage_multiplier", 2.0)
                ),
            ),
        ),
        notification=NotificationSettings(
            enabled=bool(notification_config.get("enabled", False)),
            telegram_bot_token=_optional_env("TELEGRAM_BOT_TOKEN"),
            telegram_chat_id=_optional_env("TELEGRAM_CHAT_ID"),
            min_confidence=float(notification_config.get("min_confidence", 0.70)),
            min_risk_reward=float(notification_config.get("min_risk_reward", 2.0)),
            cooldown_seconds=int(notification_config.get("cooldown_seconds", 900)),
            request_timeout_seconds=float(
                notification_config.get("request_timeout_seconds", 5.0)
            ),
        ),
        paper_trading=PaperTradingSettings(
            enabled=bool(paper_trading_config.get("enabled", False)),
            initial_balance=float(paper_trading_config.get("initial_balance", 10_000.0)),
        ),
    )
    _validate_settings(settings)
    return settings


def _read_yaml(path: Path) -> dict[str, Any]:
    """Read a YAML file into a dictionary."""
    with path.open("r", encoding="utf-8") as file:
        content = file.read()

    if yaml is None:
        loaded = _read_simple_yaml(content)
    else:
        loaded = yaml.safe_load(content) or {}

    if not isinstance(loaded, dict):
        raise ValueError(f"Config root must be a mapping: {path}")
    return loaded


def _read_simple_yaml(content: str) -> dict[str, Any]:
    """Parse the nested mapping subset used by the default config."""
    parsed: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(-1, parsed)]

    for raw_line in content.splitlines():
        line = raw_line.split("#", maxsplit=1)[0].rstrip()
        if not line:
            continue
        if ":" not in line:
            raise ValueError("Only simple YAML mappings are supported.")

        indent = len(raw_line) - len(raw_line.lstrip(" "))
        key, value = line.strip().split(":", maxsplit=1)
        while stack and indent <= stack[-1][0]:
            stack.pop()
        if not stack:
            raise ValueError("Invalid YAML indentation.")

        parent = stack[-1][1]
        value = value.strip()
        if value == "":
            child: dict[str, Any] = {}
            parent[key] = child
            stack.append((indent, child))
        else:
            parent[key] = _parse_scalar(value)

    return parsed


def _parse_scalar(value: str) -> Any:
    """Parse a simple YAML scalar value."""
    normalized = value.strip("'\"")
    if normalized.lower() == "true":
        return True
    if normalized.lower() == "false":
        return False
    if normalized.lower() in {"null", "none", ""}:
        return None
    if normalized.startswith("[") and normalized.endswith("]"):
        values = normalized.removeprefix("[").removesuffix("]").split(",")
        return [_parse_scalar(value.strip()) for value in values if value.strip()]
    try:
        return int(normalized)
    except ValueError:
        pass
    try:
        return float(normalized)
    except ValueError:
        pass
    return normalized


def _resolve_base_dir(config_path: Path) -> Path:
    """Resolve relative paths from project root for the default src/config layout."""
    resolved = config_path.resolve()
    if resolved.parent.name == "config" and resolved.parent.parent.name == "src":
        return resolved.parents[2]
    return resolved.parent


def _resolve_path(path_value: str | Path, base_dir: Path) -> Path:
    """Resolve a configured path against a base directory."""
    path = Path(path_value)
    if path.is_absolute():
        return path
    return base_dir / path


def _as_tuple(value: Any) -> tuple[str, ...]:
    """Convert a YAML scalar or list into a tuple of strings."""
    if isinstance(value, str):
        return (value,)
    if isinstance(value, list | tuple):
        return tuple(str(item) for item in value)
    raise ValueError(f"Expected string or list value, got {type(value).__name__}.")


def _optional_int(value: Any) -> int | None:
    """Parse optional integer config values."""
    if value is None:
        return None
    return int(value)


def _parse_calibration_cv(value: Any) -> str | int:
    """Parse calibration CV config."""
    if isinstance(value, str) and value.strip().lower() == "prefit":
        return "prefit"
    return int(value)


def _optional_env(key: str) -> str | None:
    """Return a non-empty environment variable value."""
    value = os.getenv(key)
    if value is None or not value.strip():
        return None
    return value.strip()


def _validate_settings(settings: Settings) -> None:
    """Validate cross-section settings that can silently break workflows."""
    split_total = (
        settings.training.train_ratio
        + settings.training.validation_ratio
        + settings.training.test_ratio
    )
    if abs(split_total - 1.0) > 1e-9:
        raise ValueError("Training split ratios must sum to 1.0.")
    if settings.training.train_ratio <= 0 or settings.training.validation_ratio <= 0:
        raise ValueError("Training and validation ratios must be positive.")
    if settings.training.test_ratio <= 0:
        raise ValueError("Test ratio must be positive.")
    if settings.training.validation.method not in {"time_split", "walk_forward", "purged_cv"}:
        raise ValueError("Training validation method must be time_split, walk_forward, or purged_cv.")
    if settings.training.validation.n_splits <= 0:
        raise ValueError("Training validation n_splits must be positive.")
    if settings.training.validation.train_window_bars <= 0:
        raise ValueError("Training validation train_window_bars must be positive.")
    if settings.training.validation.validation_window_bars <= 0:
        raise ValueError("Training validation validation_window_bars must be positive.")
    if settings.training.validation.test_window_bars < 0:
        raise ValueError("Training validation test_window_bars must be non-negative.")
    if settings.training.validation.purge_size < 0:
        raise ValueError("Training validation purge_size must be non-negative.")
    if settings.training.validation.embargo_size < 0:
        raise ValueError("Training validation embargo_size must be non-negative.")
    if settings.training.calibration.method not in {"none", "sigmoid", "isotonic"}:
        raise ValueError("Training calibration method must be none, sigmoid, or isotonic.")
    calibration_cv = settings.training.calibration.cv
    if calibration_cv != "prefit" and int(calibration_cv) < 2:
        raise ValueError("Training calibration cv must be prefit or at least 2.")
    if settings.training.regime_specific.min_samples_per_regime <= 0:
        raise ValueError("Regime-specific min_samples_per_regime must be positive.")
    if (
        settings.training.regime_specific.min_validation_accuracy < 0
        or settings.training.regime_specific.min_validation_accuracy > 1
    ):
        raise ValueError("Regime-specific min_validation_accuracy must be between 0 and 1.")
    if settings.backtest.fee_rate < 0 or settings.backtest.slippage_rate < 0:
        raise ValueError("Backtest fee and slippage rates must be non-negative.")
    if settings.backtest.execution_cost is None:
        raise ValueError("Backtest execution_cost settings must be present.")
    if settings.backtest.execution_cost.model not in {
        "zero_slippage_baseline",
        "fixed",
        "dynamic",
        "high_slippage",
        "normal",
        "volatility_adjusted",
        "spread_aware",
        "stress",
    }:
        raise ValueError("Backtest execution cost model is not supported.")
    if (
        settings.backtest.execution_cost.fee_rate < 0
        or settings.backtest.execution_cost.base_slippage_rate < 0
        or settings.backtest.execution_cost.max_slippage_rate < 0
    ):
        raise ValueError("Backtest execution cost rates must be non-negative.")
    if settings.backtest.execution_cost.stress_multiplier < 0:
        raise ValueError("Backtest stress_multiplier must be non-negative.")
    if settings.backtest.execution_cost.atr_factor < 0:
        raise ValueError("Backtest atr_factor must be non-negative.")
    if settings.backtest.execution_cost.low_volume_threshold < 0:
        raise ValueError("Backtest low_volume_threshold must be non-negative.")
    if settings.backtest.execution_cost.low_volume_multiplier < 0:
        raise ValueError("Backtest low_volume_multiplier must be non-negative.")
    if settings.backtest.execution_cost.high_vol_multiplier < 0:
        raise ValueError("Backtest high_vol_multiplier must be non-negative.")
    if settings.backtest.execution_cost.extreme_vol_multiplier < 0:
        raise ValueError("Backtest extreme_vol_multiplier must be non-negative.")
    if settings.backtest.execution_cost.high_slippage_multiplier < 0:
        raise ValueError("Backtest high_slippage_multiplier must be non-negative.")
    if settings.backtest.max_holding_bars <= 0:
        raise ValueError("Backtest max_holding_bars must be positive.")
    if not (
        0
        <= settings.backtest.volatility_low_max
        < settings.backtest.volatility_normal_max
        < settings.backtest.volatility_high_max
    ):
        raise ValueError("Backtest volatility bucket thresholds must be increasing.")
    if settings.risk.account_balance < 0 or settings.risk.risk_per_trade_pct < 0:
        raise ValueError("Risk account balance and risk percent must be non-negative.")
    if settings.risk.max_risk_per_trade_pct < 0:
        raise ValueError("Risk max_risk_per_trade_pct must be non-negative.")
    if settings.risk.min_risk_reward < 0:
        raise ValueError("Risk min_risk_reward must be non-negative.")
    if not 0 <= settings.safety_filters.mean_reversion_danger_threshold <= 1:
        raise ValueError("Mean reversion danger threshold must be between 0 and 1.")
    if not 0 <= settings.safety_filters.breakout_fakeout_threshold <= 1:
        raise ValueError("Breakout fakeout threshold must be between 0 and 1.")
    adaptive = settings.adaptive_strategy
    if adaptive.base_threshold < 0 or adaptive.base_threshold > 1:
        raise ValueError("Adaptive strategy base_threshold must be between 0 and 1.")
    if adaptive.min_opinion_score < 0 or adaptive.min_opinion_score > 1:
        raise ValueError("Adaptive strategy min_opinion_score must be between 0 and 1.")
    if adaptive.conflict_margin < 0:
        raise ValueError("Adaptive strategy conflict_margin must be non-negative.")
    if adaptive.high_uncertainty_threshold < 0 or adaptive.high_uncertainty_threshold > 1:
        raise ValueError("Adaptive strategy high_uncertainty_threshold must be between 0 and 1.")
    if adaptive.memory_lookback_trades <= 0:
        raise ValueError("Adaptive strategy memory_lookback_trades must be positive.")
    if adaptive.memory_lookback_bars <= 0:
        raise ValueError("Adaptive strategy memory_lookback_bars must be positive.")
    if adaptive.memory_min_trades_required <= 0:
        raise ValueError("Adaptive strategy memory_min_trades_required must be positive.")
    if adaptive.memory_max_score_penalty < 0 or adaptive.memory_max_score_penalty > 1:
        raise ValueError("Adaptive strategy memory_max_score_penalty must be between 0 and 1.")
    if adaptive.memory_max_size_penalty < 0 or adaptive.memory_max_size_penalty > 1:
        raise ValueError("Adaptive strategy memory_max_size_penalty must be between 0 and 1.")
    validate_reasoning_brain_settings(settings.reasoning_brain)
    if settings.risk_guard.max_trades_per_day <= 0:
        raise ValueError("Risk guard max_trades_per_day must be positive.")
    if settings.risk_guard.max_consecutive_losses <= 0:
        raise ValueError("Risk guard max_consecutive_losses must be positive.")
    if settings.risk_guard.max_daily_drawdown_pct < 0:
        raise ValueError("Risk guard max_daily_drawdown_pct must be non-negative.")
    if settings.risk_guard.max_weekly_drawdown_pct < 0:
        raise ValueError("Risk guard max_weekly_drawdown_pct must be non-negative.")
    if settings.risk_guard.max_open_positions < 0:
        raise ValueError("Risk guard max_open_positions must be non-negative.")
    if settings.risk_guard.min_time_between_trades_minutes < 0:
        raise ValueError("Risk guard min_time_between_trades_minutes must be non-negative.")
    if settings.risk_guard.cooldown_minutes_after_block < 0:
        raise ValueError("Risk guard cooldown_minutes_after_block must be non-negative.")
    if settings.notification.min_confidence < 0 or settings.notification.min_confidence > 1:
        raise ValueError("Notification min_confidence must be between 0 and 1.")
    ensemble = settings.signal.strategy_ensemble
    if ensemble is None:
        raise ValueError("Signal strategy_ensemble settings must be present.")
    if ensemble.min_strategy_score < 0 or ensemble.min_strategy_score > 1:
        raise ValueError("Strategy ensemble min_strategy_score must be between 0 and 1.")
    if ensemble.conflict_margin < 0:
        raise ValueError("Strategy ensemble conflict_margin must be non-negative.")
    if (
        ensemble.low_regime_confidence_threshold < 0
        or ensemble.low_regime_confidence_threshold > 1
    ):
        raise ValueError("Strategy ensemble low_regime_confidence_threshold must be between 0 and 1.")
    multi_timeframe = settings.signal.multi_timeframe
    if multi_timeframe is None:
        raise ValueError("Signal multi_timeframe settings must be present.")
    if not multi_timeframe.primary_timeframe:
        raise ValueError("Signal multi_timeframe primary_timeframe must be non-empty.")
    if multi_timeframe.conflict_penalty < 0 or multi_timeframe.conflict_penalty > 1:
        raise ValueError("Signal multi_timeframe conflict_penalty must be between 0 and 1.")
    if settings.notification.min_risk_reward < 0:
        raise ValueError("Notification min_risk_reward must be non-negative.")
    if settings.notification.cooldown_seconds < 0:
        raise ValueError("Notification cooldown_seconds must be non-negative.")
    if settings.paper_trading.initial_balance < 0:
        raise ValueError("Paper trading initial_balance must be non-negative.")
