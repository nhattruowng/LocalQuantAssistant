import { BarChart3 } from "lucide-react";
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
import { formatNumber, formatPercent } from "@/lib/utils";
import type { BacktestReport, BacktestResponse, Trade } from "@/types";

type AnalyticsRow = {
  key: string;
  total_trades: number;
  winrate: number;
  net_profit: number;
  profit_factor: number;
  expectancy: number;
};

type ScenarioRow = {
  scenario: string;
  total_trades: number;
  winrate: number;
  net_profit: number;
  max_drawdown: number;
};

function pickReport(payload?: BacktestResponse | null): BacktestReport | null {
  return payload?.ml_enhanced ?? payload?.rule_only ?? null;
}

function aggregateBy(trades: Trade[], key: keyof Trade): AnalyticsRow[] {
  const grouped = new Map<string, Trade[]>();
  for (const trade of trades) {
    const label = String(trade[key] ?? "UNKNOWN");
    const bucket = grouped.get(label) ?? [];
    bucket.push(trade);
    grouped.set(label, bucket);
  }
  return [...grouped.entries()]
    .map(([label, bucket]) => {
      const totalTrades = bucket.length;
      const wins = bucket.filter((item) => item.pnl > 0).length;
      const netProfit = bucket.reduce((sum, item) => sum + Number(item.pnl || 0), 0);
      const grossProfit = bucket.filter((item) => item.pnl > 0).reduce((sum, item) => sum + Number(item.pnl || 0), 0);
      const grossLoss = Math.abs(bucket.filter((item) => item.pnl < 0).reduce((sum, item) => sum + Number(item.pnl || 0), 0));
      return {
        key: label,
        total_trades: totalTrades,
        winrate: totalTrades ? wins / totalTrades : 0,
        net_profit: netProfit,
        profit_factor: grossLoss > 0 ? grossProfit / grossLoss : grossProfit > 0 ? Number.POSITIVE_INFINITY : 0,
        expectancy: totalTrades ? netProfit / totalTrades : 0,
      };
    })
    .sort((left, right) => right.net_profit - left.net_profit);
}

function waitDistribution(trades: Trade[]) {
  const counts: Record<string, number> = {};
  for (const trade of trades) {
    const key = String(trade.wait_reason ?? "NONE");
    counts[key] = (counts[key] ?? 0) + 1;
  }
  return Object.entries(counts)
    .map(([reason, count]) => ({ reason, count }))
    .sort((left, right) => right.count - left.count);
}

function scenarioRows(payload?: BacktestResponse | null): ScenarioRow[] {
  if (!payload) return [];
  return Object.entries(payload)
    .filter(([, value]) => Boolean(value))
    .map(([scenario, value]) => {
      const report = value as BacktestReport;
      return {
        scenario,
        total_trades: report.total_trades ?? 0,
        winrate: report.winrate ?? 0,
        net_profit: report.net_profit ?? 0,
        max_drawdown: report.max_drawdown ?? 0,
      };
    })
    .sort((left, right) => right.net_profit - left.net_profit);
}

function groupedOrFallback(
  report: BacktestReport | null,
  trades: Trade[],
  groupedKey: string,
  fallbackKey: keyof Trade,
) {
  const grouped = report?.grouped?.[groupedKey];
  if (grouped && typeof grouped === "object") {
    return Object.entries(grouped).map(([key, value]) => ({
      key,
      total_trades: Number(value.total_trades ?? 0),
      winrate: Number(value.winrate ?? 0),
      net_profit: Number(value.net_profit ?? 0),
      profit_factor: Number(value.profit_factor ?? 0),
      expectancy: Number(value.expectancy ?? 0),
    }));
  }
  return aggregateBy(trades, fallbackKey);
}

export function BacktestPage() {
  const actions = useActions();
  const { latestBacktest, setLatestBacktest } = useSessionStore();
  const report = pickReport(latestBacktest);
  const trades = report?.trades ?? [];
  const regimeRows = groupedOrFallback(report, trades, "by_market_regime", "market_regime");
  const strategyRows = groupedOrFallback(report, trades, "by_strategy", "strategy");
  const setupTypeRows = aggregateBy(trades, "setup_type");
  const waitRows = waitDistribution(trades);
  const ablationRows = scenarioRows(latestBacktest);

  const run = async () => {
    const result = await actions.runBacktest.mutateAsync();
    setLatestBacktest(result);
  };

  return (
    <div>
      <PageHeader
        title="Backtest"
        description="Backtest analytics for debug and research across regimes, setups, and scenarios."
        actions={(
          <Button onClick={run} disabled={actions.runBacktest.isPending}>
            <BarChart3 className="h-4 w-4" />
            {actions.runBacktest.isPending ? "Running..." : "Run Backtest"}
          </Button>
        )}
      />
      {actions.runBacktest.isError ? (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          Backtest failed. Please verify data/model setup and retry.
        </div>
      ) : null}
      <div className="mb-4 grid gap-4 md:grid-cols-3 xl:grid-cols-6">
        <MetricCard label="Total Trades" value={report?.total_trades ?? "-"} />
        <MetricCard label="Winrate" value={formatPercent(report?.winrate)} />
        <MetricCard label="Net Profit" value={formatNumber(report?.net_profit, 2)} />
        <MetricCard label="Profit Factor" value={formatNumber(report?.profit_factor, 2)} />
        <MetricCard label="Max Drawdown" value={formatNumber(report?.max_drawdown, 2)} />
        <MetricCard label="Expectancy" value={formatNumber(report?.expectancy, 2)} />
      </div>
      <div className="space-y-4">
        <EquityCurveChart trades={trades} />
        <DrawdownCurveChart trades={trades} />
        <MonthlyReturnsChart trades={trades} />
        <section className="rounded-lg border border-border bg-white p-4">
          <h3 className="mb-3 text-sm font-semibold">Performance by Regime</h3>
          <DataTable<AnalyticsRow>
            rows={regimeRows}
            emptyText="No regime analytics."
            columns={[
              { key: "key", label: "Regime" },
              { key: "total_trades", label: "Trades" },
              { key: "winrate", label: "Winrate", render: (value) => formatPercent(Number(value)) },
              { key: "net_profit", label: "Net PnL", render: (value) => formatNumber(Number(value), 2) },
              { key: "profit_factor", label: "PF", render: (value) => formatNumber(Number(value), 2) },
            ]}
          />
        </section>
        <section className="rounded-lg border border-border bg-white p-4">
          <h3 className="mb-3 text-sm font-semibold">Performance by Strategy</h3>
          <DataTable<AnalyticsRow>
            rows={strategyRows}
            emptyText="No strategy analytics."
            columns={[
              { key: "key", label: "Strategy" },
              { key: "total_trades", label: "Trades" },
              { key: "winrate", label: "Winrate", render: (value) => formatPercent(Number(value)) },
              { key: "net_profit", label: "Net PnL", render: (value) => formatNumber(Number(value), 2) },
              { key: "expectancy", label: "Expectancy", render: (value) => formatNumber(Number(value), 2) },
            ]}
          />
        </section>
        <section className="rounded-lg border border-border bg-white p-4">
          <h3 className="mb-3 text-sm font-semibold">Performance by Setup Type</h3>
          <DataTable<AnalyticsRow>
            rows={setupTypeRows}
            emptyText="No setup-type analytics."
            columns={[
              { key: "key", label: "Setup Type" },
              { key: "total_trades", label: "Trades" },
              { key: "winrate", label: "Winrate", render: (value) => formatPercent(Number(value)) },
              { key: "net_profit", label: "Net PnL", render: (value) => formatNumber(Number(value), 2) },
              { key: "profit_factor", label: "PF", render: (value) => formatNumber(Number(value), 2) },
            ]}
          />
        </section>
        <section className="rounded-lg border border-border bg-white p-4">
          <h3 className="mb-3 text-sm font-semibold">WAIT Reason Distribution</h3>
          <DataTable<{ reason: string; count: number }>
            rows={waitRows}
            emptyText="No wait reason distribution."
            columns={[
              { key: "reason", label: "Wait Reason" },
              { key: "count", label: "Count" },
            ]}
          />
        </section>
        <section className="rounded-lg border border-border bg-white p-4">
          <h3 className="mb-3 text-sm font-semibold">Ablation / Scenario Results</h3>
          <DataTable<ScenarioRow>
            rows={ablationRows}
            emptyText="No scenario comparison returned."
            columns={[
              { key: "scenario", label: "Scenario" },
              { key: "total_trades", label: "Trades" },
              { key: "winrate", label: "Winrate", render: (value) => formatPercent(Number(value)) },
              { key: "net_profit", label: "Net PnL", render: (value) => formatNumber(Number(value), 2) },
              { key: "max_drawdown", label: "Max DD", render: (value) => formatNumber(Number(value), 2) },
            ]}
          />
        </section>
        <DataTable<Trade>
          rows={trades}
          emptyText="No backtest report. Run a backtest first."
          columns={[
            { key: "opened_at", label: "Opened" },
            { key: "closed_at", label: "Closed" },
            { key: "direction", label: "Direction" },
            { key: "strategy", label: "Strategy" },
            { key: "setup_type", label: "Setup Type" },
            { key: "entry", label: "Entry", render: (value) => formatNumber(Number(value), 4) },
            { key: "exit_price", label: "Exit", render: (value) => formatNumber(Number(value), 4) },
            { key: "pnl", label: "PnL", render: (value) => formatNumber(Number(value), 2) },
            { key: "result", label: "Result" },
          ]}
        />
      </div>
    </div>
  );
}
