import type { TradeSetup } from "@/types";
import { cn, formatNumber, formatPercent, signalClass } from "@/lib/utils";
import { resolveReasoning } from "@/components/reasoning/ReasoningPanels";

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

  const reasoning = resolveReasoning(setup);
  const setupType = reasoning?.setup_type ?? setup.setup_type ?? setup.strategy ?? "-";
  const confluence = reasoning?.confluence_score ?? setup.confluence_score ?? null;
  const conflictLevel = reasoning?.conflict_level ?? setup.conflict_level ?? "-";
  const waitReason = setup.signal === "WAIT" ? reasoning?.wait_reason ?? setup.wait_reason ?? "-" : "-";
  const sizeMultiplier = reasoning?.position_size_multiplier ?? setup.position_size_multiplier ?? setup.size_multiplier ?? null;

  return (
    <section className={cn("rounded-xl border p-5 shadow-sm", signalClass(setup.signal))}>
      <p className="text-sm font-medium opacity-80">Current Decision</p>
      <div className="mt-2 flex flex-wrap items-center gap-3">
        <div className="text-5xl font-bold tracking-normal">{setup.signal}</div>
        <span className="rounded-full border border-white/40 bg-white/70 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-foreground/80">
          {String(setupType)}
        </span>
      </div>
      <p className="mt-3 max-w-md text-sm opacity-80">
        This signal is the visible outcome of confluence, conflict resolution, and risk gates.
      </p>
      <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
        <span>Confidence</span>
        <strong>{formatPercent(setup.confidence)}</strong>
        <span>Regime</span>
        <strong>{setup.market_regime ?? "-"}</strong>
        <span>Confluence</span>
        <strong>{formatPercent(confluence)}</strong>
        <span>Conflict</span>
        <strong>{String(conflictLevel ?? "-")}</strong>
        <span>Probability</span>
        <strong>{setup.probability_source ?? "raw"}</strong>
        <span>Model</span>
        <strong>{setup.model_scope_used ? `${setup.model_scope_used} ${setup.model_version ?? ""}` : "-"}</strong>
        <span>Size Multiplier</span>
        <strong>{formatNumber(sizeMultiplier, 2)}</strong>
        <span>Wait Reason</span>
        <strong>{waitReason}</strong>
      </div>
    </section>
  );
}
