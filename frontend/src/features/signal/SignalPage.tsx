import { useMemo, useState } from "react";
import { Button } from "@/components/forms/Button";
import { MetricCard } from "@/components/cards/MetricCard";
import { SignalCard } from "@/components/cards/SignalCard";
import { PageHeader } from "@/components/layout/PageHeader";
import { useActions } from "@/hooks/useApiQueries";
import { formatNumber, formatPercent } from "@/lib/utils";
import type {
  DecisionStepPayload,
  DecisionTracePayload,
  ReasoningDecisionPayload,
  ReasoningEvidencePayload,
  TradeSetup,
} from "@/types";

interface SignalPageProps {
  latestSignal?: TradeSetup | null;
  onSignalGenerated: (setup: TradeSetup) => void;
}

function extractTrace(setup?: TradeSetup | null): DecisionTracePayload | null {
  const reasoning = setup?.reasoning_decision as ReasoningDecisionPayload | null | undefined;
  const fromReasoning = reasoning?.decision_trace;
  if (fromReasoning && typeof fromReasoning === "object" && "steps" in fromReasoning) {
    return fromReasoning as DecisionTracePayload;
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

export function SignalPage({ latestSignal, onSignalGenerated }: SignalPageProps) {
  const actions = useActions();
  const [multiTimeframe, setMultiTimeframe] = useState(true);
  const explanation = latestSignal?.explanation_v2;
  const reasoning = (latestSignal?.reasoning_decision as ReasoningDecisionPayload | null | undefined) ?? null;
  const trace = useMemo(() => extractTrace(latestSignal), [latestSignal]);
  const traceSteps = Array.isArray(trace?.steps) ? trace.steps : [];
  const evidenceFor = topEvidence(reasoning?.evidence_for);
  const evidenceAgainst = topEvidence(reasoning?.evidence_against);

  const generate = async () => {
    const setup = await actions.generateSignal.mutateAsync(multiTimeframe);
    onSignalGenerated(setup);
  };

  return (
    <div>
      <PageHeader
        title="Signal"
        description="Signal output with reasoning, evidence conflict, and decision trace."
        actions={
          <div className="flex items-center gap-3">
            <label className="flex items-center gap-2 text-sm text-muted-foreground">
              <input
                type="checkbox"
                className="h-4 w-4 rounded border-border"
                checked={multiTimeframe}
                onChange={(event) => setMultiTimeframe(event.target.checked)}
              />
              Multi-timeframe
            </label>
            <Button onClick={generate} disabled={actions.generateSignal.isPending}>
              {actions.generateSignal.isPending ? "Generating..." : "Generate Signal"}
            </Button>
          </div>
        }
      />
      {actions.generateSignal.isError ? (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          Unable to generate signal. Please verify data and try again.
        </div>
      ) : null}
      <div className="grid gap-4 xl:grid-cols-[360px_1fr]">
        <SignalCard setup={latestSignal} />
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <MetricCard label="Final Signal" value={reasoning?.final_signal ?? latestSignal?.signal ?? "-"} />
          <MetricCard label="Setup Type" value={reasoning?.setup_type ?? explanation?.strategy?.setup_type ?? "-"} />
          <MetricCard label="Confluence Score" value={formatNumber(reasoning?.confluence_score ?? explanation?.strategy?.confluence_score ?? null, 4)} />
          <MetricCard label="Confidence" value={formatPercent(reasoning?.confidence ?? latestSignal?.confidence)} />
          <MetricCard label="Wait Reason" value={latestSignal?.signal === "WAIT" ? (reasoning?.wait_reason ?? latestSignal?.wait_reason ?? "-") : "-"} />
          <MetricCard label="Position Size Multiplier" value={formatNumber(reasoning?.position_size_multiplier ?? latestSignal?.size_multiplier ?? null, 4)} />
          <MetricCard label="Conflict Level" value={reasoning?.conflict_level ?? explanation?.strategy?.conflict_level ?? "-"} />
          <MetricCard label="Risk/Reward" value={formatNumber(latestSignal?.risk_reward, 2)} />
          <MetricCard label="Entry" value={formatNumber(latestSignal?.entry, 4)} />
          <MetricCard label="Stop Loss" value={formatNumber(latestSignal?.stop_loss, 4)} />
          <MetricCard label="Take Profit 1" value={formatNumber(latestSignal?.take_profit_1, 4)} />
          <MetricCard label="Take Profit 2" value={formatNumber(latestSignal?.take_profit_2, 4)} />
        </div>
      </div>
      <div className="mt-4 grid gap-4 xl:grid-cols-2">
        <section className="rounded-lg border border-border bg-white p-4">
          <h3 className="mb-3 font-semibold">Top Evidence For</h3>
          {evidenceFor.length ? (
            <ul className="space-y-2 text-sm text-muted-foreground">
              {evidenceFor.map((item, index) => (
                <li key={`${item.name ?? "for"}-${index}`} className="rounded border border-border p-2">
                  <p className="font-medium text-foreground">{item.name ?? "Evidence"}</p>
                  <p>{item.reason ?? "-"}</p>
                  <p className="mt-1 text-xs">
                    score {formatNumber(item.score ?? null, 3)} | conf {formatNumber(item.confidence ?? null, 3)} | impact {formatNumber(item.impact_on_score ?? null, 4)}
                  </p>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted-foreground">No supporting evidence payload.</p>
          )}
        </section>
        <section className="rounded-lg border border-border bg-white p-4">
          <h3 className="mb-3 font-semibold">Top Evidence Against</h3>
          {evidenceAgainst.length ? (
            <ul className="space-y-2 text-sm text-muted-foreground">
              {evidenceAgainst.map((item, index) => (
                <li key={`${item.name ?? "against"}-${index}`} className="rounded border border-border p-2">
                  <p className="font-medium text-foreground">{item.name ?? "Evidence"}</p>
                  <p>{item.reason ?? "-"}</p>
                  <p className="mt-1 text-xs">
                    score {formatNumber(item.score ?? null, 3)} | conf {formatNumber(item.confidence ?? null, 3)} | impact {formatNumber(item.impact_on_score ?? null, 4)}
                  </p>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted-foreground">No opposing evidence payload.</p>
          )}
        </section>
      </div>
      <div className="mt-4 grid gap-4 xl:grid-cols-2">
        <section className="rounded-lg border border-border bg-white p-4">
          <h3 className="mb-3 font-semibold">Risk Notes</h3>
          {latestSignal?.risk_notes?.length ? (
            <ul className="space-y-1 text-sm text-muted-foreground">
              {latestSignal.risk_notes.map((note) => <li key={note}>- {note}</li>)}
            </ul>
          ) : (
            <p className="text-sm text-muted-foreground">No risk notes.</p>
          )}
        </section>
        <section className="rounded-lg border border-border bg-white p-4">
          <h3 className="mb-3 font-semibold">Reasons</h3>
          {latestSignal?.reasons?.length ? (
            <ul className="space-y-1 text-sm text-muted-foreground">
              {latestSignal.reasons.map((reason) => <li key={reason}>- {reason}</li>)}
            </ul>
          ) : (
            <p className="text-sm text-muted-foreground">No signal reasons.</p>
          )}
        </section>
      </div>
      <section className="mt-4 rounded-lg border border-border bg-white p-4">
        <h3 className="mb-3 font-semibold">Decision Trace</h3>
        {!traceSteps.length ? (
          <p className="text-sm text-muted-foreground">No decision trace payload.</p>
        ) : (
          <div className="space-y-2">
            {traceSteps.map((step: DecisionStepPayload, index) => (
              <details key={`${step.step_name}-${index}`} className="rounded border border-border p-3">
                <summary className="cursor-pointer text-sm font-medium text-foreground">
                  {step.step_name} | in {formatNumber(step.input_score ?? null, 4)} → out {formatNumber(step.output_score ?? null, 4)} | {step.passed ? "passed" : "blocked"}
                </summary>
                <div className="mt-2 grid gap-2 text-sm text-muted-foreground md:grid-cols-2">
                  <div>delta: {formatNumber(step.delta ?? null, 4)}</div>
                  <div>timestamp: {step.timestamp ?? "-"}</div>
                </div>
                {Array.isArray(step.warnings) && step.warnings.length ? (
                  <ul className="mt-2 space-y-1 text-xs text-amber-700">
                    {step.warnings.map((warning) => <li key={warning}>warning: {warning}</li>)}
                  </ul>
                ) : null}
                <pre className="mt-2 max-h-56 overflow-auto rounded bg-muted p-2 text-xs">
                  {JSON.stringify(step.details ?? {}, null, 2)}
                </pre>
              </details>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
