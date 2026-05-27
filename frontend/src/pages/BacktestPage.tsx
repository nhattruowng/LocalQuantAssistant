import { BarChart3 } from "lucide-react";
import { AblationResultTable, type AblationResultRow } from "@/components/backtest/AblationResultTable";
import { BacktestMetricsCard } from "@/components/backtest/BacktestMetricsCard";
import { DrawdownCurveChart } from "@/components/backtest/DrawdownCurveChart";
import { EquityCurveChart } from "@/components/backtest/EquityCurveChart";
import { SliceAnalyticsTable, type SliceAnalyticsRow } from "@/components/backtest/SliceAnalyticsTable";
import { WaitReasonChart } from "@/components/backtest/WaitReasonChart";
import { Button } from "@/components/forms/Button";
import { PageHeader } from "@/components/layout/PageHeader";
import { DataTable } from "@/components/tables/DataTable";
import { useActions } from "@/hooks/useApiQueries";
import { useSessionStore } from "@/hooks/useSessionStore";
import type { BacktestReport, BacktestResponse, Trade } from "@/types";

type WaitReasonRow = {
  reason: string;
  count: number;
};

const SLICE_GROUPS: Array<{ title: string; reportKey: string; fallback: (trade: Trade) => string }> = [
  { title: "Regime", reportKey: "by_market_regime", fallback: (trade) => trade.market_regime ?? "UNKNOWN" },
  { title: "Strategy", reportKey: "by_strategy", fallback: (trade) => trade.strategy ?? "UNKNOWN" },
  { title: "Setup Type", reportKey: "by_setup_type", fallback: (trade) => trade.setup_type ?? "UNKNOWN" },
  { title: "Wait Reason", reportKey: "by_wait_reason", fallback: (trade) => trade.wait_reason ?? "NONE" },
  { title: "Conflict Level", reportKey: "by_conflict_level", fallback: (trade) => trade.conflict_level ?? "UNKNOWN" },
];

function toNumber(value: unknown): number {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return 0;
}

function pickReport(payload?: BacktestResponse | null): BacktestReport | null {
  return payload?.ml_enhanced ?? payload?.rule_only ?? null;
}

function aggregateSlice(trades: Trade[], fallback: (trade: Trade) => string): SliceAnalyticsRow[] {
  const grouped = new Map<string, Trade[]>();
  for (const trade of trades) {
    const key = String(fallback(trade) || "UNKNOWN");
    const bucket = grouped.get(key) ?? [];
    bucket.push(trade);
    grouped.set(key, bucket);
  }
  return [...grouped.entries()]
    .map(([key, bucket]) => {
      const totalTrades = bucket.length;
      const wins = bucket.filter((trade) => toNumber(trade.pnl) > 0).length;
      const netProfit = bucket.reduce((sum, trade) => sum + toNumber(trade.pnl), 0);
      const grossProfit = bucket.filter((trade) => toNumber(trade.pnl) > 0).reduce((sum, trade) => sum + toNumber(trade.pnl), 0);
      const grossLoss = Math.abs(bucket.filter((trade) => toNumber(trade.pnl) < 0).reduce((sum, trade) => sum + toNumber(trade.pnl), 0));
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

function sliceRowsFromReport(report: BacktestReport | null, trades: Trade[], reportKey: string, fallback: (trade: Trade) => string): SliceAnalyticsRow[] {
  const grouped = report?.grouped?.[reportKey];
  if (grouped && typeof grouped === "object") {
    return Object.entries(grouped)
      .map(([key, value]) => ({
        key,
        total_trades: toNumber(value.total_trades),
        winrate: toNumber(value.winrate),
        net_profit: toNumber(value.net_profit),
        profit_factor: toNumber(value.profit_factor),
        expectancy: toNumber(value.expectancy),
      }))
      .sort((left, right) => right.net_profit - left.net_profit);
  }
  return aggregateSlice(trades, fallback);
}

function waitReasonRows(trades: Trade[]): WaitReasonRow[] {
  const grouped = new Map<string, number>();
  for (const trade of trades) {
    const reason = String(trade.wait_reason ?? "NONE");
    grouped.set(reason, (grouped.get(reason) ?? 0) + 1);
  }
  return [...grouped.entries()]
    .map(([reason, count]) => ({ reason, count }))
    .sort((left, right) => right.count - left.count);
}

function normalizeAblationRows(source?: BacktestReport | BacktestResponse | null): AblationResultRow[] {
  const payload = source?.ablation_result;
  if (!payload) return [];
  const rows = Array.isArray(payload)
    ? payload.map((row, index) => normalizeAblationRow(row as Record<string, unknown>, index))
    : typeof payload === "object"
      ? Object.entries(payload).map(([key, value], index) =>
          normalizeAblationRow(
            value && typeof value === "object" && !Array.isArray(value)
              ? (value as Record<string, unknown>)
              : { module_enabled: key, net_profit: value },
            index,
          ),
        )
      : [];

  const baseline = rows.find((row) => /baseline|base|default/i.test(row.module_enabled))?.net_profit ?? 0;
  return rows.map((row) => ({ ...row, delta_vs_baseline: row.net_profit - baseline }));
}

function normalizeAblationRow(row: Record<string, unknown>, index: number): AblationResultRow {
  return {
    module_enabled: String(row.module_enabled ?? row.module_name ?? row.scenario ?? row.name ?? `Scenario ${index + 1}`),
    net_profit: toNumber(row.net_profit ?? row.pnl),
    profit_factor: toNumber(row.profit_factor),
    max_drawdown: toNumber(row.max_drawdown ?? row.drawdown),
    winrate: toNumber(row.winrate),
    expectancy: toNumber(row.expectancy),
    trade_count: toNumber(row.trade_count ?? row.total_trades ?? row.trades),
    delta_vs_baseline: 0,
  };
}

export function BacktestPage() {
  const actions = useActions();
  const { latestBacktest, setLatestBacktest } = useSessionStore();
  const report = pickReport(latestBacktest);
  const trades = report?.trades ?? [];
  const waitRows = waitReasonRows(trades);
  const ablationRows = normalizeAblationRows(latestBacktest ?? report);
  const hasReport = Boolean(report || latestBacktest);

  const runBacktest = async () => {
    const result = await actions.runBacktest.mutateAsync();
    setLatestBacktest(result);
  };

  return (
    <div>
      <PageHeader
        title="Backtest Research Dashboard"
        description="Overall metrics, curves, slice analytics, wait reasons, and ablation result."
        actions={
          <Button onClick={runBacktest} disabled={actions.runBacktest.isPending}>
            <BarChart3 className="h-4 w-4" />
            {actions.runBacktest.isPending ? "Running..." : "Run Backtest"}
          </Button>
        }
      />

      {!hasReport ? (
        <div className="mb-4 rounded-lg border border-dashed border-border bg-white p-6 text-sm text-muted-foreground">
          No backtest report yet. Run backtest to populate this dashboard.
        </div>
      ) : null}

      <BacktestMetricsCard report={report} />

      <section className="mt-4 grid gap-4 xl:grid-cols-2">
        <EquityCurveChart trades={trades} />
        <DrawdownCurveChart trades={trades} />
      </section>

      <section className="mt-4 rounded-lg border border-border bg-white p-4 shadow-sm">
        <h3 className="mb-3 text-sm font-semibold">Slice Analytics</h3>
        <div className="grid gap-4 xl:grid-cols-2">
          {SLICE_GROUPS.map((group) => (
            <SliceAnalyticsTable
              key={group.reportKey}
              title={`By ${group.title}`}
              rows={sliceRowsFromReport(report, trades, group.reportKey, group.fallback)}
              emptyText={`No ${group.title.toLowerCase()} slice data.`}
            />
          ))}
        </div>
      </section>

      <section className="mt-4 rounded-lg border border-border bg-white p-4 shadow-sm">
        <h3 className="mb-3 text-sm font-semibold">Wait Reason Distribution</h3>
        {waitRows.length ? (
          <>
            <WaitReasonChart rows={waitRows} />
            <div className="mt-4">
              <DataTable<WaitReasonRow>
                rows={waitRows}
                emptyText="No wait reason data."
                columns={[
                  { key: "reason", label: "Reason" },
                  { key: "count", label: "Count" },
                ]}
              />
            </div>
          </>
        ) : (
          <div className="rounded-lg border border-dashed border-border p-6 text-sm text-muted-foreground">
            No wait reason data.
          </div>
        )}
      </section>

      <section className="mt-4 rounded-lg border border-border bg-white p-4 shadow-sm">
        <h3 className="mb-3 text-sm font-semibold">Ablation Result</h3>
        <AblationResultTable rows={ablationRows} emptyText="No ablation results returned." />
      </section>
    </div>
  );
}
