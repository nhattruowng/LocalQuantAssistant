import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Candle } from "@/types";
import { formatNumber } from "@/lib/utils";

interface MarketChartsProps {
  candles: Candle[];
}

function scale(value: number, min: number, max: number, height: number, padding = 16) {
  if (max === min) return height / 2;
  return padding + ((max - value) / (max - min)) * (height - padding * 2);
}

function CandlestickChart({ candles }: MarketChartsProps) {
  const width = 1000;
  const height = 360;
  const visible = candles.slice(-160);
  const highs = visible.map((item) => item.high);
  const lows = visible.map((item) => item.low);
  const min = Math.min(...lows);
  const max = Math.max(...highs);
  const step = width / Math.max(visible.length, 1);
  const bodyWidth = Math.max(2, Math.min(8, step * 0.55));

  const emaPath = (key: "ema_20" | "ema_50" | "ema_200") =>
    visible
      .map((item, index) => {
        const value = item[key];
        if (typeof value !== "number") return "";
        const x = index * step + step / 2;
        const y = scale(value, min, max, height);
        return `${index === 0 ? "M" : "L"}${x.toFixed(2)},${y.toFixed(2)}`;
      })
      .filter(Boolean)
      .join(" ");

  return (
    <div className="overflow-hidden rounded-lg border border-border bg-white p-4">
      <h3 className="mb-4 text-sm font-semibold">Candlestick with EMA overlays</h3>
      <svg viewBox={`0 0 ${width} ${height}`} className="h-96 w-full" role="img" aria-label="Candlestick chart">
        <rect width={width} height={height} fill="#ffffff" />
        {[0.2, 0.4, 0.6, 0.8].map((ratio) => (
          <line
            key={ratio}
            x1="0"
            x2={width}
            y1={height * ratio}
            y2={height * ratio}
            stroke="#e5e7eb"
            strokeWidth="1"
          />
        ))}
        {visible.map((item, index) => {
          const x = index * step + step / 2;
          const open = scale(item.open, min, max, height);
          const close = scale(item.close, min, max, height);
          const high = scale(item.high, min, max, height);
          const low = scale(item.low, min, max, height);
          const bullish = item.close >= item.open;
          const color = bullish ? "#16a34a" : "#dc2626";
          const top = Math.min(open, close);
          const bodyHeight = Math.max(1.5, Math.abs(close - open));
          return (
            <g key={`${item.timestamp}-${index}`}>
              <line x1={x} x2={x} y1={high} y2={low} stroke={color} strokeWidth="1.3" />
              <rect
                x={x - bodyWidth / 2}
                y={top}
                width={bodyWidth}
                height={bodyHeight}
                fill={bullish ? "#dcfce7" : "#fee2e2"}
                stroke={color}
                strokeWidth="1"
                rx="1"
              />
            </g>
          );
        })}
        <path d={emaPath("ema_20")} fill="none" stroke="#2563eb" strokeWidth="2" />
        <path d={emaPath("ema_50")} fill="none" stroke="#f97316" strokeWidth="2" />
        <path d={emaPath("ema_200")} fill="none" stroke="#7c3aed" strokeWidth="2" />
      </svg>
      <div className="mt-2 flex gap-4 text-xs text-muted-foreground">
        <span className="text-blue-700">EMA20</span>
        <span className="text-orange-600">EMA50</span>
        <span className="text-violet-700">EMA200</span>
      </div>
    </div>
  );
}

export function MarketCharts({ candles }: MarketChartsProps) {
  if (!candles.length) {
    return <div className="rounded-lg border border-dashed border-border p-6 text-muted-foreground">No data found</div>;
  }

  return (
    <div className="space-y-4">
      <CandlestickChart candles={candles} />
      <div className="grid gap-4 xl:grid-cols-2">
        <section className="rounded-lg border border-border bg-white p-4">
          <h3 className="mb-4 text-sm font-semibold">Volume</h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={candles}>
                <CartesianGrid stroke="#e5e7eb" vertical={false} />
                <XAxis dataKey="timestamp" hide />
                <YAxis width={70} />
                <Tooltip formatter={(value) => formatNumber(Number(value), 2)} />
                <Bar dataKey="volume" fill="#94a3b8" name="Volume" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>
        <section className="rounded-lg border border-border bg-white p-4">
          <h3 className="mb-4 text-sm font-semibold">RSI 14</h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={candles}>
                <CartesianGrid stroke="#e5e7eb" vertical={false} />
                <XAxis dataKey="timestamp" hide />
                <YAxis domain={[0, 100]} width={40} />
                <Tooltip formatter={(value) => formatNumber(Number(value), 2)} />
                <Area type="monotone" dataKey="rsi_14" fill="#ccfbf1" stroke="#0f766e" name="RSI" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </section>
      </div>
    </div>
  );
}
