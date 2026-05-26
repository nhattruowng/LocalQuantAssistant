import { useMemo, useState } from "react";
import { AlertTriangle, ShieldAlert } from "lucide-react";
import { Button } from "@/components/forms/Button";
import { MetricCard } from "@/components/cards/MetricCard";
import { PageHeader } from "@/components/layout/PageHeader";
import { DecisionTraceViewer } from "@/components/reasoning/DecisionTraceViewer";
import { RiskGuardBanner, resolveDecisionTrace, resolveReasoning } from "@/components/reasoning/ReasoningPanels";
import { useActions, useRiskStatusQuery } from "@/hooks/useApiQueries";
import { cn, formatNumber, formatPercent, signalClass } from "@/lib/utils";
import type {
  ReasoningDecisionPayload,
  ReasoningEvidencePayload,
  StructuredExplanation,
  TradeSetup,
} from "@/types";

interface SignalPageProps {
  latestSignal?: TradeSetup | null;
  onSignalGenerated: (setup: TradeSetup) => void;
}

type EvidenceTab = "for" | "against" | "warnings";

const SETUP_TYPES = [
  "TREND_CONTINUATION_PULLBACK",
  "CLEAN_BREAKOUT",
  "LIQUIDITY_SWEEP_REVERSAL",
  "RANGE_REVERSION",
  "FAKEOUT_RISK",
  "CONFLICTED",
  "NO_CLEAR_SETUP",
] as const;

const EVIDENCE_SOURCES = ["regime", "price_action", "ict", "volume", "model", "mtf", "risk"] as const;

function isReasoningAvailable(reasoning: ReasoningDecisionPayload | null | undefined): boolean {
  return Boolean(reasoning && typeof reasoning === "object" && Object.keys(reasoning).length);
}

function normalizeSetupType(value?: string | null) {
  const raw = String(value ?? "").trim().toUpperCase();
  if (!raw) return "NO_CLEAR_SETUP";
  if ((SETUP_TYPES as readonly string[]).includes(raw)) return raw;
  return raw;
}

function toEvidence(
  items: ReasoningEvidencePayload[] | null | undefined,
  fallbackSource: (item: ReasoningEvidencePayload) => string,
) {
  if (!Array.isArray(items)) return [];
  return items.map((item) => ({
    ...item,
    source: normalizeSource(item.source ?? fallbackSource(item)),
  }));
}

function normalizeSource(source?: string) {
  const normalized = String(source ?? "risk").toLowerCase();
  if (EVIDENCE_SOURCES.includes(normalized as (typeof EVIDENCE_SOURCES)[number])) return normalized;
  if (normalized.includes("price")) return "price_action";
  if (normalized.includes("ict")) return "ict";
  if (normalized.includes("model")) return "model";
  if (normalized.includes("mtf") || normalized.includes("multi")) return "mtf";
  if (normalized.includes("vol")) return "volume";
  if (normalized.includes("regime")) return "regime";
  return "risk";
}

function warningEvidence(reasoning: ReasoningDecisionPayload | null, traceWarnings: string[] | undefined) {
  const warnings = [
    ...(Array.isArray(reasoning?.warnings) ? reasoning.warnings : []),
    ...(Array.isArray(traceWarnings) ? traceWarnings : []),
  ];
  return warnings.map((reason, index) => ({
    name: `Warning ${index + 1}`,
    source: inferWarningSource(reason),
    direction: "NEUTRAL",
    score: undefined,
    confidence: undefined,
    weight: undefined,
    impact_on_score: undefined,
    reason,
    is_critical: /block|critical|high|riskguard/i.test(reason),
  })) satisfies ReasoningEvidencePayload[];
}

function inferWarningSource(reason: string) {
  const text = reason.toLowerCase();
  if (text.includes("mtf") || text.includes("multi")) return "mtf";
  if (text.includes("model") || text.includes("calibration") || text.includes("probability")) return "model";
  if (text.includes("volume")) return "volume";
  if (text.includes("price") || text.includes("structure") || text.includes("breakout") || text.includes("wick")) return "price_action";
  if (text.includes("regime")) return "regime";
  return "risk";
}

function summaryFromReasoning(setup?: TradeSetup | null, reasoning?: ReasoningDecisionPayload | null, explanation?: StructuredExplanation | null) {
  const finalSignal = reasoning?.final_signal ?? setup?.signal ?? "-";
  const setupType = reasoning?.setup_type ?? setup?.setup_type ?? explanation?.strategy?.setup_type ?? "NO_CLEAR_SETUP";
  const reasons = [
    ...topTextFromEvidence(reasoning?.evidence_for),
    ...(setup?.reasons ?? []),
  ].filter(Boolean);
  const topFor = reasons.slice(0, 3).join(", ");
  const sizeMultiplier = reasoning?.position_size_multiplier ?? setup?.position_size_multiplier ?? setup?.size_multiplier ?? null;
  const waitReason = reasoning?.wait_reason ?? setup?.wait_reason ?? explanation?.strategy?.why_wait ?? null;

  if (!isReasoningAvailable(reasoning)) {
    return "Reasoning data is not available for this signal.";
  }

  if (finalSignal === "WAIT") {
    const reasonText = waitReason ? ` vì ${waitReason}` : "";
    return `WAIT được chọn${reasonText}.`;
  }

  const leading = finalSignal === "BUY" ? "BUY được chọn" : "SELL được chọn";
  const evidenceText = topFor ? ` vì ${topFor}.` : ".";
  const sizeText =
    typeof sizeMultiplier === "number" && Number.isFinite(sizeMultiplier) && sizeMultiplier < 1
      ? ` Tuy nhiên size giảm còn ${formatNumber(sizeMultiplier, 2)}x do conflict/MTF/risk gating.`
      : "";

  return `${leading} với setup ${setupType}${evidenceText}${sizeText}`;
}

function topTextFromEvidence(items?: ReasoningEvidencePayload[] | null) {
  if (!Array.isArray(items)) return [];
  return [...items]
    .sort((left, right) => Math.abs(Number(right.impact_on_score ?? right.score ?? 0)) - Math.abs(Number(left.impact_on_score ?? left.score ?? 0)))
    .map((item) => item.reason ?? item.name ?? "")
    .filter(Boolean);
}

function resolveMultiTimeframeText(explanation?: StructuredExplanation | null) {
  const multi = explanation?.multi_timeframe;
  if (!multi) return "-";
  if (multi.blocked) return "Blocked";
  if (Array.isArray(multi.aligned_timeframes) && multi.aligned_timeframes.length) {
    return multi.aligned_timeframes.join(", ");
  }
  if (Array.isArray(multi.reasons) && multi.reasons.length) {
    return multi.reasons.join("; ");
  }
  return "Partial";
}

function EvidenceItemCard({ evidence }: { evidence: ReasoningEvidencePayload }) {
  return (
    <article className="rounded-lg border border-border bg-white p-3 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-foreground">{evidence.name ?? "Evidence"}</p>
          <p className="mt-1 text-xs uppercase tracking-wide text-muted-foreground">
            {normalizeSource(evidence.source)} · {String(evidence.direction ?? "NEUTRAL").toUpperCase()}
          </p>
        </div>
        {evidence.is_critical ? (
          <span className="rounded-full border border-amber-200 bg-amber-50 px-2 py-1 text-[11px] font-semibold uppercase tracking-wide text-amber-800">
            critical
          </span>
        ) : null}
      </div>
      <div className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
        <Field label="Score" value={formatNumber(evidence.score ?? null, 2)} />
        <Field label="Confidence" value={formatPercent(evidence.confidence ?? null)} />
        <Field label="Weight" value={formatNumber(evidence.weight ?? null, 2)} />
        <Field label="Impact" value={formatNumber(evidence.impact_on_score ?? null, 2)} />
      </div>
      <div className="mt-3">
        <p className="text-xs uppercase tracking-wide text-muted-foreground">Reason</p>
        <p className="mt-1 text-sm text-foreground">{evidence.reason ?? "-"}</p>
      </div>
    </article>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md bg-muted/50 p-2">
      <p className="text-[11px] uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="mt-1 text-sm font-medium text-foreground">{value}</p>
    </div>
  );
}

function TabButton({
  active,
  children,
  onClick,
}: {
  active: boolean;
  children: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "rounded-md px-3 py-2 text-sm font-medium transition",
        active ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground hover:text-foreground",
      )}
    >
      {children}
    </button>
  );
}

export function SignalPage({ latestSignal, onSignalGenerated }: SignalPageProps) {
  const actions = useActions();
  const riskStatus = useRiskStatusQuery();
  const [multiTimeframe, setMultiTimeframe] = useState(true);
  const [activeTab, setActiveTab] = useState<EvidenceTab>("for");

  const reasoning = resolveReasoning(latestSignal);
  const trace = resolveDecisionTrace(latestSignal);
  const explanation = latestSignal?.explanation_v2 ?? null;

  const evidenceFor = useMemo(() => toEvidence(reasoning?.evidence_for, () => "risk"), [reasoning?.evidence_for]);
  const evidenceAgainst = useMemo(() => toEvidence(reasoning?.evidence_against, () => "risk"), [reasoning?.evidence_against]);
  const warningItems = useMemo(() => warningEvidence(reasoning, trace?.warnings), [reasoning, trace?.warnings]);

  const finalSignal = reasoning?.final_signal ?? latestSignal?.signal ?? "-";
  const setupType = normalizeSetupType(reasoning?.setup_type ?? latestSignal?.setup_type ?? explanation?.strategy?.setup_type);
  const confluence = reasoning?.confluence_score ?? latestSignal?.confluence_score ?? explanation?.strategy?.confluence_score ?? null;
  const confidence = reasoning?.confidence ?? latestSignal?.confidence ?? explanation?.regime?.confidence ?? null;
  const adaptiveThreshold = reasoning?.adaptive_threshold ?? explanation?.strategy?.adaptive_threshold ?? null;
  const sizeMultiplier = reasoning?.position_size_multiplier ?? latestSignal?.position_size_multiplier ?? latestSignal?.size_multiplier ?? explanation?.multi_timeframe?.confidence_multiplier ?? null;
  const waitReason = finalSignal === "WAIT"
    ? reasoning?.wait_reason ?? latestSignal?.wait_reason ?? explanation?.strategy?.why_wait ?? "-"
    : "-";
  const conflictLevel = reasoning?.conflict_level ?? latestSignal?.conflict_level ?? explanation?.strategy?.conflict_result?.severity ?? "-";

  const summary = summaryFromReasoning(latestSignal, reasoning, explanation);
  const marketContext = {
    symbol: latestSignal?.symbol ?? "-",
    timeframe: latestSignal?.timeframe ?? "-",
    regime: latestSignal?.market_regime ?? explanation?.regime?.primary ?? "-",
    regimeConfidence: explanation?.regime?.confidence ?? null,
    volatilityLevel: explanation?.regime?.volatility_level ?? "-",
    transitionWarning: Boolean(explanation?.regime?.transition_warning),
    mtfAlignment: resolveMultiTimeframeText(explanation),
  };

  const hasReasoning = isReasoningAvailable(reasoning);

  const generate = async () => {
    const setup = await actions.generateSignal.mutateAsync(multiTimeframe);
    onSignalGenerated(setup);
  };

  return (
    <div>
      <RiskGuardBanner state={riskStatus.data?.state} reasons={riskStatus.data?.reasons} />
      <PageHeader
        title="Signal"
        description="Reasoning-first signal view with setup, evidence, market context, and summary."
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

      {riskStatus.isLoading ? (
        <div className="mb-4 rounded-lg border border-border bg-white p-3 text-sm text-muted-foreground">
          Loading risk controls...
        </div>
      ) : null}

      {!hasReasoning ? (
        <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
          Reasoning data is not available for this signal.
        </div>
      ) : null}

      {!latestSignal ? (
        <div className="mb-4 rounded-lg border border-dashed border-border bg-white p-6 text-sm text-muted-foreground">
          No signal generated yet. Run Generate Signal to see reasoning, evidence, and market context.
        </div>
      ) : null}

      <div className="grid gap-4 xl:grid-cols-[1.05fr_0.95fr]">
        <section className={cn("rounded-xl border p-5 shadow-sm", signalClass(finalSignal))}>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-sm font-medium opacity-80">Signal Summary</p>
              <div className="mt-2 flex flex-wrap items-center gap-3">
                <div className="text-4xl font-bold tracking-normal">{finalSignal}</div>
                <span className="rounded-full border border-white/40 bg-white/70 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-foreground/80">
                  {String(setupType)}
                </span>
              </div>
            </div>
            {String(conflictLevel ?? "").toUpperCase() === "HIGH" ? (
              <span className="inline-flex items-center gap-1 rounded-full border border-red-200 bg-red-50 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-red-800">
                <AlertTriangle className="h-3.5 w-3.5" />
                High conflict
              </span>
            ) : null}
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <MetricCard label="Confluence Score" value={formatPercent(confluence)} />
            <MetricCard label="Confidence" value={formatPercent(confidence)} />
            <MetricCard label="Adaptive Threshold" value={formatPercent(adaptiveThreshold)} />
            <MetricCard label="Position Size Multiplier" value={formatNumber(sizeMultiplier, 2)} />
            <MetricCard label="Wait Reason" value={finalSignal === "WAIT" ? waitReason : "-"} />
            <MetricCard label="Conflict Level" value={String(conflictLevel ?? "-")} />
          </div>
          {finalSignal === "WAIT" ? (
            <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
              <div className="flex items-center gap-2 font-medium">
                <ShieldAlert className="h-4 w-4" />
                WAIT explanation
              </div>
              <p className="mt-1">{waitReason}</p>
            </div>
          ) : null}
        </section>

        <section className="rounded-xl border border-border bg-white p-5 shadow-sm">
          <p className="text-sm font-medium text-muted-foreground">Market Context</p>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <Field label="Symbol" value={marketContext.symbol} />
            <Field label="Timeframe" value={marketContext.timeframe} />
            <Field label="Current Regime" value={marketContext.regime} />
            <Field label="Regime Confidence" value={formatPercent(marketContext.regimeConfidence)} />
            <Field label="Volatility Level" value={marketContext.volatilityLevel} />
            <Field label="Multi-timeframe Alignment" value={marketContext.mtfAlignment} />
          </div>
          {marketContext.transitionWarning ? (
            <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
              <div className="flex items-center gap-2 font-medium">
                <AlertTriangle className="h-4 w-4" />
                Transition warning
              </div>
              <p className="mt-1">The regime is showing transition risk or instability.</p>
            </div>
          ) : null}
        </section>
      </div>

      <section className="mt-4 rounded-xl border border-border bg-white p-5 shadow-sm">
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <TabButton active={activeTab === "for"} onClick={() => setActiveTab("for")}>
            Evidence For
          </TabButton>
          <TabButton active={activeTab === "against"} onClick={() => setActiveTab("against")}>
            Evidence Against
          </TabButton>
          <TabButton active={activeTab === "warnings"} onClick={() => setActiveTab("warnings")}>
            Warnings
          </TabButton>
        </div>
        {activeTab === "for" ? (
          evidenceFor.length ? (
            <div className="grid gap-3 xl:grid-cols-2">
              {evidenceFor.map((item, index) => (
                <EvidenceItemCard key={`${item.name ?? "for"}-${index}`} evidence={item} />
              ))}
            </div>
          ) : (
            <div className="rounded-lg border border-dashed border-border p-6 text-sm text-muted-foreground">
              No supporting evidence available.
            </div>
          )
        ) : null}
        {activeTab === "against" ? (
          evidenceAgainst.length ? (
            <div className="grid gap-3 xl:grid-cols-2">
              {evidenceAgainst.map((item, index) => (
                <EvidenceItemCard key={`${item.name ?? "against"}-${index}`} evidence={item} />
              ))}
            </div>
          ) : (
            <div className="rounded-lg border border-dashed border-border p-6 text-sm text-muted-foreground">
              No opposing evidence available.
            </div>
          )
        ) : null}
        {activeTab === "warnings" ? (
          warningItems.length ? (
            <div className="space-y-3">
              {warningItems.map((item, index) => (
                <EvidenceItemCard key={`${item.name ?? "warning"}-${index}`} evidence={item} />
              ))}
            </div>
          ) : (
            <div className="rounded-lg border border-dashed border-border p-6 text-sm text-muted-foreground">
              No warnings available.
            </div>
          )
        ) : null}
      </section>

      <section className="mt-4 rounded-xl border border-border bg-white p-5 shadow-sm">
        <h3 className="text-sm font-semibold">Reasoning Summary</h3>
        <p className="mt-2 text-sm leading-6 text-foreground">{summary}</p>
      </section>

      <div className="mt-4">
        <DecisionTraceViewer trace={trace} title="Decision Trace" />
      </div>
    </div>
  );
}
