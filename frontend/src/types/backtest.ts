export type {
  BacktestReport,
  BacktestResponse,
  BacktestSegmentMetrics,
  Trade,
} from "./index";

export interface BacktestAnalyticsMetric {
  total_trades?: number;
  winrate?: number;
  net_profit?: number;
  gross_profit?: number;
  gross_loss?: number;
  profit_factor?: number | string | null;
  expectancy?: number;
  max_drawdown?: number;
  avg_r_multiple?: number;
  avg_holding_bars?: number;
  best_trade?: number | null;
  worst_trade?: number | null;
}

export interface BacktestAnalytics {
  generated_at?: string;
  overall?: BacktestAnalyticsMetric;
  grouped?: Record<string, Record<string, BacktestAnalyticsMetric>>;
  wait_reason_distribution?: Record<string, number>;
}
