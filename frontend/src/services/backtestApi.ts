import {
  getLatestBacktest as getLatestBacktestRequest,
  runBacktest as runBacktestRequest,
} from "@/lib/api";
import type { BacktestReport, BacktestResponse, Trade } from "@/types";
import type { BacktestAnalytics, BacktestAnalyticsMetric } from "@/types/backtest";
import {
  asRecord,
  numberOrNull,
  stringArray,
  toApiResource,
  type ApiResource,
} from "@/services/apiState";

export { getLatestBacktest, runBacktest } from "@/lib/api";

export interface RunBacktestParams {
  symbol: string;
  timeframe: string;
  initial_balance: number;
  risk_percent: number;
}

export function normalizeBacktestAnalytics(payload: unknown): BacktestAnalytics | null {
  const record = asRecord(payload);
  if (!record) return null;
  const grouped = asRecord(record.grouped);
  return {
    generated_at: nullableString(record.generated_at) ?? undefined,
    overall: normalizeMetric(record.overall),
    grouped: grouped ? normalizeGroupedMetrics(grouped) : undefined,
    wait_reason_distribution: normalizeCountMap(record.wait_reason_distribution),
  };
}

export function normalizeBacktestReport(payload: unknown): BacktestReport | null {
  const record = asRecord(payload);
  if (!record) return null;
  return {
    ...(record as unknown as BacktestReport),
    symbol: String(record.symbol ?? ""),
    timeframe: String(record.timeframe ?? ""),
    total_trades: numberOrNull(record.total_trades) ?? 0,
    winrate: numberOrNull(record.winrate) ?? 0,
    net_profit: numberOrNull(record.net_profit) ?? 0,
    profit_factor: numberOrNull(record.profit_factor),
    max_drawdown: numberOrNull(record.max_drawdown) ?? 0,
    expectancy: numberOrNull(record.expectancy) ?? 0,
    trades: normalizeTrades(record.trades),
    wait_reason_distribution: normalizeCountMap(record.wait_reason_distribution),
    backtest_analytics: normalizeBacktestAnalytics(record.backtest_analytics) as Record<string, unknown> | null,
  };
}

export function normalizeBacktestResponse(payload: unknown): BacktestResponse | null {
  const record = asRecord(payload);
  if (!record) return null;
  const response: BacktestResponse = {};
  for (const [key, value] of Object.entries(record)) {
    if (key === "backtest_analytics") {
      response[key] = normalizeBacktestAnalytics(value) as Record<string, unknown> | null;
      continue;
    }
    if (key === "ablation_result") {
      response[key] = value as BacktestResponse["ablation_result"];
      continue;
    }
    const report = normalizeBacktestReport(value);
    response[key] = report ?? (value as BacktestResponse[string]);
  }
  return response;
}

export async function runBacktestResource(params: RunBacktestParams): Promise<ApiResource<BacktestResponse>> {
  return toApiResource(() => runBacktestRequest(params), (payload) => normalizeBacktestResponse(payload) ?? {});
}

export async function getLatestBacktestResource(
  symbol: string,
  timeframe: string,
): Promise<ApiResource<BacktestResponse | null>> {
  return toApiResource(() => getLatestBacktestRequest(symbol, timeframe), normalizeBacktestResponse);
}

function normalizeMetric(payload: unknown): BacktestAnalyticsMetric | undefined {
  const record = asRecord(payload);
  if (!record) return undefined;
  return {
    total_trades: numberOrNull(record.total_trades) ?? undefined,
    winrate: numberOrNull(record.winrate) ?? undefined,
    net_profit: numberOrNull(record.net_profit) ?? undefined,
    gross_profit: numberOrNull(record.gross_profit) ?? undefined,
    gross_loss: numberOrNull(record.gross_loss) ?? undefined,
    profit_factor: record.profit_factor === "Infinity" ? "Infinity" : numberOrNull(record.profit_factor),
    expectancy: numberOrNull(record.expectancy) ?? undefined,
    max_drawdown: numberOrNull(record.max_drawdown) ?? undefined,
    avg_r_multiple: numberOrNull(record.avg_r_multiple) ?? undefined,
    avg_holding_bars: numberOrNull(record.avg_holding_bars) ?? undefined,
    best_trade: numberOrNull(record.best_trade),
    worst_trade: numberOrNull(record.worst_trade),
  };
}

function normalizeGroupedMetrics(payload: Record<string, unknown>): Record<string, Record<string, BacktestAnalyticsMetric>> {
  const grouped: Record<string, Record<string, BacktestAnalyticsMetric>> = {};
  for (const [dimension, segments] of Object.entries(payload)) {
    const segmentRecord = asRecord(segments);
    if (!segmentRecord) continue;
    grouped[dimension] = {};
    for (const [segment, metric] of Object.entries(segmentRecord)) {
      grouped[dimension][segment] = normalizeMetric(metric) ?? {};
    }
  }
  return grouped;
}

function normalizeCountMap(payload: unknown): Record<string, number> {
  const record = asRecord(payload);
  if (!record) return {};
  return Object.fromEntries(
    Object.entries(record).map(([key, value]) => [key, numberOrNull(value) ?? 0]),
  );
}

function normalizeTrades(payload: unknown): Trade[] {
  if (!Array.isArray(payload)) return [];
  return payload.map((item) => {
    const record = asRecord(item) ?? {};
    return {
      ...(record as unknown as Trade),
      reasons: stringArray(record.reasons),
    } as Trade;
  });
}

function nullableString(value: unknown): string | null {
  if (value === null || value === undefined) return null;
  return String(value);
}
