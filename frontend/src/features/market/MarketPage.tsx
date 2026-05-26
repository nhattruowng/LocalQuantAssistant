import { MetricCard } from "@/components/cards/MetricCard";
import { MarketCharts } from "@/components/charts/MarketCharts";
import { PageHeader } from "@/components/layout/PageHeader";
import { MarketPresetSelector } from "@/components/market/MarketPresetSelector";
import { MARKET_UNAVAILABLE_MESSAGE } from "@/constants/marketPresets";
import { useAppSettings } from "@/hooks/useAppSettings";
import { useCandlesQuery } from "@/hooks/useApiQueries";
import { formatNumber } from "@/lib/utils";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const REGIME_ORDER = ["UPTREND", "SIDEWAY", "DOWNTREND", "BREAKOUT"];

const REGIME_COLORS: Record<string, string> = {
  UPTREND: "#16a34a",
  SIDEWAY: "#64748b",
  DOWNTREND: "#dc2626",
  BREAKOUT: "#2563eb",
  UNKNOWN: "#a1a1aa",
};

function normalizeRegime(raw?: string): string {
  if (!raw) return "UNKNOWN";
  const key = raw.trim().toUpperCase();
  if (REGIME_ORDER.includes(key)) return key;
  return key || "UNKNOWN";
}

function buildTransitionMatrix(regimes: string[]) {
  const labels = Array.from(new Set([...REGIME_ORDER, ...regimes.filter(Boolean)]));
  const matrix = labels.map((from) => {
    const counts: Record<string, number> = {};
    labels.forEach((to) => {
      counts[to] = 0;
    });
    return { from, counts };
  });
  const rowMap = new Map(matrix.map((row) => [row.from, row.counts]));

  for (let index = 1; index < regimes.length; index += 1) {
    const from = regimes[index - 1];
    const to = regimes[index];
    if (!from || !to) continue;
    const counts = rowMap.get(from);
    if (!counts) continue;
    counts[to] = (counts[to] ?? 0) + 1;
  }

  return { labels, matrix };
}

export function MarketPage() {
  const { symbol, timeframe, setSymbol, setTimeframe } = useAppSettings();
  const candles = useCandlesQuery(500);
  const latest = candles.data?.at(-1);
  const timeline = (candles.data ?? []).slice(-160).map((item, index) => {
    const regime = normalizeRegime(item.market_regime);
    const level = REGIME_ORDER.indexOf(regime);
    return {
      index,
      timestamp: item.timestamp,
      regime,
      level: level >= 0 ? level : REGIME_ORDER.length,
    };
  });
  const regimes = timeline.map((item) => item.regime);
  const transition = buildTransitionMatrix(regimes);

  return (
    <div>
      <PageHeader title="Market" description="OHLCV chart, indicator overlays, volume, RSI, and current regime." />
      <MarketPresetSelector
        selectedSymbol={symbol}
        selectedTimeframe={timeframe}
        onSelect={(payload) => {
          setSymbol(payload.symbol);
          setTimeframe(payload.timeframe);
        }}
        className="mb-4"
      />
      <div className="mb-4 grid gap-4 md:grid-cols-4">
        <MetricCard label="Close" value={formatNumber(latest?.close, 4)} />
        <MetricCard label="High" value={formatNumber(latest?.high, 4)} />
        <MetricCard label="Low" value={formatNumber(latest?.low, 4)} />
        <MetricCard label="Regime" value={latest?.market_regime ?? "-"} />
      </div>
      {candles.isLoading ? <p className="text-muted-foreground">Loading market data...</p> : null}
      {candles.isError ? <p className="text-red-600">{MARKET_UNAVAILABLE_MESSAGE}</p> : null}
      <MarketCharts candles={candles.data ?? []} />
      <div className="mt-4 grid gap-4 xl:grid-cols-2">
        <section className="rounded-lg border border-border bg-white p-4">
          <h3 className="mb-4 text-sm font-semibold">Regime Timeline</h3>
          {!timeline.length ? (
            <p className="text-sm text-muted-foreground">No regime timeline available.</p>
          ) : (
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={timeline}>
                  <CartesianGrid stroke="#e5e7eb" />
                  <XAxis dataKey="index" tick={{ fontSize: 11 }} />
                  <YAxis
                    type="number"
                    domain={[0, REGIME_ORDER.length]}
                    tickFormatter={(value) => REGIME_ORDER[value] ?? "UNKNOWN"}
                    tick={{ fontSize: 11 }}
                    width={90}
                  />
                  <Tooltip
                    formatter={(_, __, context) => context?.payload?.regime ?? "UNKNOWN"}
                    labelFormatter={(value) => `Bar ${value}`}
                  />
                  <Line type="stepAfter" dataKey="level" stroke="#0f172a" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
          {timeline.length ? (
            <div className="mt-3 flex flex-wrap gap-2 text-xs">
              {REGIME_ORDER.map((regime) => (
                <span
                  key={regime}
                  className="rounded px-2 py-1 text-white"
                  style={{ backgroundColor: REGIME_COLORS[regime] ?? REGIME_COLORS.UNKNOWN }}
                >
                  {regime}
                </span>
              ))}
            </div>
          ) : null}
        </section>
        <section className="rounded-lg border border-border bg-white p-4">
          <h3 className="mb-4 text-sm font-semibold">Regime Transition Matrix</h3>
          {!transition.matrix.length ? (
            <p className="text-sm text-muted-foreground">No transition data available.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-xs uppercase text-muted-foreground">
                    <th className="py-2 pr-3">From \ To</th>
                    {transition.labels.map((to) => (
                      <th key={to} className="py-2 pr-3">
                        {to}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {transition.matrix.map((row) => (
                    <tr key={row.from} className="border-b border-border/60">
                      <td className="py-2 pr-3 font-medium">{row.from}</td>
                      {transition.labels.map((to) => (
                        <td key={`${row.from}-${to}`} className="py-2 pr-3">
                          <span
                            className="inline-flex min-w-8 items-center justify-center rounded px-2 py-0.5 text-xs"
                            style={{
                              backgroundColor:
                                (row.counts[to] ?? 0) > 0
                                  ? `${REGIME_COLORS[to] ?? REGIME_COLORS.UNKNOWN}20`
                                  : "transparent",
                              color: (row.counts[to] ?? 0) > 0 ? "#0f172a" : "#94a3b8",
                            }}
                          >
                            {row.counts[to] ?? 0}
                          </span>
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
