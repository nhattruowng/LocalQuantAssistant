import { DataTable } from "@/components/tables/DataTable";
import { formatNumber, formatPercent } from "@/lib/utils";

export interface SliceAnalyticsRow {
  key: string;
  total_trades: number;
  winrate: number;
  net_profit: number;
  profit_factor: number;
  expectancy: number;
}

export function SliceAnalyticsTable({ title, rows, emptyText }: { title: string; rows: SliceAnalyticsRow[]; emptyText: string }) {
  return (
    <section className="rounded-lg border border-border bg-white p-4 shadow-sm">
      <h3 className="mb-3 text-sm font-semibold">{title}</h3>
      <DataTable<SliceAnalyticsRow>
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
    </section>
  );
}
