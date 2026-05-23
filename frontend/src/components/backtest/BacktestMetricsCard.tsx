import { MetricCard } from "@/components/cards/MetricCard";
import type { BacktestReport } from "@/types";
import { formatNumber, formatPercent } from "@/lib/utils";

export function BacktestMetricsCard({ report }: { report?: BacktestReport | null }) {
  return (
    <section className="rounded-lg border border-border bg-white p-4 shadow-sm">
      <h3 className="mb-3 text-sm font-semibold">Overall Metrics</h3>
      <div className="grid gap-4 md:grid-cols-3 xl:grid-cols-4">
        <MetricCard label="Total Trades" value={report?.total_trades ?? "-"} />
        <MetricCard label="Winrate" value={formatPercent(report?.winrate)} />
        <MetricCard label="Net Profit" value={formatNumber(report?.net_profit, 2)} />
        <MetricCard label="Profit Factor" value={formatNumber(report?.profit_factor ?? null, 2)} />
        <MetricCard label="Max Drawdown" value={formatNumber(report?.max_drawdown, 2)} />
        <MetricCard label="Expectancy" value={formatNumber(report?.expectancy, 2)} />
        <MetricCard label="Avg R Multiple" value={formatNumber(report?.avg_r_multiple ?? null, 2)} />
        <MetricCard label="Best Trade" value={formatNumber(report?.best_trade ?? null, 2)} />
        <MetricCard label="Worst Trade" value={formatNumber(report?.worst_trade ?? null, 2)} />
      </div>
    </section>
  );
}
