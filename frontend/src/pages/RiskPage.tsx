import { RefreshCw } from "lucide-react";
import { Button } from "@/components/forms/Button";
import { PageHeader } from "@/components/layout/PageHeader";
import { PaperTradingAnalytics } from "@/components/risk/PaperTradingAnalytics";
import { RiskEventsTable } from "@/components/risk/RiskEventsTable";
import { RiskStatusCard } from "@/components/risk/RiskStatusCard";
import { useLatestBacktestQuery, useRiskStatusQuery } from "@/hooks/useApiQueries";
import { useSessionStore } from "@/hooks/useSessionStore";
import type { BacktestReport, BacktestResponse } from "@/types";

function pickReport(payload?: BacktestResponse | null): BacktestReport | null {
  return payload?.ml_enhanced ?? payload?.rule_only ?? null;
}

export function RiskPage() {
  const riskQuery = useRiskStatusQuery();
  const latestBacktestQuery = useLatestBacktestQuery();
  const sessionBacktest = useSessionStore((state) => state.latestBacktest);
  const latestBacktest = latestBacktestQuery.data ?? sessionBacktest;
  const report = pickReport(latestBacktest);

  return (
    <div>
      <PageHeader
        title="Risk Research Dashboard"
        description="Monitor RiskGuard state, drawdown, exposure, and paper-trading diagnostics."
        actions={
          <Button onClick={() => riskQuery.refetch()} disabled={riskQuery.isFetching || latestBacktestQuery.isFetching}>
            <RefreshCw className={`h-4 w-4 ${riskQuery.isFetching || latestBacktestQuery.isFetching ? "animate-spin" : ""}`} />
            Refresh
          </Button>
        }
      />

      <RiskStatusCard status={riskQuery.data} />

      <section className="mt-4 rounded-lg border border-border bg-white p-4 shadow-sm">
        <h3 className="mb-3 text-sm font-semibold">Paper Trading Analytics</h3>
        {report ? (
          <PaperTradingAnalytics report={report} />
        ) : (
          <div className="rounded-lg border border-dashed border-border p-6 text-sm text-muted-foreground">
            No paper trading analytics available yet.
          </div>
        )}
      </section>

      <section className="mt-4 rounded-lg border border-border bg-white p-4 shadow-sm">
        <h3 className="mb-3 text-sm font-semibold">Risk Events</h3>
        <RiskEventsTable events={riskQuery.data?.events} />
      </section>
    </div>
  );
}
