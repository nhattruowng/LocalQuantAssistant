export interface RiskEvent {
  timestamp?: string;
  event_type?: string;
  state?: string;
  severity?: string;
  message?: string;
  reason?: string;
  affected_symbol?: string;
  symbol?: string;
  timeframe?: string;
  action_taken?: string;
}

export interface RiskStatus {
  enabled?: boolean;
  state?: "ACTIVE" | "WARNING" | "BLOCKED" | "COOLDOWN" | "UNKNOWN" | string;
  reasons?: string[];
  daily_trade_count?: number;
  trades_today?: number;
  open_positions?: number;
  consecutive_losses?: number;
  max_consecutive_losses?: number;
  daily_drawdown_pct?: number;
  weekly_drawdown_pct?: number;
  current_exposure?: number | null;
  last_blocked_at?: string | null;
  events?: RiskEvent[];
}
