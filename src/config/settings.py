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
    sideway_trend_threshold: float
    sideway_bollinger_width_threshold: float
    sideway_atr_percent_threshold: float
    breakout_window: int
    breakout_volume_ratio_threshold: float
    breakout_atr_percent_threshold: float
    high_volatility_percentile: float
    low_volatility_percentile: float
    volatility_percentile_window: int


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
    stop_loss_atr_multiplier: float = 1.5
    take_profit_1_atr_multiplier: float = 2.0
    take_profit_2_atr_multiplier: float = 3.0


@dataclass(frozen=True)
class SignalSettings:
    """Signal decision settings."""

    min_confidence: float
    min_risk_reward: float
    trend_probability_threshold: float = 0.65
    breakout_probability_threshold: float = 0.65
    mean_reversion_probability_threshold: float = 0.60
    ema_near_pct: float = 0.01
    breakout_volume_ratio_threshold: float = 1.2
    support_resistance_near_pct: float = 0.01
    trend_buy_rsi_min: float = 40.0
    trend_buy_rsi_max: float = 70.0
    trend_sell_rsi_min: float = 30.0
    trend_sell_rsi_max: float = 60.0
    mean_reversion_buy_rsi_max: float = 35.0
    mean_reversion_sell_rsi_min: float = 65.0
    model_score_weight: float = 0.40
    trend_score_weight: float = 0.25
    indicator_score_weight: float = 0.20
    volume_score_weight: float = 0.10
    risk_reward_score_weight: float = 0.05


@dataclass(frozen=True)
class LabelingSettings:
    """TP/SL first-touch labeling settings."""

    lookahead_bars: int
    stop_loss_atr_multiplier: float
    take_profit_atr_multiplier: float


@dataclass(frozen=True)
class TrainingSettings:
    """Model training settings."""

    train_ratio: float
    validation_ratio: float
    test_ratio: float
    random_state: int
    n_estimators: int
    max_depth: int | None
    model_dir: Path


@dataclass(frozen=True)
class BacktestSettings:
    """Backtesting execution and cost settings."""

    fee_rate: float
    slippage_rate: float
    cooldown_bars_after_loss: int
    max_holding_bars: int
    output_dir: Path


@dataclass(frozen=True)
class NotificationSettings:
    """Notification delivery settings."""

    enabled: bool
    telegram_bot_token: str | None
    telegram_chat_id: str | None
    min_confidence: float
    min_risk_reward: float
    cooldown_seconds: int
    request_timeout_seconds: float


@dataclass(frozen=True)
class PaperTradingSettings:
    """Paper trading simulation settings."""

    enabled: bool
    initial_balance: float


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
    labeling: LabelingSettings
    training: TrainingSettings
    backtest: BacktestSettings
    notification: NotificationSettings
    paper_trading: PaperTradingSettings
