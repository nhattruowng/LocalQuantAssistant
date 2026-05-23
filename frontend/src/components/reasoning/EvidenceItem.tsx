import { cn, formatNumber } from "@/lib/utils";
import type { ReasoningEvidencePayload } from "@/types";

function directionTone(direction?: string) {
  const value = String(direction ?? "NEUTRAL").toUpperCase();
  if (value === "BUY") return "border-emerald-200 bg-emerald-50 text-emerald-800";
  if (value === "SELL") return "border-red-200 bg-red-50 text-red-800";
  return "border-amber-200 bg-amber-50 text-amber-800";
}

export function EvidenceItem({ evidence }: { evidence: ReasoningEvidencePayload }) {
  return (
    <div className={cn("rounded-lg border p-3 text-sm", directionTone(evidence.direction))}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-semibold text-foreground">{evidence.name ?? "Evidence"}</p>
          <p className="mt-1 text-xs uppercase tracking-wide opacity-75">
            {evidence.source ?? "source"} · {String(evidence.direction ?? "NEUTRAL")} · {String(evidence.evidence_type ?? "SUPPORT")}
          </p>
        </div>
        <div className="text-right text-xs opacity-80">
          <div>score {formatNumber(evidence.score ?? null, 2)}</div>
          <div>impact {formatNumber(evidence.impact_on_score ?? null, 2)}</div>
        </div>
      </div>
      <p className="mt-2 text-sm opacity-90">{evidence.reason ?? "-"}</p>
      <div className="mt-2 flex flex-wrap gap-2 text-[11px] opacity-80">
        <span>confidence {formatNumber(evidence.confidence ?? null, 2)}</span>
        <span>weight {formatNumber(evidence.weight ?? null, 2)}</span>
        {evidence.is_critical ? <span>critical</span> : null}
      </div>
    </div>
  );
}
