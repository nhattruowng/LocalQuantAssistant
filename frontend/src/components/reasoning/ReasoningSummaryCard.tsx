import type { TradeSetup } from "@/types";
import { resolveSignalIntelligence } from "@/components/reasoning/signalIntelligence";

export function ReasoningSummaryCard({ setup }: { setup?: TradeSetup | null }) {
  const snapshot = resolveSignalIntelligence(setup);
  const evidenceFor = snapshot.reasoning?.evidence_for ?? [];
  const warnings = [
    ...(snapshot.reasoning?.warnings ?? []),
    ...(snapshot.trace?.warnings ?? []),
  ];
  const leadingEvidence = evidenceFor
    .map((item) => item.reason ?? item.name)
    .filter(Boolean)
    .slice(0, 3);

  const summary = snapshot.hasReasoning
    ? buildReasoningSummary(snapshot.finalSignal, snapshot.setupType, leadingEvidence, snapshot.waitReason)
    : "Reasoning decision is not available yet. The page is safely falling back to the legacy signal response.";

  return (
    <section className="rounded-2xl border border-border bg-white p-5 shadow-sm">
      <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Reasoning Summary</p>
      <p className="mt-3 text-sm leading-6 text-foreground">{summary}</p>
      {warnings.length ? (
        <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
          <p className="font-semibold">Warnings</p>
          <ul className="mt-2 space-y-1">
            {warnings.slice(0, 5).map((warning) => (
              <li key={warning}>• {warning}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}

function buildReasoningSummary(
  finalSignal: string,
  setupType: string,
  evidence: Array<string | undefined>,
  waitReason: string | null,
): string {
  if (finalSignal === "WAIT") {
    return `WAIT is active because ${waitReason ?? "the setup did not pass enough causal checks"}.`;
  }
  const evidenceText = evidence.length ? ` Top evidence: ${evidence.join("; ")}.` : "";
  return `${finalSignal} is the active fallback-safe decision for ${setupType}.${evidenceText}`;
}
