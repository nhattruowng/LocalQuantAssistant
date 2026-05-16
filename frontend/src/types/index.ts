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
  explainability?: Explainability | null;
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
