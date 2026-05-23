import { AlertTriangle } from "lucide-react";
import { MetricCard } from "@/components/cards/MetricCard";
import type { RiskStatus } from "@/types";
import { formatNumber, formatPercent, shortDate } from "@/lib/utils";

export function RiskStatusCard({ status }: { status?: RiskStatus | null }) {
  const blocked = String(status?.state ?? "").toUpperCase() === "BLOCKED" || String(status?.state ?? "").toUpperCase() === "COOLDOWN";
  const reason = status?.reasons?.[0] ?? "Risk guard is active.";

  return (
    <section className="rounded-lg border border-border bg-white p-4 shadow-sm">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h3 className="text-sm font-semibold">Risk Status</h3>
        <span className="rounded-full bg-muted px-3 py-1 text-xs text-muted-foreground">{status?.state ?? "-"}</span>
      </div>
      {blocked ? (
        <div className="mb-4 flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <p>{reason}</p>
        </div>
      ) : null}
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <MetricCard label="Daily Drawdown" value={formatPercent(status?.daily_drawdown_pct)} />
        <MetricCard label="Weekly Drawdown" value={formatPercent(status?.weekly_drawdown_pct)} />
        <MetricCard label="Max Consecutive Losses" value={formatNumber(status?.max_consecutive_losses ?? status?.consecutive_losses ?? 0, 0)} />
        <MetricCard label="Trades Today" value={formatNumber(status?.trades_today ?? status?.daily_trade_count ?? 0, 0)} />
        <MetricCard label="Current Exposure" value={formatNumber(status?.current_exposure ?? null, 2)} />
        <MetricCard label="Last Blocked At" value={shortDate(status?.last_blocked_at ?? undefined)} />
      </div>
    </section>
  );
}
