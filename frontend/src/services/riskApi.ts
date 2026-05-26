import { getRiskStatus as getRiskStatusRequest } from "@/lib/api";
import type { RiskEvent, RiskStatus } from "@/types/risk";
import {
  asRecord,
  boolOrDefault,
  numberOrNull,
  stringArray,
  toApiResource,
  type ApiResource,
} from "@/services/apiState";

export { getRiskStatus } from "@/lib/api";

export function normalizeRiskStatus(payload: unknown): RiskStatus {
  const record = asRecord(payload) ?? {};
  return {
    enabled: boolOrDefault(record.enabled, false),
    state: String(record.state ?? "UNKNOWN"),
    reasons: stringArray(record.reasons),
    daily_trade_count: numberOrNull(record.daily_trade_count) ?? 0,
    trades_today: numberOrNull(record.trades_today) ?? undefined,
    open_positions: numberOrNull(record.open_positions) ?? 0,
    consecutive_losses: numberOrNull(record.consecutive_losses) ?? 0,
    max_consecutive_losses: numberOrNull(record.max_consecutive_losses) ?? undefined,
    daily_drawdown_pct: numberOrNull(record.daily_drawdown_pct) ?? 0,
    weekly_drawdown_pct: numberOrNull(record.weekly_drawdown_pct) ?? 0,
    current_exposure: numberOrNull(record.current_exposure),
    last_blocked_at: nullableString(record.last_blocked_at),
    events: normalizeRiskEvents(record.events),
  };
}

export async function getRiskStatusResource(
  symbol: string,
  timeframe: string,
): Promise<ApiResource<RiskStatus>> {
  return toApiResource(() => getRiskStatusRequest(symbol, timeframe), normalizeRiskStatus);
}

function normalizeRiskEvents(payload: unknown): RiskEvent[] {
  if (!Array.isArray(payload)) return [];
  return payload.map((item) => {
    const record = asRecord(item) ?? {};
    return {
      timestamp: nullableString(record.timestamp) ?? undefined,
      event_type: nullableString(record.event_type) ?? undefined,
      state: nullableString(record.state) ?? undefined,
      severity: nullableString(record.severity) ?? undefined,
      message: nullableString(record.message) ?? undefined,
      reason: nullableString(record.reason) ?? undefined,
      affected_symbol: nullableString(record.affected_symbol) ?? undefined,
      symbol: nullableString(record.symbol) ?? undefined,
      timeframe: nullableString(record.timeframe) ?? undefined,
      action_taken: nullableString(record.action_taken) ?? undefined,
    };
  });
}

function nullableString(value: unknown): string | null {
  if (value === null || value === undefined) return null;
  return String(value);
}
