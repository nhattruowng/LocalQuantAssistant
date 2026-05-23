import { useMemo } from "react";
import { AlertTriangle, RefreshCw, ShieldAlert } from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { DrawdownCurveChart, EquityCurveChart, MonthlyReturnsChart } from "@/components/charts/BacktestCharts";
import { MetricCard } from "@/components/cards/MetricCard";
import { Button } from "@/components/forms/Button";
import { PageHeader } from "@/components/layout/PageHeader";
import { DataTable } from "@/components/tables/DataTable";
import { useLatestBacktestQuery, useRiskStatusQuery } from "@/hooks/useApiQueries";
import { useSessionStore } from "@/hooks/useSessionStore";
import { formatNumber, formatPercent, shortDate } from "@/lib/utils";
import type { BacktestReport, RiskStatus, Trade } from "@/types";

type RiskEventRow = {
  timestamp: string;
  event_type: string;
  severity: string;
  message: string;
  affected_symbol: string;
  action_taken: string;
};

type SliceRow = {
  label: string;
  trade_count: number;
  net_pnl: number;
  winrate: number;
};

type StreakRow = {
  type: "WIN" | "LOSS" | "BREAKEVEN";
  length: number;
  net_pnl: number;
  start: string;
  end: string;
};

type ConfidencePoint = {
  confidence: number;
  pnl: number;
  outcome: string;
};

function toNumber(value: unknown): number {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return 0;
}

function normalizeConfidence(value: unknown) {
  const numeric = toNumber(value);
  if (!Number.isFinite(numeric)) return 0;
  return numeric > 1 ? numeric / 100 : numeric;
}

function pickBacktestReport(source?: BacktestReport | null) {
  return source ?? null;
}

function getTrades(report?: BacktestReport | null): Trade[] {
  return Array.isArray(report?.trades) ? report!.trades! : [];
}

function aggregateTrades(trades: Trade[], selector: (trade: Trade) => string): SliceRow[] {
  const buckets = new Map<string, Trade[]>();
  for (const trade of trades) {
    const label = selector(trade) || "UNKNOWN";
    const bucket = buckets.get(label) ?? [];
    bucket.push(trade);
    buckets.set(label, bucket);
  }

  return Array.from(buckets.entries())
    .map(([label, bucket]) => {
      const tradeCount = bucket.length;
      const wins = bucket.filter((trade) => toNumber(trade.pnl) > 0).length;
      const netPnl = bucket.reduce((sum, trade) => sum + toNumber(trade.pnl), 0);
      return {
        label,
        trade_count: tradeCount,
        net_pnl: netPnl,
        winrate: tradeCount ? wins / tradeCount : 0,
      };
    })
    .sort((left, right) => right.net_pnl - left.net_pnl);
}

function confidencePoints(trades: Trade[]): ConfidencePoint[] {
  return trades
    .map((trade) => {
      const confidence = normalizeConfidence(trade.confidence);
      const pnl = toNumber(trade.pnl);
      return {
        confidence,
        pnl,
        outcome: pnl > 0 ? "WIN" : pnl < 0 ? "LOSS" : "BREAKEVEN",
      };
    })
    .filter((point) => Number.isFinite(point.confidence));
}

function computeStreaks(trades: Trade[]): StreakRow[] {
  const rows: StreakRow[] = [];
  let currentType: StreakRow["type"] | null = null;
  let length = 0;
  let netPnl = 0;
  let start = "";
  let end = "";

  const flush = () => {
    if (!currentType || !length) return;
    rows.push({
      type: currentType,
      length,
      net_pnl: netPnl,
      start,
      end,
    });
  };

  for (const trade of trades) {
    const pnl = toNumber(trade.pnl);
    const nextType: StreakRow["type"] = pnl > 0 ? "WIN" : pnl < 0 ? "LOSS" : "BREAKEVEN";
    const timestamp = trade.closed_at || trade.opened_at || "";

    if (nextType !== currentType) {
      flush();
      currentType = nextType;
      length = 1;
      netPnl = pnl;
      start = timestamp;
      end = timestamp;
      continue;
    }

    length += 1;
    netPnl += pnl;
    end = timestamp;
  }

  flush();
  return rows;
}

function normalizeRiskEvents(status?: RiskStatus | null): RiskEventRow[] {
  const events = status?.events ?? [];
  return events
    .map((event) => {
      const severity = (event.severity ?? inferSeverity(event.state)).toUpperCase();
      return {
        timestamp: event.timestamp || "-",
        event_type: event.event_type ?? event.state ?? "EVENT",
        severity,
        message: event.message ?? event.reason ?? "-",
        affected_symbol: event.affected_symbol ?? event.symbol ?? "-",
        action_taken: event.action_taken ?? inferAction(event.state),
      };
    })
    .sort((left, right) => right.timestamp.localeCompare(left.timestamp));
}

function inferSeverity(state?: string | null) {
  const normalized = String(state ?? "").toUpperCase();
  if (normalized.includes("BLOCK")) return "HIGH";
  if (normalized.includes("COOLDOWN")) return "MEDIUM";
  if (normalized.includes("WARN")) return "MEDIUM";
  return "LOW";
}

function inferAction(state?: string | null) {
  const normalized = String(state ?? "").toUpperCase();
  if (normalized.includes("BLOCK")) return "Blocked new entries";
  if (normalized.includes("COOLDOWN")) return "Cooldown enforced";
  if (normalized.includes("WARN")) return "Warned trader";
  return "Continue";
}

function PnLBarChart({
  title,
  rows,
  emptyText,
}: {
  title: string;
  rows: SliceRow[];
  emptyText: string;
}) {
  return (
    <section className="rounded-lg border border-border bg-white p-4">
      <h3 className="text-sm font-semibold text-foreground">{title}</h3>
      {rows.length ? (
        <div className="mt-4 h-72">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={rows}>
              <CartesianGrid stroke="#e5e7eb" vertical={false} />
              <XAxis dataKey="label" tick={{ fontSize: 12 }} interval={0} />
              <YAxis tickFormatter={(value) => formatNumber(Number(value), 0)} />
              <Tooltip
                formatter={(value, name) => {
                  if (name === "net_pnl") return [formatNumber(Number(value), 2), "Net PnL"];
                  if (name === "winrate") return [formatPercent(Number(value)), "Winrate"];
                  if (name === "trade_count") return [formatNumber(Number(value), 0), "Trades"];
                  return [String(value), String(name)];
                }}
              />
              <Bar dataKey="net_pnl" fill="#2563eb" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <p className="mt-3 text-sm text-muted-foreground">{emptyText}</p>
      )}
    </section>
  );
}

function ConfidenceScatterChart({ trades }: { trades: Trade[] }) {
  const points = confidencePoints(trades);
  return (
    <section className="rounded-lg border border-border bg-white p-4">
      <h3 className="text-sm font-semibold text-foreground">Confidence vs Actual Result</h3>
      {points.length ? (
        <div className="mt-4 h-72">
          <ResponsiveContainer width="100%" height="100%">
            <ScatterChart margin={{ top: 8, right: 8, left: 8, bottom: 8 }}>
              <CartesianGrid stroke="#e5e7eb" />
              <XAxis
                type="number"
                dataKey="confidence"
                domain={[0, 1]}
                tickFormatter={(value) => `${Math.round(Number(value) * 100)}%`}
              />
              <YAxis type="number" dataKey="pnl" tickFormatter={(value) => formatNumber(Number(value), 0)} />
              <Tooltip
                cursor={{ strokeDasharray: "3 3" }}
                formatter={(value, name) => {
                  if (name === "confidence") return [`${Math.round(Number(value) * 100)}%`, "Confidence"];
                  if (name === "pnl") return [formatNumber(Number(value), 2), "PnL"];
                  return [String(value), String(name)];
                }}
              />
              <Scatter data={points}>
                {points.map((point, index) => (
                  <Cell key={`${point.outcome}-${index}`} fill={point.pnl >= 0 ? "#0f766e" : "#dc2626"} />
                ))}
              </Scatter>
            </ScatterChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <p className="mt-3 text-sm text-muted-foreground">No confidence data available.</p>
      )}
    </section>
  );
}

export function RiskPage() {
  const risk = useRiskStatusQuery();
  const latestBacktestQuery = useLatestBacktestQuery();
  const sessionBacktest = useSessionStore((state) => state.latestBacktest);

  const backtestResponse = latestBacktestQuery.data ?? sessionBacktest;
  const latestReport = useMemo(() => {
    const enhanced = pickBacktestReport(backtestResponse?.ml_enhanced ?? null);
    if (enhanced) return enhanced;
    return pickBacktestReport(backtestResponse?.rule_only ?? null);
  }, [backtestResponse]);
  const trades = getTrades(latestReport);
  const riskEvents = normalizeRiskEvents(risk.data);
  const regimeRows = aggregateTrades(trades, (trade) => trade.market_regime ?? "UNKNOWN");
  const strategyRows = aggregateTrades(trades, (trade) => trade.strategy ?? "UNKNOWN");
  const setupTypeRows = aggregateTrades(trades, (trade) => trade.setup_type ?? "UNKNOWN");
  const streaks = computeStreaks(trades);
  const maxWinningStreak = streaks.filter((row) => row.type === "WIN").reduce((max, row) => Math.max(max, row.length), 0);
  const maxLosingStreak = streaks.filter((row) => row.type === "LOSS").reduce((max, row) => Math.max(max, row.length), 0);
  const currentStreak = streaks.at(-1) ?? null;
  const riskState = risk.data?.state ?? "-";
  const isBlocked = riskState === "BLOCKED" || riskState === "COOLDOWN";
  const reason = risk.data?.reasons?.[0] ?? "Risk guard is active.";
  const currentExposure = risk.data?.current_exposure ?? null;
  const tradesToday = risk.data?.trades_today ?? risk.data?.daily_trade_count ?? 0;
  const maxConsecutiveLosses = risk.data?.max_consecutive_losses ?? risk.data?.consecutive_losses ?? 0;
  const dailyDrawdown = risk.data?.daily_drawdown_pct ?? 0;
  const weeklyDrawdown = risk.data?.weekly_drawdown_pct ?? 0;

  return (
    <div>
      <PageHeader
        title="Risk Dashboard"
        description="Paper trading risk, exposure, and trade quality at a glance."
        actions={(
          <Button onClick={() => risk.refetch()} disabled={risk.isFetching || latestBacktestQuery.isFetching}>
            <RefreshCw className={`h-4 w-4 ${risk.isFetching || latestBacktestQuery.isFetching ? "animate-spin" : ""}`} />
            Refresh
          </Button>
        )}
      />

      {risk.isLoading ? (
        <div className="mb-4 rounded-lg border border-border bg-white p-4 text-sm text-muted-foreground">
          Loading risk status...
        </div>
      ) : null}

      {risk.isError ? (
        <div className="mb-4 flex items-start gap-3 rounded-lg border border-dashed border-border bg-white p-4 text-sm text-muted-foreground">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />
          <p>Risk status is unavailable. The dashboard is still showing paper trading analytics when possible.</p>
        </div>
      ) : null}

      {isBlocked ? (
        <div className="mb-4 flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">
          <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" />
          <div>
            <p className="font-semibold">RiskGuard {riskState}</p>
            <p className="mt-1">{reason}</p>
          </div>
        </div>
      ) : null}

      <section className="rounded-lg border border-border bg-white p-4">
        <div className="mb-4 flex items-center justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold text-foreground">Risk Status</h3>
            <p className="text-xs text-muted-foreground">Current guard state and live paper-trading exposure.</p>
          </div>
          <span className="rounded-full bg-muted px-3 py-1 text-xs text-muted-foreground">{riskState}</span>
        </div>
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          <MetricCard label="RiskGuard State" value={riskState} />
          <MetricCard label="Daily Drawdown" value={formatPercent(dailyDrawdown)} />
          <MetricCard label="Weekly Drawdown" value={formatPercent(weeklyDrawdown)} />
          <MetricCard label="Max Consecutive Losses" value={formatNumber(maxConsecutiveLosses, 0)} />
          <MetricCard label="Trades Today" value={formatNumber(tradesToday, 0)} />
          <MetricCard label="Current Exposure" value={currentExposure === null ? "-" : formatNumber(currentExposure, 2)} />
          <MetricCard label="Open Positions" value={formatNumber(risk.data?.open_positions ?? 0, 0)} />
          <MetricCard label="Last Blocked At" value={shortDate(risk.data?.last_blocked_at ?? undefined)} />
          <MetricCard label="Block Reason" value={reason} />
        </div>
      </section>

      <section className="mt-4">
        <div className="mb-4">
          <h3 className="text-sm font-semibold text-foreground">Paper Trading Analytics</h3>
          <p className="text-xs text-muted-foreground">Latest backtest run or in-session report, used as a proxy for paper analytics.</p>
        </div>

        {!latestReport ? (
          <div className="rounded-lg border border-dashed border-border bg-white p-6 text-sm text-muted-foreground">
            No paper trading analytics are available yet. Run a backtest to populate this section.
          </div>
        ) : (
          <div className="space-y-4">
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              <MetricCard label="Realized PnL" value={formatNumber(latestReport.net_profit, 2)} />
              <MetricCard label="Winrate" value={formatPercent(latestReport.winrate)} />
              <MetricCard label="Max Drawdown" value={formatNumber(latestReport.max_drawdown, 2)} />
              <MetricCard label="Total Trades" value={formatNumber(latestReport.total_trades, 0)} />
              <MetricCard label="Max Winning Streak" value={formatNumber(maxWinningStreak, 0)} />
              <MetricCard label="Max Losing Streak" value={formatNumber(maxLosingStreak, 0)} />
              <MetricCard label="Current Streak" value={currentStreak ? `${currentStreak.type} x${currentStreak.length}` : "-"} />
              <MetricCard label="Avg R Multiple" value={formatNumber(latestReport.avg_r_multiple ?? null, 2)} />
            </div>

            <div className="grid gap-4 xl:grid-cols-3">
              <EquityCurveChart trades={trades} />
              <DrawdownCurveChart trades={trades} />
              <MonthlyReturnsChart trades={trades} />
            </div>

            <div className="grid gap-4 xl:grid-cols-3">
              <PnLBarChart title="PnL by Regime" rows={regimeRows} emptyText="No regime-sliced trade data available." />
              <PnLBarChart title="PnL by Strategy" rows={strategyRows} emptyText="No strategy-sliced trade data available." />
              <PnLBarChart title="PnL by Setup Type" rows={setupTypeRows} emptyText="No setup-sliced trade data available." />
            </div>

            <div className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
              <ConfidenceScatterChart trades={trades} />
              <section className="rounded-lg border border-border bg-white p-4">
                <h3 className="text-sm font-semibold text-foreground">Streak Summary</h3>
                {streaks.length ? (
                  <>
                    <div className="mt-4 grid gap-4 md:grid-cols-3">
                      <MetricCard label="Max Winning Streak" value={formatNumber(maxWinningStreak, 0)} />
                      <MetricCard label="Max Losing Streak" value={formatNumber(maxLosingStreak, 0)} />
                      <MetricCard label="Recent Streak" value={currentStreak ? `${currentStreak.type} x${currentStreak.length}` : "-"} />
                    </div>
                    <div className="mt-4 overflow-x-auto">
                      <table className="min-w-full text-left text-sm">
                        <thead className="text-xs uppercase tracking-wide text-muted-foreground">
                          <tr>
                            <th className="py-2 pr-4">Type</th>
                            <th className="py-2 pr-4">Length</th>
                            <th className="py-2 pr-4">Net PnL</th>
                            <th className="py-2 pr-4">Start</th>
                            <th className="py-2 pr-4">End</th>
                          </tr>
                        </thead>
                        <tbody>
                          {streaks.slice(-8).map((row, index) => (
                            <tr key={`${row.type}-${row.start}-${index}`} className="border-t border-border">
                              <td className="py-2 pr-4 font-medium text-foreground">{row.type}</td>
                              <td className="py-2 pr-4 text-muted-foreground">{row.length}</td>
                              <td className={row.net_pnl >= 0 ? "py-2 pr-4 text-emerald-700" : "py-2 pr-4 text-red-700"}>
                                {formatNumber(row.net_pnl, 2)}
                              </td>
                              <td className="py-2 pr-4 text-muted-foreground">{shortDate(row.start)}</td>
                              <td className="py-2 pr-4 text-muted-foreground">{shortDate(row.end)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </>
                ) : (
                  <p className="mt-3 text-sm text-muted-foreground">No streak data available.</p>
                )}
              </section>
            </div>
          </div>
        )}
      </section>

      <section className="mt-4 rounded-lg border border-border bg-white p-4">
        <div className="mb-4">
          <h3 className="text-sm font-semibold text-foreground">Risk Events</h3>
          <p className="text-xs text-muted-foreground">Operational audit trail for blocks, warnings, and exposures.</p>
        </div>
        <DataTable
          rows={riskEvents}
          columns={[
            { key: "timestamp", label: "Timestamp", render: (value) => shortDate(String(value ?? "-")) },
            { key: "event_type", label: "Event Type" },
            { key: "severity", label: "Severity" },
            { key: "message", label: "Message" },
            { key: "affected_symbol", label: "Affected Symbol" },
            { key: "action_taken", label: "Action Taken" },
          ]}
          emptyText="No risk events recorded yet."
        />
      </section>
    </div>
  );
}
