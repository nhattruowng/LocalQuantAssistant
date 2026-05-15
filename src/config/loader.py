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
    CollectorSettings,
    DatabaseSettings,
    DataSettings,
    FeatureSettings,
    FeatureToggleSettings,
    LoggingSettings,
    MarketRegimeSettings,
    ModelSettings,
    RiskSettings,
    Settings,
    SignalSettings,
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

    database_path = os.getenv("LOCALQUANT_DB_PATH", database_config.get("path"))
    log_level = os.getenv("LOG_LEVEL", logging_config.get("level", "INFO"))
    resolved_database_path = _resolve_path(database_path or "data/localquant.db", base_dir)
    model_path = model_config.get("path")

    return Settings(
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
        ),
        signal=SignalSettings(
            min_confidence=float(signal_config.get("min_confidence", 0.55)),
            min_risk_reward=float(signal_config.get("min_risk_reward", 1.5)),
        ),
    )


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
