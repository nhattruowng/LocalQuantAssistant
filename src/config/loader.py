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
    BacktestSettings,
    CollectorSettings,
    DatabaseSettings,
    DataSettings,
    FeatureSettings,
    FeatureToggleSettings,
    LabelingSettings,
    LoggingSettings,
    MarketRegimeSettings,
    ModelSettings,
    NotificationSettings,
    PaperTradingSettings,
    RiskSettings,
    Settings,
    SignalSettings,
    TrainingSettings,
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
    model_config = raw_config.get("model", {})
    risk_config = raw_config.get("risk", {})
    signal_config = raw_config.get("signal", {})
    labeling_config = raw_config.get("labeling", {})
    training_config = raw_config.get("training", {})
    backtest_config = raw_config.get("backtest", {})
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
        ),
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
        ),
        signal=SignalSettings(
            min_confidence=float(signal_config.get("min_confidence", 0.55)),
            min_risk_reward=float(signal_config.get("min_risk_reward", 2.0)),
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
        ),
        backtest=BacktestSettings(
            fee_rate=float(backtest_config.get("fee_rate", 0.001)),
            slippage_rate=float(backtest_config.get("slippage_rate", 0.0005)),
            cooldown_bars_after_loss=int(
                backtest_config.get("cooldown_bars_after_loss", 3)
            ),
            max_holding_bars=int(backtest_config.get("max_holding_bars", 10)),
            output_dir=_resolve_path(backtest_config.get("output_dir", "data/backtest"), base_dir),
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
    """Parse the small nested mapping format used by the default config."""
    parsed: dict[str, Any] = {}
    current_section: str | None = None

    for raw_line in content.splitlines():
        line = raw_line.split("#", maxsplit=1)[0].rstrip()
        if not line:
            continue

        if not raw_line.startswith(" "):
            key = line.removesuffix(":")
            parsed[key] = {}
            current_section = key
            continue

        if current_section is None or ":" not in line:
            raise ValueError("Only simple nested YAML mappings are supported.")

        key, value = line.strip().split(":", maxsplit=1)
        section = parsed[current_section]
        if not isinstance(section, dict):
            raise ValueError("Invalid YAML section.")
        section[key] = _parse_scalar(value.strip())

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
    if settings.backtest.fee_rate < 0 or settings.backtest.slippage_rate < 0:
        raise ValueError("Backtest fee and slippage rates must be non-negative.")
    if settings.backtest.max_holding_bars <= 0:
        raise ValueError("Backtest max_holding_bars must be positive.")
    if settings.risk.account_balance < 0 or settings.risk.risk_per_trade_pct < 0:
        raise ValueError("Risk account balance and risk percent must be non-negative.")
    if settings.notification.min_confidence < 0 or settings.notification.min_confidence > 1:
        raise ValueError("Notification min_confidence must be between 0 and 1.")
    if settings.notification.min_risk_reward < 0:
        raise ValueError("Notification min_risk_reward must be non-negative.")
    if settings.notification.cooldown_seconds < 0:
        raise ValueError("Notification cooldown_seconds must be non-negative.")
    if settings.paper_trading.initial_balance < 0:
        raise ValueError("Paper trading initial_balance must be non-negative.")
