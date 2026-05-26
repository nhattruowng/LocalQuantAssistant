import { AlertTriangle, Compass } from "lucide-react";
import { resolveSignalIntelligence } from "@/components/reasoning/signalIntelligence";
import type { TradeSetup } from "@/types";

export function MarketContextCard({ setup }: { setup?: TradeSetup | null }) {
  const snapshot = resolveSignalIntelligence(setup);

  return (
    <section className="rounded-2xl border border-border bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-muted-foreground">
            <Compass className="h-4 w-4" />
            <p className="text-xs font-semibold uppercase tracking-wide">Market Context</p>
          </div>
          <h3 className="mt-2 text-xl font-semibold text-foreground">
            {snapshot.symbol} · {snapshot.timeframe}
          </h3>
        </div>
        {snapshot.transitionWarning ? (
          <span className="inline-flex items-center gap-1 rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-800">
            <AlertTriangle className="h-3.5 w-3.5" />
            Transition warning
          </span>
        ) : null}
      </div>

      <div className="mt-5 grid gap-3 sm:grid-cols-2">
        <ContextMetric label="Current Regime" value={snapshot.currentRegime} />
        <ContextMetric label="Volatility Level" value={snapshot.volatilityLevel} />
        <ContextMetric label="MTF Alignment" value={snapshot.mtfAlignment} />
        <ContextMetric label="Transition Warning" value={snapshot.transitionWarning ? "Yes" : "No"} />
      </div>
    </section>
  );
}

function ContextMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-border bg-muted/40 p-3">
      <p className="text-[11px] uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="mt-1 break-words text-sm font-semibold text-foreground">{value || "-"}</p>
    </div>
  );
}
