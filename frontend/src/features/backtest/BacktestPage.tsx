import { BarChart3, Layers3 } from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { MetricCard } from "@/components/cards/MetricCard";
import {
  DrawdownCurveChart,
  EquityCurveChart,
  MonthlyReturnsChart,
} from "@/components/charts/BacktestCharts";
import { Button } from "@/components/forms/Button";
import { PageHeader } from "@/components/layout/PageHeader";
import { DataTable } from "@/components/tables/DataTable";
import { useActions } from "@/hooks/useApiQueries";
import { useSessionStore } from "@/hooks/useSessionStore";
import { cn, formatNumber, formatPercent } from "@/lib/utils";
import type { BacktestReport, BacktestResponse, Trade } from "@/types";

type SliceRow = {
  key: string;
  total_trades: number;
  winrate: number;
  net_profit: number;
  profit_factor: number;
  expectancy: number;
};

type WaitReasonRow = {
  reason: string;
  count: number;
};

type AblationRow = {
  module_enabled: string;
  net_profit: number;
  profit_factor: number;
  max_drawdown: number;
  winrate: number;
  expectancy: number;
  trade_count: number;
  delta_vs_baseline: number;
};

const SLICE_GROUPS: Array<{
  title: string;
  reportKey: string;
  fallback: (trade: Trade) => string;
}> = [
  { title: "Regime", reportKey: "by_market_regime", fallback: (trade) => trade.market_regime ?? "UNKNOWN" },
  { title: "Strategy", reportKey: "by_strategy", fallback: (trade) => trade.strategy ?? "UNKNOWN" },
  { title: "Setup Type", reportKey: "by_setup_type", fallback: (trade) => trade.setup_type ?? "UNKNOWN" },
  { title: "Setup Grade", reportKey: "by_setup_grade", fallback: (trade) => trade.setup_grade ?? "UNKNOWN" },
  { title: "Signal", reportKey: "by_signal", fallback: (trade) => trade.direction ?? "UNKNOWN" },
  { title: "Wait Reason", reportKey: "by_wait_reason", fallback: (trade) => trade.wait_reason ?? "NONE" },
  { title: "Conflict Level", reportKey: "by_conflict_level", fallback: (trade) => trade.conflict_level ?? "UNKNOWN" },
  { title: "Probability Source", reportKey: "by_probability_source", fallback: (trade) => trade.probability_source ?? "UNKNOWN" },
  { title: "Model Scope", reportKey: "by_model_scope", fallback: (trade) => trade.model_scope ?? "UNKNOWN" },
  { title: "Confluence Bucket", reportKey: "by_confluence_bucket", fallback: (trade) => confluenceBucket(trade.confluence_score) },
];

const WAIT_REASONS = [
  "WAIT_LOW_CONFIDENCE",
  "WAIT_STRATEGY_CONFLICT",
  "WAIT_MTF_CONFLICT",
  "WAIT_RISK_BLOCK",
  "WAIT_SAFETY_FILTER",
  "WAIT_DATA_QUALITY",
  "WAIT_MODEL_UNCERTAIN",
  "WAIT_HIGH_VOLATILITY",
  "WAIT_TRANSITION_WARNING",
  "WAIT_INDUCEMENT_RISK",
  "WAIT_NO_CLEAR_SETUP",
] as const;

function pickReport(payload?: BacktestResponse | null): BacktestReport | null {
  return payload?.ml_enhanced ?? payload?.rule_only ?? null;
}

function getBaselineProfit(source?: BacktestReport | BacktestResponse | null): number | null {
  const ablation = source?.ablation_result;
  if (!ablation) return null;
  if (Array.isArray(ablation)) {
    const baseline = ablation.find((row) => isBaselineRow(row));
    return baseline ? asNumber((baseline as Record<string, unknown>).net_profit) : null;
  }
  if (typeof ablation === "object") {
    for (const value of Object.values(ablation)) {
      if (value && typeof value === "object" && isBaselineRow(value as Record<string, unknown>)) {
        return asNumber((value as Record<string, unknown>).net_profit);
      }
    }
  }
  return null;
}

function isBaselineRow(row: Record<string, unknown>) {
  const label = String(row.module_enabled ?? row.scenario ?? row.name ?? row.key ?? row.mode ?? "").toLowerCase();
  return label === "baseline" || label === "base" || label === "default" || row.baseline === true;
}

function asNumber(value: unknown): number {
  const number = typeof value === "number" ? value : Number(value);
  return Number.isFinite(number) ? number : 0;
}

function pickBucket(trade: Trade, fallback: (trade: Trade) => string) {
  return String(fallback(trade) ?? "UNKNOWN") || "UNKNOWN";
}

function aggregateSlice(trades: Trade[], fallback: (trade: Trade) => string): SliceRow[] {
  const grouped = new Map<string, Trade[]>();
  for (const trade of trades) {
    const key = pickBucket(trade, fallback);
    const bucket = grouped.get(key) ?? [];
    bucket.push(trade);
    grouped.set(key, bucket);
  }

  return [...grouped.entries()]
    .map(([key, bucket]) => {
      const totalTrades = bucket.length;
      const wins = bucket.filter((trade) => trade.pnl > 0).length;
      const netProfit = bucket.reduce((sum, trade) => sum + asNumber(trade.pnl), 0);
      const grossProfit = bucket.filter((trade) => trade.pnl > 0).reduce((sum, trade) => sum + asNumber(trade.pnl), 0);
      const grossLoss = Math.abs(bucket.filter((trade) => trade.pnl < 0).reduce((sum, trade) => sum + asNumber(trade.pnl), 0));
      return {
        key,
        total_trades: totalTrades,
        winrate: totalTrades ? wins / totalTrades : 0,
        net_profit: netProfit,
        profit_factor: grossLoss > 0 ? grossProfit / grossLoss : grossProfit > 0 ? Number.POSITIVE_INFINITY : 0,
        expectancy: totalTrades ? netProfit / totalTrades : 0,
      };
    })
    .sort((left, right) => right.net_profit - left.net_profit);
}

function sliceRowsFromReport(report: BacktestReport | null, trades: Trade[], reportKey: string, fallback: (trade: Trade) => string) {
  const grouped = report?.grouped?.[reportKey];
  if (grouped && typeof grouped === "object") {
    return Object.entries(grouped)
      .map(([key, value]) => ({
        key,
        total_trades: asNumber(value.total_trades),
        winrate: asNumber(value.winrate),
        net_profit: asNumber(value.net_profit),
        profit_factor: asNumber(value.profit_factor),
        expectancy: asNumber(value.expectancy),
      }))
      .sort((left, right) => right.net_profit - left.net_profit);
  }
  return aggregateSlice(trades, fallback);
}

function confluenceBucket(value?: number | null) {
  const score = asNumber(value);
  if (!Number.isFinite(score)) return "UNKNOWN";
  if (score >= 0.8) return "0.80-1.00";
  if (score >= 0.65) return "0.65-0.79";
  if (score >= 0.5) return "0.50-0.64";
  return "<0.50";
}

function waitReasonDistribution(trades: Trade[]) {
  const counts: Record<string, number> = Object.fromEntries(WAIT_REASONS.map((reason) => [reason, 0]));
  for (const trade of trades) {
    if (!trade.wait_reason) continue;
    counts[trade.wait_reason] = (counts[trade.wait_reason] ?? 0) + 1;
  }
  return WAIT_REASONS.map((reason) => ({ reason, count: counts[reason] ?? 0 }));
}

function toNumericMetrics(source?: BacktestReport | BacktestResponse | null) {
  const analytics = source?.backtest_analytics;
  if (!analytics || typeof analytics !== "object" || Array.isArray(analytics)) return [];
  return Object.entries(analytics)
    .filter(([, value]) => typeof value === "number" && Number.isFinite(value))
    .map(([metric, value]) => ({ metric, value: Number(value) }))
    .sort((left, right) => Math.abs(right.value) - Math.abs(left.value))
    .slice(0, 8);
}

function normalizedAblationRows(source?: BacktestReport | BacktestResponse | null): AblationRow[] {
  const payload = source?.ablation_result;
  const baselineProfit = getBaselineProfit(source) ?? 0;
  if (!payload) return [];

  const rows = Array.isArray(payload)
    ? payload.map((row, index) => normalizeAblationRow(row as Record<string, unknown>, index))
    : typeof payload === "object"
      ? Object.entries(payload).map(([key, value], index) =>
          normalizeAblationRow(
            (value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : { module_enabled: key, net_profit: value }) as Record<string, unknown>,
            index,
          ),
        )
      : [];

  return rows.map((row) => ({
    ...row,
    delta_vs_baseline: row.net_profit - baselineProfit,
  }));
}

function normalizeAblationRow(row: Record<string, unknown>, index: number): AblationRow {
  const label = String(
    row.module_enabled ??
      row.module_name ??
      row.scenario ??
      row.name ??
      row.variant ??
      row.component ??
      row.mode ??
      row.key ??
      `Scenario ${index + 1}`,
  );
  return {
    module_enabled: label,
    net_profit: asNumber(row.net_profit ?? row.pnl),
    profit_factor: asNumber(row.profit_factor),
    max_drawdown: asNumber(row.max_drawdown ?? row.drawdown),
    winrate: asNumber(row.winrate),
    expectancy: asNumber(row.expectancy),
    trade_count: asNumber(row.trade_count ?? row.total_trades ?? row.trades),
    delta_vs_baseline: 0,
  };
}

function metricText(value: number | null | undefined, digits = 2) {
  return value === null || value === undefined || Number.isNaN(value) ? "-" : formatNumber(value, digits);
}

function boolText(value: unknown) {
  if (value === true) return "Yes";
  if (value === false) return "No";
  return "-";
}

function severityCell(value: number) {
  if (value > 0) return "text-emerald-700";
  if (value < 0) return "text-red-700";
  return "text-muted-foreground";
}

function SliceSection({
  title,
  rows,
  emptyText,
}: {
  title: string;
  rows: SliceRow[];
  emptyText: string;
}) {
  return (
    <section className="rounded-lg border border-border bg-white p-4 shadow-sm">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold">{title}</h3>
        <span className="rounded-full bg-muted px-2.5 py-1 text-[11px] font-semibold text-muted-foreground">
          {rows.length}
        </span>
      </div>
      {rows.length ? (
        <div className="space-y-4">
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={rows} layout="vertical" margin={{ left: 70, right: 20 }}>
                <CartesianGrid stroke="#e5e7eb" horizontal={false} />
                <XAxis type="number" />
                <YAxis type="category" dataKey="key" width={110} tick={{ fontSize: 11 }} />
                <Tooltip formatter={(value) => formatNumber(Number(value), 2)} />
                <Bar dataKey="net_profit" fill="#2563eb">
                  {rows.map((entry, index) => (
                    <Cell key={entry.key} fill={index % 2 === 0 ? "#2563eb" : "#0f766e"} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          <DataTable<SliceRow>
            rows={rows}
            emptyText={emptyText}
            columns={[
              { key: "key", label: "Bucket" },
              { key: "total_trades", label: "Trades" },
              { key: "winrate", label: "Winrate", render: (value) => formatPercent(Number(value)) },
              { key: "net_profit", label: "Net PnL", render: (value) => formatNumber(Number(value), 2) },
              { key: "profit_factor", label: "PF", render: (value) => formatNumber(Number(value), 2) },
              { key: "expectancy", label: "Expectancy", render: (value) => formatNumber(Number(value), 2) },
            ]}
          />
        </div>
      ) : (
        <div className="rounded-lg border border-dashed border-border p-6 text-sm text-muted-foreground">
          {emptyText}
        </div>
      )}
    </section>
  );
}

function WaitReasonChart({ rows }: { rows: WaitReasonRow[] }) {
  return (
    <div className="h-72">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} margin={{ left: 20, right: 20 }}>
          <CartesianGrid stroke="#e5e7eb" vertical={false} />
          <XAxis dataKey="reason" tick={{ fontSize: 10 }} interval={0} angle={-20} height={70} />
          <YAxis />
          <Tooltip />
          <Bar dataKey="count" fill="#0f766e" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function BacktestPage() {
  const actions = useActions();
  const { latestBacktest, setLatestBacktest } = useSessionStore();
  const report = pickReport(latestBacktest);
  const trades = report?.trades ?? [];
  const analyticsRows = toNumericMetrics(latestBacktest ?? report);

  const sliceSections = SLICE_GROUPS.map((group) => ({
    title: group.title,
    rows: sliceRowsFromReport(report, trades, group.reportKey, group.fallback),
  }));

  const waitRows = waitReasonDistribution(trades);
  const ablationRows = normalizedAblationRows(latestBacktest ?? report);
  const run = async () => {
    const result = await actions.runBacktest.mutateAsync();
    setLatestBacktest(result);
  };
  const hasReport = Boolean(report || latestBacktest);

  return (
    <div>
      <PageHeader
        title="Backtest"
        description="Multi-slice backtest analytics for research, debug, and ablation study."
        actions={
          <Button onClick={run} disabled={actions.runBacktest.isPending}>
            <BarChart3 className="h-4 w-4" />
            {actions.runBacktest.isPending ? "Running..." : "Run Backtest"}
          </Button>
        }
      />

      {actions.runBacktest.isPending ? (
        <div className="mb-4 rounded-lg border border-border bg-white p-3 text-sm text-muted-foreground">
          Running backtest...
        </div>
      ) : null}

      {actions.runBacktest.isError ? (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          Backtest failed. Please verify data/model setup and retry.
        </div>
      ) : null}

      {!hasReport ? (
        <div className="mb-4 rounded-lg border border-dashed border-border bg-white p-6 text-sm text-muted-foreground">
          No backtest report yet. Run a backtest to inspect metrics, slices, wait reasons, and ablation results.
        </div>
      ) : null}

      <section className="rounded-lg border border-border bg-white p-4 shadow-sm">
        <div className="mb-3 flex items-center justify-between gap-2">
          <h3 className="text-sm font-semibold">A. Overall Metrics</h3>
          <span className="inline-flex items-center gap-1 rounded-full bg-muted px-2.5 py-1 text-[11px] font-semibold text-muted-foreground">
            <Layers3 className="h-3.5 w-3.5" />
            {report?.mode ?? "latest"}
          </span>
        </div>
        <div className="grid gap-4 md:grid-cols-3 xl:grid-cols-4">
          <MetricCard label="Total Trades" value={report?.total_trades ?? "-"} />
          <MetricCard label="Winrate" value={formatPercent(report?.winrate)} />
          <MetricCard label="Net Profit" value={formatNumber(report?.net_profit, 2)} />
          <MetricCard label="Profit Factor" value={metricText(report?.profit_factor ?? null, 2)} />
          <MetricCard label="Max Drawdown" value={formatNumber(report?.max_drawdown, 2)} />
          <MetricCard label="Expectancy" value={formatNumber(report?.expectancy, 2)} />
          <MetricCard label="Avg R Multiple" value={metricText(report?.avg_r_multiple ?? null, 2)} />
          <MetricCard label="Best Trade" value={metricText(report?.best_trade ?? null, 2)} />
          <MetricCard label="Worst Trade" value={metricText(report?.worst_trade ?? null, 2)} />
        </div>
      </section>

      <div className="mt-4 space-y-4">
        <section className="grid gap-4 xl:grid-cols-2">
          <EquityCurveChart trades={trades} />
          <DrawdownCurveChart trades={trades} />
        </section>
        <MonthlyReturnsChart trades={trades} />

        <section className="rounded-lg border border-border bg-white p-4 shadow-sm">
          <h3 className="mb-3 text-sm font-semibold">C. Slice Analytics</h3>
          <div className="grid gap-4 xl:grid-cols-2">
            {sliceSections.map((slice) => (
              <SliceSection key={slice.title} title={slice.title} rows={slice.rows} emptyText={`No ${slice.title.toLowerCase()} analytics.`} />
            ))}
          </div>
        </section>

        <section className="rounded-lg border border-border bg-white p-4 shadow-sm">
          <h3 className="mb-3 text-sm font-semibold">D. WAIT Reason Distribution</h3>
          {waitRows.some((row) => row.count > 0) ? (
            <>
              <WaitReasonChart rows={waitRows} />
              <div className="mt-4">
                <DataTable<WaitReasonRow>
                  rows={waitRows}
                  emptyText="No wait reason distribution."
                  columns={[
                    { key: "reason", label: "Reason" },
                    { key: "count", label: "Count" },
                  ]}
                />
              </div>
            </>
          ) : (
            <div className="rounded-lg border border-dashed border-border p-6 text-sm text-muted-foreground">
              No WAIT reason distribution available.
            </div>
          )}
        </section>

        <section className="rounded-lg border border-border bg-white p-4 shadow-sm">
          <h3 className="mb-3 text-sm font-semibold">E. Ablation Study</h3>
          {ablationRows.length ? (
            <DataTable<AblationRow>
              rows={ablationRows}
              emptyText="No ablation results."
              columns={[
                {
                  key: "module_enabled",
                  label: "Module Enabled",
                  render: (value, row) => (
                    <span className={cn("font-medium", row.delta_vs_baseline >= 0 ? "text-emerald-700" : "text-red-700")}>
                      {boolText(value)}
                    </span>
                  ),
                },
                { key: "net_profit", label: "Net Profit", render: (value) => formatNumber(Number(value), 2) },
                { key: "profit_factor", label: "Profit Factor", render: (value) => metricText(Number(value), 2) },
                { key: "max_drawdown", label: "Max Drawdown", render: (value) => formatNumber(Number(value), 2) },
                { key: "winrate", label: "Winrate", render: (value) => formatPercent(Number(value)) },
                { key: "expectancy", label: "Expectancy", render: (value) => formatNumber(Number(value), 2) },
                { key: "trade_count", label: "Trade Count" },
                {
                  key: "delta_vs_baseline",
                  label: "Delta vs Baseline",
                  render: (value, row) => (
                    <span className={severityCell(asNumber(value))}>{formatNumber(Number(value), 2)}</span>
                  ),
                },
              ]}
            />
          ) : (
            <div className="rounded-lg border border-dashed border-border p-6 text-sm text-muted-foreground">
              No ablation study returned by backend.
            </div>
          )}
        </section>

        <section className="rounded-lg border border-border bg-white p-4 shadow-sm">
          <details>
            <summary className="cursor-pointer text-sm font-medium">Raw backtest payload</summary>
            <pre className="mt-3 max-h-80 overflow-auto rounded bg-muted p-3 text-xs">
              {JSON.stringify(latestBacktest ?? report ?? {}, null, 2)}
            </pre>
          </details>
        </section>
      </div>
    </div>
  );
}
