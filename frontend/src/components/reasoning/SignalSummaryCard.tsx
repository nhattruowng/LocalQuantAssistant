import { AlertTriangle, ShieldAlert } from "lucide-react";
import { MetricCard } from "@/components/cards/MetricCard";
import {
  resolveSignalIntelligence,
  riskGuardIsBlocked,
} from "@/components/reasoning/signalIntelligence";
import { cn, formatNumber, formatPercent, signalClass } from "@/lib/utils";
import type { RiskStatus, TradeSetup } from "@/types";

interface SignalSummaryCardProps {
  setup?: TradeSetup | null;
  riskStatus?: RiskStatus | null;
}

export function SignalSummaryCard({ setup, riskStatus }: SignalSummaryCardProps) {
  const snapshot = resolveSignalIntelligence(setup);
  const blocked = riskGuardIsBlocked(riskStatus?.state);
  const panelTone = blocked
    ? "border-red-300 bg-red-50 text-red-950"
    : signalClass(snapshot.finalSignal);

  return (
    <section className={cn("rounded-2xl border p-5 shadow-sm", panelTone)}>
      {blocked ? (
        <div className="mb-4 rounded-xl border border-red-300 bg-white/80 p-4 text-red-900 shadow-sm">
          <div className="flex items-start gap-3">
            <ShieldAlert className="mt-0.5 h-5 w-5" />
            <div>
              <p className="font-semibold">RiskGuard {String(riskStatus?.state ?? "BLOCKED").toUpperCase()}</p>
              <p className="mt-1 text-sm">
                {(riskStatus?.reasons ?? [])[0] ?? "Risk controls are blocking this signal context."}
              </p>
            </div>
          </div>
        </div>
      ) : null}

      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-sm font-medium opacity-80">Signal Intelligence</p>
          <div className="mt-2 flex flex-wrap items-center gap-3">
            <div className="text-5xl font-bold tracking-tight">{snapshot.finalSignal}</div>
            <span className="rounded-full border border-white/50 bg-white/75 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-foreground/80">
              {snapshot.setupType}
            </span>
          </div>
          {!snapshot.hasReasoning ? (
            <p className="mt-3 text-sm opacity-80">
              Reasoning Brain details are missing; displaying the legacy signal payload.
            </p>
          ) : null}
        </div>
        {snapshot.conflictLevel.toUpperCase() === "HIGH" ? (
          <span className="inline-flex items-center gap-1 rounded-full border border-red-300 bg-white/80 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-red-800">
            <AlertTriangle className="h-3.5 w-3.5" />
            High conflict
          </span>
        ) : null}
      </div>

      <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <MetricCard label="Confluence" value={formatPercent(snapshot.confluenceScore)} className="bg-white/75" />
        <MetricCard label="Confidence" value={formatPercent(snapshot.confidence)} className="bg-white/75" />
        <MetricCard label="Adaptive Threshold" value={formatPercent(snapshot.adaptiveThreshold)} className="bg-white/75" />
        <MetricCard label="Size Multiplier" value={formatNumber(snapshot.positionSizeMultiplier, 2)} className="bg-white/75" />
        <MetricCard label="Conflict" value={snapshot.conflictLevel} className="bg-white/75" />
      </div>

      {snapshot.finalSignal === "WAIT" ? (
        <div className="mt-4 rounded-xl border border-amber-300 bg-white/80 p-4 text-sm text-amber-950">
          <div className="flex items-center gap-2 font-semibold">
            <ShieldAlert className="h-4 w-4" />
            WAIT reason
          </div>
          <p className="mt-1">{snapshot.waitReason ?? "WAIT_NO_CLEAR_SETUP"}</p>
        </div>
      ) : null}
    </section>
  );
}
