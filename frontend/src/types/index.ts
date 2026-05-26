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
    adaptive_threshold?: number | null;
    conflict_result?: Record<string, unknown> | null;
    setup_quality?: string | null;
    decision_warnings?: string[];
    why_wait?: string | null;
    passed_conditions?: string[];
    failed_conditions?: string[];
    rejected_strategies?: Array<Record<string, unknown>>;
    setup_type?: string | null;
    confluence_score?: number | null;
    evidence_for?: Array<Record<string, unknown>>;
    evidence_against?: Array<Record<string, unknown>>;
    conflict_level?: string | null;
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
  setup_type?: string | null;
  confluence_score?: number | null;
  conflict_level?: string | null;
  conflict_details?: Record<string, unknown> | null;
  confidence: number;
  entry: number | null;
  stop_loss: number | null;
  take_profit_1: number | null;
  take_profit_2: number | null;
  risk_reward: number | null;
  position_size: number | null;
  position_size_multiplier?: number | null;
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
  wait_reason?: string | null;
  size_multiplier?: number | null;
  strategy_diagnostics?: Record<string, unknown> | null;
  reasoning_decision?: ReasoningDecisionPayload | null;
}

export interface DecisionStepPayload {
  step_name?: string;
  input_score?: number | null;
  output_score?: number | null;
  delta?: number | null;
  passed?: boolean;
  details?: Record<string, unknown>;
  warnings?: string[];
  timestamp?: string;
}

export interface DecisionTracePayload {
  trace_id?: string;
  symbol?: string;
  timeframe?: string;
  model_version?: string | null;
  config_hash?: string | null;
  steps?: DecisionStepPayload[];
  final_signal?: string | null;
  final_confidence?: number | null;
  wait_reason?: string | null;
  created_at?: string;
  warnings?: string[];
}

export interface ReasoningEvidencePayload {
  name?: string;
  source?: string;
  direction?: string;
  score?: number | null;
  confidence?: number | null;
  weight?: number | null;
  evidence_type?: string;
  reason?: string;
  impact_on_score?: number | null;
  is_critical?: boolean;
}

export interface ReasoningDecisionPayload {
  final_signal?: string | null;
  setup_type?: string | null;
  confluence_score?: number | null;
  confidence?: number | null;
  adaptive_threshold?: number | null;
  position_size_multiplier?: number | null;
  evidence_for?: ReasoningEvidencePayload[] | null;
  evidence_against?: ReasoningEvidencePayload[] | null;
  warnings?: string[];
  wait_reason?: string | null;
  conflict_level?: string | null;
  conflict_details?: Record<string, unknown> | null;
  risk_notes?: string[];
  decision_trace?: DecisionTracePayload | Record<string, unknown> | null;
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
  market_regime?: string;
  setup_type?: string;
  setup_grade?: string;
  wait_reason?: string;
  safety_filter?: string;
  model_scope?: string;
  probability_source?: string;
  conflict_level?: string;
  confluence_score?: number;
  confluence_bucket?: string;
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

export interface BacktestSegmentMetrics {
  total_trades: number;
  winrate: number;
  gross_profit: number;
  gross_loss: number;
  net_profit: number;
  profit_factor: number;
  max_drawdown: number;
  expectancy: number;
  avg_holding_bars?: number;
  avg_confidence?: number;
  best_trade?: number;
  worst_trade?: number;
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
  avg_r_multiple?: number | null;
  best_trade?: number | null;
  worst_trade?: number | null;
  average_risk_reward?: number;
  trades?: Trade[];
  grouped?: Record<string, Record<string, BacktestSegmentMetrics>>;
  wait_reason_distribution?: Record<string, number>;
  backtest_analytics?: Record<string, unknown> | null;
  ablation_result?: Record<string, unknown> | Array<Record<string, unknown>> | null;
  scenarios?: Array<Record<string, unknown>>;
  json_path?: string;
  csv_path?: string;
  html_path?: string;
}

export interface BacktestResponse {
  rule_only?: BacktestReport;
  ml_enhanced?: BacktestReport;
  backtest_analytics?: Record<string, unknown> | null;
  ablation_result?: Record<string, unknown> | Array<Record<string, unknown>> | null;
  [mode: string]: BacktestReport | Record<string, unknown> | Array<Record<string, unknown>> | null | undefined;
}

export interface ModelInfo {
  model_type?: string;
  trained_at?: string;
  symbol?: string;
  timeframe?: string;
  feature_columns?: string[];
  metrics?: Record<string, unknown>;
  metadata_path?: string;
  model_path?: string;
  model_id?: string;
  model_version?: string;
  model_scope?: string;
  validation_method?: string;
  status?: string;
  calibration_enabled?: boolean;
  calibration_method?: string;
  probability_source?: string;
  brier_score_before?: number | null;
  brier_score_after?: number | null;
  log_loss_before?: number | null;
  log_loss_after?: number | null;
  drift_report?: DriftReportPayload | null;
}

export interface ModelCalibration {
  symbol?: string;
  timeframe?: string;
  trained_at?: string;
  calibration_enabled?: boolean;
  calibration_method?: string;
  raw_probability?: number | null;
  calibrated_probability?: number | null;
  raw_probabilities?: Partial<Record<SignalType, number>> | null;
  calibrated_probabilities?: Partial<Record<SignalType, number>> | null;
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

export interface DriftReportPayload {
  drift_level?: "NONE" | "LOW" | "MEDIUM" | "HIGH" | string;
  drift_score?: number | null;
  drifted?: boolean;
  drifted_features?: Array<Record<string, unknown>>;
  feature_metrics?: Array<Record<string, unknown>>;
  prediction_shift?: Record<string, unknown>;
  prediction_distribution_shift?: Record<string, unknown>;
  calibration_shift?: Record<string, unknown>;
  calibration_drift?: Record<string, unknown>;
  regime_shift?: Record<string, unknown>;
  regime_drift?: Record<string, unknown>;
  recommended_action?: "CONTINUE" | "WARN" | "RETRAIN_CANDIDATE" | "DISABLE_MODEL" | string;
  metadata?: Record<string, unknown>;
}

export interface ModelDriftResponse {
  symbol?: string;
  timeframe?: string;
  model_id?: string;
  model_version?: string;
  report?: DriftReportPayload;
}

export interface RiskStatus {
  enabled: boolean;
  state: "ACTIVE" | "WARNING" | "BLOCKED" | "COOLDOWN" | string;
  reasons: string[];
  daily_trade_count: number;
  trades_today?: number;
  open_positions: number;
  consecutive_losses: number;
  max_consecutive_losses?: number;
  daily_drawdown_pct: number;
  weekly_drawdown_pct: number;
  current_exposure?: number | null;
  last_blocked_at?: string | null;
  events?: Array<{
    timestamp: string;
    event_type?: string;
    state: string;
    severity?: string;
    message?: string;
    reason: string;
    affected_symbol?: string;
    symbol: string;
    timeframe: string;
    action_taken?: string;
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

export type { BacktestAnalytics } from "./backtest";
export type { DriftReport } from "./model";
export type { MarketPreset } from "./reasoning";
