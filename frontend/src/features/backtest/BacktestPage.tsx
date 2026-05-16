import { BarChart3 } from "lucide-react";
import { MetricCard } from "@/components/cards/MetricCard";
import { EquityCurveChart } from "@/components/charts/BacktestCharts";
import { Button } from "@/components/forms/Button";
import { PageHeader } from "@/components/layout/PageHeader";
import { DataTable } from "@/components/tables/DataTable";
import { useActions } from "@/hooks/useApiQueries";
import { useSessionStore } from "@/hooks/useSessionStore";
import { formatNumber, formatPercent } from "@/lib/utils";
import type { BacktestReport, Trade } from "@/types";

function selectReport(report?: BacktestReport | null) {
  return report ?? null;
}

export function BacktestPage() {
  const actions = useActions();
  const { latestBacktest, setLatestBacktest } = useSessionStore();
  const report = selectReport(latestBacktest?.ml_enhanced ?? latestBacktest?.rule_only);
  const trades = report?.trades ?? [];

  const run = async () => {
    const result = await actions.runBacktest.mutateAsync();
    setLatestBacktest(result);
  };

  return (
    <div>
      <PageHeader
        title="Backtest"
        description="Run historical simulation with fees, slippage, drawdown, and trade history."
        actions={
          <Button onClick={run} disabled={actions.runBacktest.isPending}>
            <BarChart3 className="h-4 w-4" />
            Run Backtest
          </Button>
        }
      />
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
        <DataTable<Trade>
          rows={trades}
          emptyText="No backtest report. Run a backtest first."
          columns={[
            { key: "opened_at", label: "Opened" },
            { key: "closed_at", label: "Closed" },
            { key: "direction", label: "Direction" },
            { key: "strategy", label: "Strategy" },
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
