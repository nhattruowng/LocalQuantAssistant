import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Trade } from "@/types";
import { formatNumber } from "@/lib/utils";

interface BacktestChartsProps {
  trades: Trade[];
}

function equitySeries(trades: Trade[]) {
  let equity = 0;
  let peak = 0;
  return trades.map((trade, index) => {
    equity += Number(trade.pnl || 0);
    peak = Math.max(peak, equity);
    const drawdown = peak - equity;
    return {
      index: index + 1,
      equity,
      drawdown,
      closed_at: trade.closed_at,
    };
  });
}

function monthlyReturnSeries(trades: Trade[]) {
  const byMonth: Record<string, number> = {};
  for (const trade of trades) {
    const stamp = new Date(trade.closed_at);
    if (Number.isNaN(stamp.getTime())) continue;
    const key = `${stamp.getFullYear()}-${String(stamp.getMonth() + 1).padStart(2, "0")}`;
    byMonth[key] = (byMonth[key] ?? 0) + Number(trade.pnl || 0);
  }
  return Object.entries(byMonth)
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([month, pnl]) => ({ month, pnl }));
}

function EmptyChart({ label }: { label: string }) {
  return <div className="rounded-lg border border-dashed border-border p-6 text-muted-foreground">{label}</div>;
}

export function EquityCurveChart({ trades }: BacktestChartsProps) {
  if (!trades.length) {
    return <EmptyChart label="No trades to chart equity." />;
  }
  const data = equitySeries(trades);
  return (
    <section className="rounded-lg border border-border bg-white p-4">
      <h3 className="mb-4 text-sm font-semibold">Equity Curve</h3>
      <div className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data}>
            <CartesianGrid stroke="#e5e7eb" vertical={false} />
            <XAxis dataKey="index" />
            <YAxis width={70} tickFormatter={(value) => formatNumber(Number(value), 0)} />
            <Tooltip formatter={(value) => formatNumber(Number(value), 2)} labelFormatter={(label) => `Trade ${label}`} />
            <Line type="monotone" dataKey="equity" stroke="#2563eb" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}

export function DrawdownCurveChart({ trades }: BacktestChartsProps) {
  if (!trades.length) {
    return <EmptyChart label="No trades to chart drawdown." />;
  }
  const data = equitySeries(trades);
  return (
    <section className="rounded-lg border border-border bg-white p-4">
      <h3 className="mb-4 text-sm font-semibold">Drawdown Curve</h3>
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data}>
            <CartesianGrid stroke="#e5e7eb" vertical={false} />
            <XAxis dataKey="index" />
            <YAxis width={70} tickFormatter={(value) => formatNumber(Number(value), 0)} />
            <Tooltip formatter={(value) => formatNumber(Number(value), 2)} labelFormatter={(label) => `Trade ${label}`} />
            <Line type="monotone" dataKey="drawdown" stroke="#dc2626" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}

export function MonthlyReturnsChart({ trades }: BacktestChartsProps) {
  const data = monthlyReturnSeries(trades);
  if (!data.length) {
    return <EmptyChart label="No monthly return data." />;
  }
  return (
    <section className="rounded-lg border border-border bg-white p-4">
      <h3 className="mb-4 text-sm font-semibold">Monthly Returns</h3>
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data}>
            <CartesianGrid stroke="#e5e7eb" vertical={false} />
            <XAxis dataKey="month" />
            <YAxis width={70} tickFormatter={(value) => formatNumber(Number(value), 0)} />
            <Tooltip formatter={(value) => formatNumber(Number(value), 2)} />
            <Bar dataKey="pnl" fill="#0f766e" />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
