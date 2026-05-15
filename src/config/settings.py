"""Typed application settings."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppSettings:
    """General application settings."""

    name: str
    environment: str


@dataclass(frozen=True)
class DatabaseSettings:
    """Database connection settings."""

    driver: str
    path: Path


@dataclass(frozen=True)
class LoggingSettings:
    """Logging settings."""

    level: str
    serialize: bool = False


@dataclass(frozen=True)
class DataSettings:
    """Market data validation settings."""

    min_bars: int


@dataclass(frozen=True)
class CollectorSettings:
    """Market data collector settings."""

    exchange: str
    symbols: tuple[str, ...]
    timeframes: tuple[str, ...]
    candles_limit: int
    retry_attempts: int
    retry_delay_seconds: float


@dataclass(frozen=True)
class FeatureSettings:
    """Feature engineering settings."""

    fast_ma_window: int
    slow_ma_window: int
    volatility_window: int
    breakout_lookback: int
    output_dir: Path
    drop_warmup_rows: bool


@dataclass(frozen=True)
class FeatureToggleSettings:
    """Feature group toggle settings."""

    price_action: bool
    trend: bool
    momentum: bool
    volatility: bool
    volume: bool


@dataclass(frozen=True)
class MarketRegimeSettings:
    """Market regime detection settings."""

    trend_strength_threshold: float
    high_volatility_threshold: float
    breakout_buffer_pct: float


@dataclass(frozen=True)
class ModelSettings:
    """Prediction model settings."""

    path: Path | None
    fallback_action_probability: float
    fallback_wait_probability: float
    fallback_opposite_probability: float


@dataclass(frozen=True)
class RiskSettings:
    """Risk calculation settings."""

    account_balance: float
    risk_per_trade_pct: float
    stop_loss_pct: float
    take_profit_pct: float


@dataclass(frozen=True)
class SignalSettings:
    """Signal decision settings."""

    min_confidence: float
    min_risk_reward: float


@dataclass(frozen=True)
class Settings:
    """Root application settings."""

    app: AppSettings
    database: DatabaseSettings
    logging: LoggingSettings
    data: DataSettings
    collector: CollectorSettings
    features: FeatureSettings
    feature_toggles: FeatureToggleSettings
    market_regime: MarketRegimeSettings
    model: ModelSettings
    risk: RiskSettings
    signal: SignalSettings
