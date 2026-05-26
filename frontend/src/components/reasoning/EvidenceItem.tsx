import { AlertTriangle } from "lucide-react";
import { cn, formatNumber } from "@/lib/utils";
import type { ReasoningEvidencePayload } from "@/types";

function evidenceTone(evidence: ReasoningEvidencePayload) {
  const type = String(evidence.evidence_type ?? "").toUpperCase();
  const value = String(evidence.direction ?? "NEUTRAL").toUpperCase();
  if (type === "WARNING") return "border-amber-200 bg-amber-50 text-amber-900";
  if (type === "AGAINST") return "border-red-200 bg-red-50 text-red-900";
  if (value === "BUY") return "border-emerald-200 bg-emerald-50 text-emerald-800";
  if (value === "SELL") return "border-red-200 bg-red-50 text-red-800";
  return "border-slate-200 bg-slate-50 text-slate-800";
}

export function EvidenceItem({ evidence }: { evidence: ReasoningEvidencePayload }) {
  const isCritical = Boolean(evidence.is_critical);

  return (
    <article className={cn("rounded-xl border p-4 text-sm shadow-sm", evidenceTone(evidence))}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-semibold text-foreground">{evidence.name ?? "Evidence"}</p>
          <p className="mt-1 text-xs uppercase tracking-wide opacity-75">
            {evidence.source ?? "source"} · {String(evidence.direction ?? "NEUTRAL")} · {String(evidence.evidence_type ?? "SUPPORT")}
          </p>
        </div>
        {isCritical ? (
          <span className="inline-flex items-center gap-1 rounded-full border border-red-200 bg-white/80 px-2 py-1 text-[11px] font-semibold uppercase tracking-wide text-red-800">
            <AlertTriangle className="h-3 w-3" />
            critical
          </span>
        ) : null}
      </div>
      <p className="mt-2 text-sm opacity-90">{evidence.reason ?? "-"}</p>
      <div className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
        <EvidenceMetric label="Score" value={formatNumber(evidence.score ?? null, 2)} />
        <EvidenceMetric label="Confidence" value={formatNumber(evidence.confidence ?? null, 2)} />
        <EvidenceMetric label="Weight" value={formatNumber(evidence.weight ?? null, 2)} />
        <EvidenceMetric label="Impact" value={formatNumber(evidence.impact_on_score ?? null, 2)} />
        <EvidenceMetric label="Source" value={evidence.source ?? "-"} />
        <EvidenceMetric label="Direction" value={String(evidence.direction ?? "NEUTRAL")} />
        <EvidenceMetric label="Type" value={String(evidence.evidence_type ?? "SUPPORT")} />
        <EvidenceMetric label="Critical" value={isCritical ? "Yes" : "No"} />
      </div>
    </article>
  );
}

function EvidenceMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-white/50 bg-white/70 p-2">
      <p className="text-[10px] uppercase tracking-wide opacity-70">{label}</p>
      <p className="mt-1 break-words text-xs font-semibold text-foreground">{value}</p>
    </div>
  );
}
