import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { Trade } from "@/types";
import { formatNumber } from "@/lib/utils";

interface BacktestChartsProps {
  trades: Trade[];
}

export function EquityCurveChart({ trades }: BacktestChartsProps) {
  if (!trades.length) {
    return <div className="rounded-lg border border-dashed border-border p-6 text-muted-foreground">No trades to chart</div>;
  }

  let equity = 0;
  const data = trades.map((trade, index) => {
    equity += Number(trade.pnl || 0);
    return {
      index: index + 1,
      equity,
      closed_at: trade.closed_at,
    };
  });

  return (
    <section className="rounded-lg border border-border bg-white p-4">
      <h3 className="mb-4 text-sm font-semibold">Equity curve</h3>
      <div className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data}>
            <CartesianGrid stroke="#e5e7eb" vertical={false} />
            <XAxis dataKey="index" />
            <YAxis width={70} tickFormatter={(v) => formatNumber(Number(v), 0)} />
            <Tooltip formatter={(value) => formatNumber(Number(value), 2)} labelFormatter={(label) => `Trade ${label}`} />
            <Line type="monotone" dataKey="equity" stroke="#2563eb" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
