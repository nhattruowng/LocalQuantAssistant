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
    adaptive_strategy_enabled: bool = False


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
    dynamic_sizing_enabled: bool = True
    max_risk_per_trade_pct: float = 1.0
    min_risk_reward: float = 2.0


@dataclass(frozen=True)
class SafetyFilterSettings:
    """Safety filters for fragile setup types."""

    mean_reversion_danger_enabled: bool = True
    breakout_fakeout_defense_enabled: bool = True
    extreme_volatility_block: bool = True
    higher_timeframe_conflict_block: bool = True
    mean_reversion_danger_threshold: float = 0.70
    breakout_fakeout_threshold: float = 0.55


@dataclass(frozen=True)
class RiskGuardSettings:
    """Risk guard and circuit breaker settings."""

    enabled: bool = False
    max_trades_per_day: int = 5
    max_consecutive_losses: int = 3
    max_daily_drawdown_pct: float = 0.05
    max_weekly_drawdown_pct: float = 0.10
    max_open_positions: int = 1
    min_time_between_trades_minutes: int = 30
    cooldown_minutes_after_block: int = 60
    require_calibrated_model: bool = False
    block_low_regime_confidence: bool = False


@dataclass(frozen=True)
class StrategyEnsembleSettings:
    """Strategy ensemble decision settings."""

    enabled: bool = False
    min_strategy_score: float = 0.55
    conflict_margin: float = 0.10
    low_regime_confidence_threshold: float = 0.55


@dataclass(frozen=True)
class MultiTimeframeSettings:
    """Higher timeframe confirmation settings for signal generation."""

    enabled: bool = False
    primary_timeframe: str = "15m"
    confirmation_timeframes: tuple[str, ...] = ("1h", "4h")
    conflict_penalty: float = 0.35
    require_higher_tf_alignment: bool = False


@dataclass(frozen=True)
class AdaptiveStrategySettings:
    """Adaptive decision settings for strategy opinion ensemble."""

    enabled: bool = False
    base_threshold: float = 0.65
    min_opinion_score: float = 0.55
    conflict_margin: float = 0.12
    high_uncertainty_threshold: float = 0.45
    require_calibrated_probability: bool = False
    allow_grade_c_signal: bool = False
    memory_lookback_trades: int = 30
    memory_lookback_bars: int = 200
    memory_min_trades_required: int = 10
    memory_max_score_penalty: float = 0.20
    memory_max_size_penalty: float = 0.50
    memory_block_after_consecutive_losses: bool = True


@dataclass(frozen=True)
class SignalSettings:
    """Signal decision settings."""

    min_confidence: float
    min_risk_reward: float
    use_calibrated_probability: bool = True
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
    strategy_ensemble: StrategyEnsembleSettings | None = None
    multi_timeframe: MultiTimeframeSettings | None = None


@dataclass(frozen=True)
class LabelingSettings:
    """TP/SL first-touch labeling settings."""

    lookahead_bars: int
    stop_loss_atr_multiplier: float
    take_profit_atr_multiplier: float


@dataclass(frozen=True)
class TrainingValidationSettings:
    """Time-series validation settings."""

    method: str = "time_split"
    n_splits: int = 5
    train_window_bars: int = 500
    validation_window_bars: int = 100
    expanding_window: bool = True
    embargo_size: int = 0


@dataclass(frozen=True)
class TrainingCalibrationSettings:
    """Probability calibration settings for trained classifiers."""

    enabled: bool = False
    method: str = "sigmoid"
    cv: str | int = "prefit"


@dataclass(frozen=True)
class RegimeSpecificTrainingSettings:
    """Settings for optional regime-specific model training."""

    enabled: bool = False
    min_samples_per_regime: int = 200
    allowed_regimes: tuple[str, ...] = ()
    min_validation_accuracy: float = 0.0


@dataclass(frozen=True)
class ModelRegistrySettings:
    """Settings for model registry lifecycle behavior."""

    auto_promote_champion: bool = True


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
    validation: TrainingValidationSettings
    calibration: TrainingCalibrationSettings
    regime_specific: RegimeSpecificTrainingSettings
    registry: ModelRegistrySettings


@dataclass(frozen=True)
class ExecutionCostSettings:
    """Execution cost model settings for backtests."""

    model: str = "fixed"
    fee_rate: float = 0.001
    base_slippage_rate: float = 0.0005
    stress_multiplier: float = 3.0
    max_slippage_rate: float = 0.01
    volatility_multiplier: float = 10.0
    estimated_spread_rate: float = 0.0005


@dataclass(frozen=True)
class BacktestSettings:
    """Backtesting execution and cost settings."""

    fee_rate: float
    slippage_rate: float
    cooldown_bars_after_loss: int
    max_holding_bars: int
    output_dir: Path
    volatility_low_max: float = 0.01
    volatility_normal_max: float = 0.025
    volatility_high_max: float = 0.05
    execution_cost: ExecutionCostSettings | None = None


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
    adaptive_strategy: AdaptiveStrategySettings
    model: ModelSettings
    risk: RiskSettings
    safety_filters: SafetyFilterSettings
    risk_guard: RiskGuardSettings
    signal: SignalSettings
    labeling: LabelingSettings
    training: TrainingSettings
    backtest: BacktestSettings
    notification: NotificationSettings
    paper_trading: PaperTradingSettings
