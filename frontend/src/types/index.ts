export type SignalType = "BUY" | "SELL" | "WAIT";

export type StrategyType =
  | "TREND_FOLLOWING"
  | "BREAKOUT_CONFIRMATION"
  | "MEAN_REVERSION"
  | "NONE"
  | string;

export interface Candle {
  symbol: string;
  timeframe: string;
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  ema_20?: number;
  ema_50?: number;
  ema_200?: number;
  rsi_14?: number;
  market_regime?: string;
}

export interface ExplainabilityFactor {
  feature: string;
  impact: number;
}

export interface Explainability {
  method: string;
  top_positive_factors: ExplainabilityFactor[];
  top_negative_factors: ExplainabilityFactor[];
  top_factors?: ExplainabilityFactor[];
  summary: string;
}

export interface StructuredExplanation {
  final_decision: SignalType;
  summary: string;
  regime: {
    primary?: string;
    confidence?: number;
    regime_scores?: Record<string, number>;
    uncertainty_score?: number;
    transition_warning?: boolean;
    volatility_level?: string;
    transition_warnings?: Array<Record<string, unknown>>;
    higher_timeframes?: Array<Record<string, unknown>>;
  };
  strategy: {
    selected?: StrategyType;
    selected_score?: number | null;
    selected_opinion?: Record<string, unknown> | null;
    strategy_opinions?: Array<Record<string, unknown>>;
    passed_conditions?: string[];
    failed_conditions?: string[];
    rejected_strategies?: Array<Record<string, unknown>>;
  };
  risk: {
    risk_reward?: number | null;
    position_size?: number | null;
    risk_notes?: string[];
  };
  model: {
    probability_source?: string;
    buy_probability?: number;
    sell_probability?: number;
    wait_probability?: number;
    raw_probabilities?: Partial<Record<SignalType, number>> | null;
    calibrated_probabilities?: Partial<Record<SignalType, number>> | null;
  };
  multi_timeframe: {
    enabled?: boolean;
    primary_timeframe?: string;
    confirmation_timeframes?: string[];
    missing_timeframes?: string[];
    confirmations?: Array<{
      timeframe?: string;
      regime?: string;
      confidence?: number;
      aligned?: boolean;
      conflict?: boolean;
      volume_ratio?: number;
      atr_percent?: number;
      breakout_confirmed?: boolean;
    }>;
    conflict?: boolean;
    aligned_timeframes?: string[];
    confidence_multiplier?: number;
    blocked?: boolean;
    reasons?: string[];
  };
  final_decision_summary: string;
}

export interface TradeSetup {
  symbol: string;
  timeframe: string;
  timestamp?: string;
  market_regime?: string;
  signal: SignalType;
  strategy?: StrategyType;
  confidence: number;
  entry: number | null;
  stop_loss: number | null;
  take_profit_1: number | null;
  take_profit_2: number | null;
  risk_reward: number | null;
  position_size: number | null;
  reasons: string[];
  risk_notes: string[];
  probabilities?: Partial<Record<SignalType, number>>;
  raw_probabilities?: Partial<Record<SignalType, number>> | null;
  calibrated_probabilities?: Partial<Record<SignalType, number>> | null;
  probability_source?: "raw" | "calibrated" | string;
  model_scope_used?: "global" | "regime_specific" | string | null;
  model_version?: string | null;
  fallback_reason?: string | null;
  explainability?: Explainability | null;
  explanation_v2?: StructuredExplanation | null;
}

export interface Trade {
  symbol: string;
  timeframe: string;
  direction: SignalType;
  strategy: StrategyType;
  opened_at: string;
  closed_at: string;
  entry: number;
  exit_price: number;
  pnl: number;
  result: string;
  confidence: number;
  risk_reward?: number;
}

export interface PaperTrade {
  id?: number;
  symbol: string;
  timeframe: string;
  direction: SignalType;
  status?: string;
  entry: number;
  stop_loss?: number;
  take_profit_1?: number;
  take_profit_2?: number;
  position_size?: number;
  opened_at?: string;
  closed_at?: string;
  pnl?: number;
}

export interface BacktestReport {
  symbol: string;
  timeframe: string;
  mode?: string;
  total_trades: number;
  winrate: number;
  gross_profit?: number;
  gross_loss?: number;
  net_profit: number;
  profit_factor: number | null;
  max_drawdown: number;
  average_win?: number;
  average_loss?: number;
  expectancy: number;
  average_risk_reward?: number;
  trades?: Trade[];
}

export interface BacktestResponse {
  rule_only?: BacktestReport;
  ml_enhanced?: BacktestReport;
  [mode: string]: BacktestReport | undefined;
}

export interface ModelInfo {
  model_type?: string;
  trained_at?: string;
  feature_columns?: string[];
  metrics?: Record<string, unknown>;
  metadata_path?: string;
  model_path?: string;
  model_id?: string;
  model_version?: string;
  model_scope?: string;
  status?: string;
  calibration_enabled?: boolean;
  calibration_method?: string;
  brier_score_before?: number | null;
  brier_score_after?: number | null;
  log_loss_before?: number | null;
  log_loss_after?: number | null;
}

export interface ModelCalibration {
  symbol?: string;
  timeframe?: string;
  trained_at?: string;
  calibration_enabled?: boolean;
  calibration_method?: string;
  brier_score_before?: number | null;
  brier_score_after?: number | null;
  log_loss_before?: number | null;
  log_loss_after?: number | null;
  expected_calibration_error_before?: number | null;
  expected_calibration_error_after?: number | null;
  per_class_brier_score_before?: Record<string, number> | null;
  per_class_brier_score_after?: Record<string, number> | null;
  reliability_curve_before?: Record<string, unknown[]> | null;
  reliability_curve_after?: Record<string, unknown[]> | null;
  probability_histogram_before?: Record<string, unknown[]> | null;
  probability_histogram_after?: Record<string, unknown[]> | null;
  report?: Record<string, unknown>;
}

export interface RiskStatus {
  enabled: boolean;
  state: "ACTIVE" | "WARNING" | "BLOCKED" | "COOLDOWN" | string;
  reasons: string[];
  daily_trade_count: number;
  open_positions: number;
  consecutive_losses: number;
  daily_drawdown_pct: number;
  weekly_drawdown_pct: number;
  last_blocked_at?: string | null;
  events?: Array<{
    timestamp: string;
    state: string;
    reason: string;
    symbol: string;
    timeframe: string;
  }>;
}

export interface SignalHistory {
  symbol: string;
  timeframe: string;
  signal: SignalType;
  strategy?: string;
  confidence?: number;
  market_regime?: string;
  recorded_at?: string;
}

export interface ApiError {
  error?: {
    code: string;
    message: string;
  };
}
