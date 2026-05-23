import { AlertTriangle, ArrowRightLeft, ShieldAlert, Sparkles } from "lucide-react";
import { DecisionTraceViewer } from "@/components/reasoning/DecisionTraceViewer";
import type {
  DecisionStepPayload,
  DecisionTracePayload,
  ReasoningDecisionPayload,
  ReasoningEvidencePayload,
  TradeSetup,
} from "@/types";
import { cn, formatNumber, formatPercent, signalClass } from "@/lib/utils";

export function resolveReasoning(setup?: TradeSetup | null): ReasoningDecisionPayload | null {
  if (!setup) return null;
  const candidate = setup.reasoning_decision;
  return candidate && typeof candidate === "object" ? candidate : null;
}

export function resolveDecisionTrace(setup?: TradeSetup | null): DecisionTracePayload | null {
  const reasoning = resolveReasoning(setup);
  const trace = reasoning?.decision_trace;
  if (trace && typeof trace === "object" && "steps" in trace) {
    return trace as DecisionTracePayload;
  }
  const diagnostics = setup?.strategy_diagnostics;
  if (diagnostics && typeof diagnostics === "object") {
    const candidate = (diagnostics as Record<string, unknown>).decision_trace;
    if (candidate && typeof candidate === "object" && "steps" in candidate) {
      return candidate as DecisionTracePayload;
    }
  }
  return null;
}

function topEvidence(evidence: ReasoningEvidencePayload[] | undefined, count = 5) {
  if (!Array.isArray(evidence)) return [];
  return [...evidence]
    .sort((left, right) => Math.abs(Number(right.impact_on_score ?? right.score ?? 0)) - Math.abs(Number(left.impact_on_score ?? left.score ?? 0)))
    .slice(0, count);
}

function evidenceTone(item: ReasoningEvidencePayload) {
  const type = String(item.evidence_type ?? "").toUpperCase();
  if (type === "WARNING") return "border-amber-200 bg-amber-50 text-amber-900";
  if (type === "AGAINST") return "border-red-200 bg-red-50 text-red-900";
  return "border-emerald-200 bg-emerald-50 text-emerald-900";
}

function directionLabel(item: ReasoningEvidencePayload) {
  const direction = String(item.direction ?? "NEUTRAL").toUpperCase();
  return direction === "BUY" || direction === "SELL" ? direction : "NEUTRAL";
}

export function ReasoningOverview({ setup }: { setup?: TradeSetup | null }) {
  const reasoning = resolveReasoning(setup);
  const finalSignal = reasoning?.final_signal ?? setup?.signal ?? "-";
  const confluence = reasoning?.confluence_score ?? setup?.confluence_score ?? null;
  const confidence = reasoning?.confidence ?? setup?.confidence ?? null;
  const sizeMultiplier = reasoning?.position_size_multiplier ?? setup?.position_size_multiplier ?? setup?.size_multiplier ?? null;
  const waitReason = finalSignal === "WAIT" ? reasoning?.wait_reason ?? setup?.wait_reason ?? "-" : "-";
  const conflictLevel = reasoning?.conflict_level ?? setup?.conflict_level ?? "-";
  const setupType = reasoning?.setup_type ?? setup?.setup_type ?? setup?.strategy ?? "-";

  return (
    <section className={cn("rounded-xl border p-5 shadow-sm", signalClass(finalSignal))}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm font-medium opacity-80">Market Reasoning Brain</p>
          <div className="mt-2 flex flex-wrap items-center gap-3">
            <div className="text-4xl font-bold tracking-normal">{finalSignal}</div>
            <span className="rounded-full border border-white/40 bg-white/70 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-foreground/80">
              {String(setupType ?? "-")}
            </span>
          </div>
          <p className="mt-3 max-w-2xl text-sm text-foreground/80">
            The signal is not just a label. It is a scored decision assembled from evidence, conflicts, risk filters, and setup quality.
          </p>
        </div>
        <div className="flex flex-wrap gap-2 text-xs">
          {finalSignal === "WAIT" ? (
            <span className="inline-flex items-center gap-1 rounded-full border border-amber-200 bg-white/80 px-3 py-1 font-medium text-amber-700">
              <ShieldAlert className="h-3.5 w-3.5" />
              {waitReason}
            </span>
          ) : null}
          <span className="inline-flex items-center gap-1 rounded-full border border-white/40 bg-white/70 px-3 py-1 font-medium">
            <Sparkles className="h-3.5 w-3.5" />
            Confidence {formatPercent(confidence)}
          </span>
          <span className="inline-flex items-center gap-1 rounded-full border border-white/40 bg-white/70 px-3 py-1 font-medium">
            <ArrowRightLeft className="h-3.5 w-3.5" />
            Confluence {formatPercent(confluence)}
          </span>
        </div>
      </div>
      <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <MiniReasoningMetric label="Setup Type" value={String(setupType ?? "-")} />
        <MiniReasoningMetric label="Conflict Level" value={String(conflictLevel ?? "-")} />
        <MiniReasoningMetric label="Size Multiplier" value={formatNumber(sizeMultiplier, 2)} />
        <MiniReasoningMetric label="Wait Reason" value={String(waitReason ?? "-")} />
      </div>
      {String(conflictLevel ?? "").toUpperCase() === "HIGH" ? (
        <div className="mt-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">
          <div className="flex items-center gap-2 font-medium">
            <AlertTriangle className="h-4 w-4" />
            High conflict detected
          </div>
          <p className="mt-1">
            Conflicting evidence is strong enough to materially reduce confidence or move the setup to WAIT.
          </p>
        </div>
      ) : null}
      {Array.isArray(setup?.risk_notes) && setup.risk_notes.length ? (
        <div className="mt-4 rounded-lg border border-white/40 bg-white/70 p-3 text-sm text-foreground/80">
          <div className="mb-2 flex items-center gap-2 font-medium">
            <AlertTriangle className="h-4 w-4" />
            Risk Notes
          </div>
          <ul className="space-y-1">
            {setup.risk_notes.slice(0, 4).map((note) => (
              <li key={note}>• {note}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}

export function RiskGuardBanner({
  state,
  reasons,
}: {
  state?: string | null;
  reasons?: string[] | null;
}) {
  const normalized = String(state ?? "").toUpperCase();
  if (normalized !== "BLOCKED" && normalized !== "COOLDOWN" && normalized !== "WARNING") return null;

  const isBlocked = normalized === "BLOCKED";
  const tone = isBlocked ? "border-red-200 bg-red-50 text-red-800" : "border-amber-200 bg-amber-50 text-amber-800";
  const title = isBlocked ? "RiskGuard BLOCKED" : normalized;
  const message = reasons?.[0] ?? (isBlocked ? "New signals are blocked by risk controls." : "Risk controls are active.");

  return (
    <section className={cn("mb-4 rounded-lg border p-4 shadow-sm", tone)}>
      <div className="flex items-start gap-3">
        <ShieldAlert className="mt-0.5 h-5 w-5" />
        <div>
          <p className="font-semibold">{title}</p>
          <p className="mt-1 text-sm">{message}</p>
        </div>
      </div>
    </section>
  );
}

export function EvidenceRail({
  title,
  items,
  tone,
  emptyText,
}: {
  title: string;
  items?: ReasoningEvidencePayload[] | null;
  tone: "for" | "against" | "warning";
  emptyText: string;
}) {
  const evidence = topEvidence(items ?? undefined, 6);

  return (
    <section className="rounded-lg border border-border bg-white p-4 shadow-sm">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold">{title}</h3>
        <span
          className={cn(
            "rounded-full px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide",
            tone === "for" && "bg-emerald-50 text-emerald-700",
            tone === "against" && "bg-red-50 text-red-700",
            tone === "warning" && "bg-amber-50 text-amber-700",
          )}
        >
          {evidence.length}
        </span>
      </div>
      {evidence.length ? (
        <ul className="space-y-2">
          {evidence.map((item, index) => (
            <li key={`${item.name ?? title}-${index}`} className={cn("rounded-lg border p-3 text-sm", evidenceTone(item))}>
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <p className="font-semibold text-foreground">{item.name ?? "Evidence"}</p>
                  <p className="mt-1 text-xs uppercase tracking-wide opacity-70">
                    {item.source ?? "source"} · {directionLabel(item)} · {String(item.evidence_type ?? "SUPPORT")}
                  </p>
                </div>
                <div className="text-right text-xs opacity-80">
                  <div>impact {formatNumber(item.impact_on_score ?? null, 2)}</div>
                  <div>score {formatNumber(item.score ?? null, 2)}</div>
                </div>
              </div>
              <p className="mt-2 text-sm opacity-90">{item.reason ?? "-"}</p>
              <div className="mt-2 flex flex-wrap gap-2 text-[11px] opacity-80">
                <span>confidence {formatNumber(item.confidence ?? null, 2)}</span>
                <span>weight {formatNumber(item.weight ?? null, 2)}</span>
                {item.is_critical ? <span>critical</span> : null}
              </div>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-muted-foreground">{emptyText}</p>
      )}
    </section>
  );
}

export function ConflictPanel({ setup }: { setup?: TradeSetup | null }) {
  const reasoning = resolveReasoning(setup);
  const details = reasoning?.conflict_details ?? setup?.conflict_details ?? null;
  const conflictLevel = reasoning?.conflict_level ?? setup?.conflict_level ?? "-";
  const notes = reasoning?.warnings ?? setup?.risk_notes ?? [];

  return (
    <section className="rounded-lg border border-border bg-white p-4 shadow-sm">
      <h3 className="mb-3 text-sm font-semibold">Conflict and Risk</h3>
      <div className="grid gap-3 md:grid-cols-3">
        <MiniReasoningMetric label="Conflict Level" value={String(conflictLevel ?? "-")} />
        <MiniReasoningMetric label="RiskGuard" value={finalRiskGuardState(setup)} />
        <MiniReasoningMetric label="Evidence Warnings" value={String(Array.isArray(notes) ? notes.length : 0)} />
      </div>
      {Array.isArray(notes) && notes.length ? (
        <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
          <p className="mb-2 font-medium">Warnings</p>
          <ul className="space-y-1">
            {notes.slice(0, 5).map((note) => (
              <li key={note}>• {note}</li>
            ))}
          </ul>
        </div>
      ) : null}
      {details && typeof details === "object" ? (
        <details className="mt-3 rounded-lg border border-border p-3">
          <summary className="cursor-pointer text-sm font-medium">Conflict details</summary>
          <pre className="mt-2 max-h-56 overflow-auto rounded bg-muted p-2 text-xs">
            {JSON.stringify(details, null, 2)}
          </pre>
        </details>
      ) : null}
    </section>
  );
}

export function DecisionTracePanel({ setup }: { setup?: TradeSetup | null }) {
  return <DecisionTraceViewer trace={resolveDecisionTrace(setup)} />;
}

function MiniReasoningMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-white/50 bg-white/70 p-3">
      <p className="text-xs uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="mt-1 break-words text-sm font-semibold text-foreground">{value}</p>
    </div>
  );
}

function finalRiskGuardState(setup?: TradeSetup | null): string {
  const riskNotes = setup?.risk_notes ?? [];
  if (!riskNotes.length) return "clear";
  const blocked = riskNotes.find((note) => /block|blocked|cooldown|riskguard/i.test(note));
  return blocked ? "blocked" : "watch";
}
