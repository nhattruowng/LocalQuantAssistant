import { DataTable } from "@/components/tables/DataTable";
import { cn, formatNumber, formatPercent } from "@/lib/utils";

export interface AblationResultRow {
  module_enabled: string;
  net_profit: number;
  profit_factor: number;
  max_drawdown: number;
  winrate: number;
  expectancy: number;
  trade_count: number;
  delta_vs_baseline: number;
}

export function AblationResultTable({ rows, emptyText }: { rows: AblationResultRow[]; emptyText: string }) {
  return (
    <DataTable<AblationResultRow>
      rows={rows}
      emptyText={emptyText}
      columns={[
        { key: "module_enabled", label: "Module Enabled" },
        { key: "net_profit", label: "Net Profit", render: (value) => formatNumber(Number(value), 2) },
        { key: "profit_factor", label: "Profit Factor", render: (value) => formatNumber(Number(value), 2) },
        { key: "max_drawdown", label: "Max Drawdown", render: (value) => formatNumber(Number(value), 2) },
        { key: "winrate", label: "Winrate", render: (value) => formatPercent(Number(value)) },
        { key: "expectancy", label: "Expectancy", render: (value) => formatNumber(Number(value), 2) },
        { key: "trade_count", label: "Trade Count" },
        {
          key: "delta_vs_baseline",
          label: "Delta vs Baseline",
          render: (value) => <span className={cn(Number(value) >= 0 ? "text-emerald-700" : "text-red-700")}>{formatNumber(Number(value), 2)}</span>,
        },
      ]}
    />
  );
}
