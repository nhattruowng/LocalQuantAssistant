import type { TradeSetup } from "@/types";
import { cn, formatPercent, signalClass } from "@/lib/utils";

interface SignalCardProps {
  setup?: TradeSetup | null;
}

export function SignalCard({ setup }: SignalCardProps) {
  if (!setup) {
    return (
      <section className="rounded-lg border border-dashed border-border bg-card p-6 text-muted-foreground">
        No signal generated
      </section>
    );
  }

  return (
    <section className={cn("rounded-lg border p-5 shadow-sm", signalClass(setup.signal))}>
      <p className="text-sm font-medium opacity-80">Current Signal</p>
      <div className="mt-2 text-5xl font-bold tracking-normal">{setup.signal}</div>
      <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
        <span>Confidence</span>
        <strong>{formatPercent(setup.confidence)}</strong>
        <span>Regime</span>
        <strong>{setup.market_regime ?? "-"}</strong>
        <span>Strategy</span>
        <strong>{setup.strategy ?? "-"}</strong>
        <span>Probability</span>
        <strong>{setup.probability_source ?? "raw"}</strong>
        <span>Model</span>
        <strong>{setup.model_scope_used ? `${setup.model_scope_used} ${setup.model_version ?? ""}` : "-"}</strong>
      </div>
    </section>
  );
}
