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
import { DrawdownCurveChart } from "@/components/backtest/DrawdownCurveChart";
import { EquityCurveChart } from "@/components/backtest/EquityCurveChart";
import { MonthlyReturnsChart } from "@/components/charts/BacktestCharts";
import { DataTable } from "@/components/tables/DataTable";
import { MetricCard } from "@/components/cards/MetricCard";
import { formatNumber, formatPercent, shortDate } from "@/lib/utils";
import type { BacktestReport, Trade } from "@/types";

type SliceRow = { label: string; net_pnl: number; trade_count: number; winrate: number };
type ConfidencePoint = { confidence: number; pnl: number; outcome: string };
type StreakRow = { type: "WIN" | "LOSS" | "BREAKEVEN"; length: number; net_pnl: number; start: string; end: string };

function toNumber(value: unknown): number {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return 0;
}

function buildRows(trades: Trade[], selector: (trade: Trade) => string): SliceRow[] {
  const buckets = new Map<string, Trade[]>();
  for (const trade of trades) {
    const label = selector(trade) || "UNKNOWN";
    const bucket = buckets.get(label) ?? [];
    bucket.push(trade);
    buckets.set(label, bucket);
  }
  return [...buckets.entries()]
    .map(([label, bucket]) => {
      const wins = bucket.filter((trade) => toNumber(trade.pnl) > 0).length;
      const netPnl = bucket.reduce((sum, trade) => sum + toNumber(trade.pnl), 0);
      return { label, net_pnl: netPnl, trade_count: bucket.length, winrate: bucket.length ? wins / bucket.length : 0 };
    })
    .sort((left, right) => right.net_pnl - left.net_pnl);
}

function buildConfidencePoints(trades: Trade[]): ConfidencePoint[] {
  return trades.map((trade) => ({
    confidence: Math.abs(toNumber(trade.confidence)) <= 1 ? toNumber(trade.confidence) : toNumber(trade.confidence) / 100,
    pnl: toNumber(trade.pnl),
    outcome: toNumber(trade.pnl) > 0 ? "WIN" : toNumber(trade.pnl) < 0 ? "LOSS" : "BREAKEVEN",
  }));
}

function buildStreaks(trades: Trade[]): StreakRow[] {
  const rows: StreakRow[] = [];
  let current: StreakRow["type"] | null = null;
  let length = 0;
  let netPnl = 0;
  let start = "";
  let end = "";
  const flush = () => {
    if (!current || !length) return;
    rows.push({ type: current, length, net_pnl: netPnl, start, end });
  };
  for (const trade of trades) {
    const pnl = toNumber(trade.pnl);
    const next: StreakRow["type"] = pnl > 0 ? "WIN" : pnl < 0 ? "LOSS" : "BREAKEVEN";
    const stamp = trade.closed_at || trade.opened_at || "";
    if (next !== current) {
      flush();
      current = next;
      length = 1;
      netPnl = pnl;
      start = stamp;
      end = stamp;
      continue;
    }
    length += 1;
    netPnl += pnl;
    end = stamp;
  }
  flush();
  return rows;
}

export function PaperTradingAnalytics({ report }: { report?: BacktestReport | null }) {
  const trades = report?.trades ?? [];
  const regimeRows = buildRows(trades, (trade) => trade.market_regime ?? "UNKNOWN");
  const strategyRows = buildRows(trades, (trade) => trade.strategy ?? "UNKNOWN");
  const setupRows = buildRows(trades, (trade) => trade.setup_type ?? "UNKNOWN");
  const confidencePoints = buildConfidencePoints(trades);
  const streaks = buildStreaks(trades);

  return (
    <section className="space-y-4">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Realized PnL" value={formatNumber(report?.net_profit, 2)} />
        <MetricCard label="Winrate" value={formatPercent(report?.winrate)} />
        <MetricCard label="Drawdown" value={formatNumber(report?.max_drawdown, 2)} />
        <MetricCard label="Trades" value={report?.total_trades ?? "-"} />
      </div>
      <div className="grid gap-4 xl:grid-cols-3">
        <EquityCurveChart trades={trades} />
        <DrawdownCurveChart trades={trades} />
        <MonthlyReturnsChart trades={trades} />
      </div>
      <div className="grid gap-4 xl:grid-cols-3">
        <SliceBar title="PnL by Regime" rows={regimeRows} />
        <SliceBar title="PnL by Strategy" rows={strategyRows} />
        <SliceBar title="PnL by Setup Type" rows={setupRows} />
      </div>
      <div className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
        <section className="rounded-lg border border-border bg-white p-4 shadow-sm">
          <h3 className="text-sm font-semibold">Confidence vs Actual Result</h3>
          <div className="mt-4 h-72">
            <ResponsiveContainer width="100%" height="100%">
              <ScatterChart margin={{ top: 8, right: 8, left: 8, bottom: 8 }}>
                <CartesianGrid stroke="#e5e7eb" />
                <XAxis type="number" dataKey="confidence" domain={[0, 1]} tickFormatter={(value) => `${Math.round(Number(value) * 100)}%`} />
                <YAxis type="number" dataKey="pnl" tickFormatter={(value) => formatNumber(Number(value), 0)} />
                <Tooltip />
                <Scatter data={confidencePoints}>
                  {confidencePoints.map((point, index) => (
                    <Cell key={`${point.outcome}-${index}`} fill={point.pnl >= 0 ? "#0f766e" : "#dc2626"} />
                  ))}
                </Scatter>
              </ScatterChart>
            </ResponsiveContainer>
          </div>
        </section>
        <section className="rounded-lg border border-border bg-white p-4 shadow-sm">
          <h3 className="text-sm font-semibold">Streaks</h3>
          <div className="mt-4 overflow-x-auto">
            <DataTable<StreakRow>
              rows={streaks.slice(-8)}
              emptyText="No streaks."
              columns={[
                { key: "type", label: "Type" },
                { key: "length", label: "Length" },
                { key: "net_pnl", label: "Net PnL", render: (value) => formatNumber(Number(value), 2) },
                { key: "start", label: "Start", render: (value) => shortDate(String(value)) },
                { key: "end", label: "End", render: (value) => shortDate(String(value)) },
              ]}
            />
          </div>
        </section>
      </div>
    </section>
  );
}

function SliceBar({ title, rows }: { title: string; rows: SliceRow[] }) {
  return (
    <section className="rounded-lg border border-border bg-white p-4 shadow-sm">
      <h3 className="text-sm font-semibold">{title}</h3>
      <div className="mt-4 h-64">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={rows}>
            <CartesianGrid stroke="#e5e7eb" vertical={false} />
            <XAxis dataKey="label" tick={{ fontSize: 11 }} interval={0} />
            <YAxis tickFormatter={(value) => formatNumber(Number(value), 0)} />
            <Tooltip formatter={(value) => formatNumber(Number(value), 2)} />
            <Bar dataKey="net_pnl" fill="#2563eb">
              {rows.map((entry, index) => (
                <Cell key={entry.label} fill={index % 2 === 0 ? "#2563eb" : "#0f766e"} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
