import { Activity, BarChart3, Database, Gauge } from "lucide-react";
import { Button } from "@/components/forms/Button";
import { MetricCard } from "@/components/cards/MetricCard";
import { SignalCard } from "@/components/cards/SignalCard";
import { PageHeader } from "@/components/layout/PageHeader";
import { useActions, useCandlesQuery, useRiskStatusQuery } from "@/hooks/useApiQueries";
import { useSessionStore } from "@/hooks/useSessionStore";
import { formatNumber, formatPercent } from "@/lib/utils";
import type { TradeSetup } from "@/types";

interface DashboardPageProps {
  latestSignal?: TradeSetup | null;
  latestBacktestNetProfit?: number | null;
  onSignalGenerated: (setup: TradeSetup) => void;
  onBacktestRun: () => void;
}

export function DashboardPage({
  latestSignal,
  latestBacktestNetProfit,
  onSignalGenerated,
  onBacktestRun,
}: DashboardPageProps) {
  const candles = useCandlesQuery(200);
  const riskStatus = useRiskStatusQuery();
  const actions = useActions();
  const { setLatestBacktest } = useSessionStore();
  const latestCandle = candles.data?.at(-1);

  const generate = async () => {
    const setup = await actions.generateSignal.mutateAsync(undefined);
    onSignalGenerated(setup);
  };

  const runBacktest = async () => {
    const report = await actions.runBacktest.mutateAsync();
    setLatestBacktest(report);
    onBacktestRun();
  };

  return (
    <div>
      <PageHeader
        title="Dashboard"
        description="Market snapshot, current setup, and quick workflow actions."
        actions={
          <>
            <Button onClick={() => actions.updateData.mutate()} disabled={actions.updateData.isPending}>
              <Database className="h-4 w-4" />
              Update Data
            </Button>
            <Button onClick={generate} disabled={actions.generateSignal.isPending}>
              <Activity className="h-4 w-4" />
              Generate Signal
            </Button>
            <Button onClick={runBacktest} disabled={actions.runBacktest.isPending}>
              <BarChart3 className="h-4 w-4" />
              Run Backtest
            </Button>
          </>
        }
      />
      <div className="grid gap-4 xl:grid-cols-[380px_1fr]">
        <SignalCard setup={latestSignal} />
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <MetricCard label="Latest Price" value={formatNumber(latestCandle?.close, 4)} />
          <MetricCard label="Market Regime" value={latestSignal?.market_regime ?? latestCandle?.market_regime ?? "-"} />
          <MetricCard label="Confidence" value={formatPercent(latestSignal?.confidence)} />
          <MetricCard label="Risk/Reward" value={formatNumber(latestSignal?.risk_reward, 2)} />
          <MetricCard label="Rows Loaded" value={candles.data?.length ?? 0} />
          <MetricCard label="Volume" value={formatNumber(latestCandle?.volume, 2)} />
          <MetricCard label="RSI 14" value={formatNumber(latestCandle?.rsi_14, 2)} />
          <MetricCard
            label="Backtest Net"
            value={formatNumber(latestBacktestNetProfit, 2)}
            helper={<span className="inline-flex items-center gap-1"><Gauge className="h-3 w-3" /> Latest run</span>}
          />
        </div>
      </div>
      <section className="mt-4 rounded-lg border border-border bg-white p-4">
        <div className="grid gap-4 md:grid-cols-4">
          <MetricCard label="Circuit Breaker" value={riskStatus.data?.state ?? "-"} />
          <MetricCard label="Open Positions" value={riskStatus.data?.open_positions ?? "-"} />
          <MetricCard label="Daily Trades" value={riskStatus.data?.daily_trade_count ?? "-"} />
          <MetricCard label="Daily DD" value={formatPercent(riskStatus.data?.daily_drawdown_pct)} />
        </div>
        {riskStatus.data?.state === "BLOCKED" || riskStatus.data?.state === "COOLDOWN" ? (
          <p className="mt-3 text-sm font-medium text-red-600">
            {riskStatus.data.reasons?.[0] ?? "Risk guard is blocking new signals."}
          </p>
        ) : null}
      </section>
      {candles.isError ? <p className="mt-4 text-sm text-red-600">No data found or backend request failed.</p> : null}
    </div>
  );
}
