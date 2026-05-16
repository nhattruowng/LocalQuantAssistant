import { MetricCard } from "@/components/cards/MetricCard";
import { MarketCharts } from "@/components/charts/MarketCharts";
import { PageHeader } from "@/components/layout/PageHeader";
import { useCandlesQuery } from "@/hooks/useApiQueries";
import { formatNumber } from "@/lib/utils";

export function MarketPage() {
  const candles = useCandlesQuery(500);
  const latest = candles.data?.at(-1);

  return (
    <div>
      <PageHeader title="Market" description="OHLCV chart, indicator overlays, volume, RSI, and current regime." />
      <div className="mb-4 grid gap-4 md:grid-cols-4">
        <MetricCard label="Close" value={formatNumber(latest?.close, 4)} />
        <MetricCard label="High" value={formatNumber(latest?.high, 4)} />
        <MetricCard label="Low" value={formatNumber(latest?.low, 4)} />
        <MetricCard label="Regime" value={latest?.market_regime ?? "-"} />
      </div>
      {candles.isLoading ? <p className="text-muted-foreground">Loading market data...</p> : null}
      {candles.isError ? <p className="text-red-600">No data found</p> : null}
      <MarketCharts candles={candles.data ?? []} />
    </div>
  );
}
