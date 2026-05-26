import { useMemo } from "react";
import { AlertTriangle, Loader2 } from "lucide-react";
import { Button } from "@/components/forms/Button";
import { PageHeader } from "@/components/layout/PageHeader";
import { ConflictSummaryCard } from "@/components/reasoning/ConflictSummaryCard";
import { DecisionTraceViewer } from "@/components/reasoning/DecisionTraceViewer";
import { EvidenceRail, RiskGuardBanner } from "@/components/reasoning/ReasoningPanels";
import { MarketContextCard } from "@/components/reasoning/MarketContextCard";
import { ReasoningSummaryCard } from "@/components/reasoning/ReasoningSummaryCard";
import { SignalSummaryCard } from "@/components/reasoning/SignalSummaryCard";
import {
  resolveDecisionTrace,
  resolveSignalIntelligence,
} from "@/components/reasoning/signalIntelligence";
import { useActions, useRiskStatusQuery } from "@/hooks/useApiQueries";
import type { ReasoningEvidencePayload, TradeSetup } from "@/types";

interface SignalPageProps {
  latestSignal?: TradeSetup | null;
  onSignalGenerated: (setup: TradeSetup) => void;
}

export function SignalPage({ latestSignal, onSignalGenerated }: SignalPageProps) {
  const actions = useActions();
  const riskStatus = useRiskStatusQuery();
  const snapshot = resolveSignalIntelligence(latestSignal);
  const trace = resolveDecisionTrace(latestSignal, snapshot.reasoning);
  const supportingEvidence = useMemo(
    () => normalizeEvidence(snapshot.reasoning?.evidence_for),
    [snapshot.reasoning?.evidence_for],
  );
  const opposingEvidence = useMemo(
    () => normalizeEvidence(snapshot.reasoning?.evidence_against),
    [snapshot.reasoning?.evidence_against],
  );

  const generate = async () => {
    const setup = await actions.generateSignal.mutateAsync(true);
    onSignalGenerated(setup);
  };

  return (
    <div>
      <RiskGuardBanner state={riskStatus.data?.state} reasons={riskStatus.data?.reasons} />
      <PageHeader
        title="Signal Intelligence"
        description="Reasoning Brain signal summary, market context, conflict checks, and trace diagnostics."
        actions={
          <Button onClick={generate} disabled={actions.generateSignal.isPending}>
            {actions.generateSignal.isPending ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Generating...
              </>
            ) : (
              "Generate Signal"
            )}
          </Button>
        }
      />

      {actions.generateSignal.isPending ? (
        <StatePanel tone="loading" title="Generating signal" message="Building features, checking RiskGuard, and collecting reasoning evidence..." />
      ) : null}

      {actions.generateSignal.isError ? (
        <StatePanel tone="error" title="Unable to generate signal" message="Please verify market data availability and try again." />
      ) : null}

      {riskStatus.isLoading ? (
        <StatePanel tone="loading" title="Loading RiskGuard" message="Risk controls are being refreshed." />
      ) : null}

      {riskStatus.isError ? (
        <StatePanel tone="warning" title="Risk status unavailable" message="Signal view can render, but RiskGuard state could not be loaded." />
      ) : null}

      {!latestSignal ? (
        <StatePanel tone="empty" title="No signal yet" message="Generate a signal to see Signal Intelligence details." />
      ) : null}

      {latestSignal && !snapshot.hasReasoning ? (
        <StatePanel
          tone="warning"
          title="Reasoning decision missing"
          message="Falling back to the legacy signal payload until the backend returns reasoning_decision."
        />
      ) : null}

      <div className="grid gap-4 xl:grid-cols-[1.15fr_0.85fr]">
        <SignalSummaryCard setup={latestSignal} riskStatus={riskStatus.data ?? null} />
        <MarketContextCard setup={latestSignal} />
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-[0.9fr_1.1fr]">
        <ConflictSummaryCard setup={latestSignal} />
        <ReasoningSummaryCard setup={latestSignal} />
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-2">
        <EvidenceRail
          title="Evidence For"
          items={supportingEvidence}
          tone="for"
          emptyText="No supporting evidence available."
        />
        <EvidenceRail
          title="Evidence Against"
          items={opposingEvidence}
          tone="against"
          emptyText="No opposing evidence available."
        />
      </div>

      <div className="mt-4">
        <DecisionTraceViewer trace={trace} title="Decision Trace" />
      </div>
    </div>
  );
}

function normalizeEvidence(items?: ReasoningEvidencePayload[] | null): ReasoningEvidencePayload[] {
  return Array.isArray(items) ? items : [];
}

function StatePanel({
  title,
  message,
  tone,
}: {
  title: string;
  message: string;
  tone: "loading" | "error" | "warning" | "empty";
}) {
  const toneClass = {
    loading: "border-slate-200 bg-slate-50 text-slate-800",
    error: "border-red-200 bg-red-50 text-red-800",
    warning: "border-amber-200 bg-amber-50 text-amber-800",
    empty: "border-dashed border-border bg-white text-muted-foreground",
  }[tone];

  return (
    <section className={`mb-4 rounded-xl border p-4 text-sm shadow-sm ${toneClass}`}>
      <div className="flex items-start gap-3">
        {tone === "loading" ? <Loader2 className="mt-0.5 h-4 w-4 animate-spin" /> : <AlertTriangle className="mt-0.5 h-4 w-4" />}
        <div>
          <p className="font-semibold">{title}</p>
          <p className="mt-1">{message}</p>
        </div>
      </div>
    </section>
  );
}
