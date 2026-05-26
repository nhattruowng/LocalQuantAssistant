import { useMemo, useState } from "react";
import { Copy, Filter, TriangleAlert } from "lucide-react";
import { Button } from "@/components/forms/Button";
import { Select } from "@/components/forms/Select";
import { cn, formatNumber } from "@/lib/utils";
import type { DecisionStepPayload, DecisionTracePayload } from "@/types";

export type DecisionTraceFilter = "all" | "failed" | "warning" | "score_changes";
export type DecisionTraceMode = "timeline" | "accordion";
export type DecisionTraceDensity = "compact" | "full";

interface DecisionTraceViewerProps {
  trace?: DecisionTracePayload | null;
  title?: string;
  className?: string;
}

function isWarningStep(step: DecisionStepPayload) {
  return Boolean(Array.isArray(step.warnings) && step.warnings.length);
}

function isFailedStep(step: DecisionStepPayload) {
  return step.passed === false;
}

function hasScoreChange(step: DecisionStepPayload) {
  const inputScore = Number(step.input_score ?? 0);
  const outputScore = Number(step.output_score ?? 0);
  const delta = Number(step.delta ?? outputScore - inputScore);
  return Number.isFinite(delta) && Math.abs(delta) > 0.0001;
}

function normalizeStepName(step: DecisionStepPayload) {
  return String(step.step_name ?? "step").trim() || "step";
}

function stepTone(step: DecisionStepPayload) {
  if (isFailedStep(step)) return "border-red-200 bg-red-50 text-red-900";
  if (isWarningStep(step)) return "border-amber-200 bg-amber-50 text-amber-900";
  return "border-border bg-white text-foreground";
}

function scoreLabel(value?: number | null) {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  return formatNumber(value, 2);
}

function safeTraceJson(trace?: DecisionTracePayload | null) {
  return JSON.stringify(trace ?? {}, null, 2);
}

export function DecisionTraceViewer({ trace, title = "Decision Trace", className }: DecisionTraceViewerProps) {
  const [mode, setMode] = useState<DecisionTraceMode>("timeline");
  const [density, setDensity] = useState<DecisionTraceDensity>("compact");
  const [filter, setFilter] = useState<DecisionTraceFilter>("all");
  const [copied, setCopied] = useState(false);

  const steps = useMemo(() => (Array.isArray(trace?.steps) ? trace.steps : []), [trace?.steps]);

  const filteredSteps = useMemo(() => {
    return steps.filter((step) => {
      if (filter === "failed") return isFailedStep(step);
      if (filter === "warning") return isWarningStep(step);
      if (filter === "score_changes") return hasScoreChange(step);
      return true;
    });
  }, [filter, steps]);

  const copyTrace = async () => {
    try {
      await navigator.clipboard.writeText(safeTraceJson(trace));
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  };

  return (
    <section className={cn("rounded-xl border border-border bg-white p-4 shadow-sm", className)}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold">{title}</h3>
          <p className="mt-1 text-xs text-muted-foreground">
            {steps.length ? `${filteredSteps.length} of ${steps.length} steps shown` : "No trace available."}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Select
            className="h-9"
            options={["all", "failed", "warning", "score_changes"]}
            value={filter}
            onChange={(event) => setFilter(event.target.value as DecisionTraceFilter)}
          />
          <Button
            type="button"
            onClick={() => setMode((current) => (current === "timeline" ? "accordion" : "timeline"))}
            className="h-9 bg-muted px-3 text-foreground hover:opacity-100"
          >
            <Filter className="h-4 w-4" />
            {mode === "timeline" ? "Timeline" : "Accordion"}
          </Button>
          <Button
            type="button"
            onClick={() => setDensity((current) => (current === "compact" ? "full" : "compact"))}
            className="h-9 bg-muted px-3 text-foreground hover:opacity-100"
          >
            {density === "compact" ? "Compact" : "Full detail"}
          </Button>
          <Button type="button" onClick={copyTrace} className="h-9">
            <Copy className="h-4 w-4" />
            {copied ? "Copied" : "Copy Trace JSON"}
          </Button>
        </div>
      </div>

      <div className="mt-4">
        {filteredSteps.length ? (
          <div className={cn(mode === "timeline" ? "space-y-3" : "space-y-2")}>
            {filteredSteps.map((step, index) => {
              const tone = stepTone(step);
              const name = normalizeStepName(step);
              const warnings = Array.isArray(step.warnings) ? step.warnings : [];
              const hasExpandedContent = density === "full" || warnings.length > 0 || Boolean(step.details);

              if (mode === "timeline") {
                return (
                  <details
                    key={`${name}-${index}`}
                    open={density === "full" || isFailedStep(step) || isWarningStep(step)}
                    className={cn("relative rounded-lg border p-4", tone)}
                  >
                    <summary className="cursor-pointer list-none">
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div className="flex items-center gap-3">
                          <span
                            className={cn(
                              "flex h-8 w-8 items-center justify-center rounded-full border text-xs font-bold",
                              isFailedStep(step)
                                ? "border-red-300 bg-red-100 text-red-700"
                                : isWarningStep(step)
                                  ? "border-amber-300 bg-amber-100 text-amber-700"
                                  : "border-emerald-300 bg-emerald-100 text-emerald-700",
                            )}
                          >
                            {index + 1}
                          </span>
                          <div>
                            <div className="flex flex-wrap items-center gap-2">
                              <span className="font-semibold">{name}</span>
                              {isFailedStep(step) ? (
                                <span className="inline-flex items-center gap-1 rounded-full border border-red-200 bg-red-50 px-2 py-0.5 text-[11px] font-semibold text-red-800">
                                  <TriangleAlert className="h-3 w-3" />
                                  failed
                                </span>
                              ) : null}
                              {!isFailedStep(step) && isWarningStep(step) ? (
                                <span className="inline-flex items-center gap-1 rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-[11px] font-semibold text-amber-800">
                                  <TriangleAlert className="h-3 w-3" />
                                  warning
                                </span>
                              ) : null}
                            </div>
                            <p className="mt-1 text-xs text-muted-foreground">
                              in {scoreLabel(step.input_score)} → out {scoreLabel(step.output_score)} · delta {scoreLabel(step.delta)}
                            </p>
                          </div>
                        </div>
                        <div className="text-xs text-muted-foreground">
                          {step.timestamp ?? ""}
                        </div>
                      </div>
                    </summary>

                    {hasExpandedContent ? (
                      <div className="mt-4 grid gap-3 md:grid-cols-2">
                        <Metric label="Input Score" value={scoreLabel(step.input_score)} />
                        <Metric label="Output Score" value={scoreLabel(step.output_score)} />
                        <Metric label="Delta" value={scoreLabel(step.delta)} />
                        <Metric label="Passed" value={step.passed === false ? "No" : step.passed === true ? "Yes" : "-"} />
                        <Metric label="Timestamp" value={step.timestamp ?? "-"} />
                        <Metric label="Warnings" value={warnings.length ? String(warnings.length) : "0"} />
                      </div>
                    ) : null}

                    {warnings.length ? (
                      <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
                        <p className="font-medium">Warnings</p>
                        <ul className="mt-1 space-y-1">
                          {warnings.map((warning) => (
                            <li key={warning}>• {warning}</li>
                          ))}
                        </ul>
                      </div>
                    ) : null}

                    <details className="mt-4 rounded-lg border border-border bg-background/40 p-3">
                      <summary className="cursor-pointer text-sm font-medium">Details JSON</summary>
                      <pre className="mt-2 max-h-72 overflow-auto rounded bg-muted p-3 text-xs">
                        {JSON.stringify(step.details ?? {}, null, 2)}
                      </pre>
                    </details>
                  </details>
                );
              }

              return (
                <details
                  key={`${name}-${index}`}
                  open={density === "full" || isFailedStep(step) || isWarningStep(step)}
                  className={cn("rounded-lg border p-4", tone)}
                >
                  <summary className="cursor-pointer list-none">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-semibold">{name}</span>
                          {isFailedStep(step) ? (
                            <span className="inline-flex items-center gap-1 rounded-full border border-red-200 bg-red-50 px-2 py-0.5 text-[11px] font-semibold text-red-800">
                              <TriangleAlert className="h-3 w-3" />
                              failed
                            </span>
                          ) : null}
                          {!isFailedStep(step) && isWarningStep(step) ? (
                            <span className="inline-flex items-center gap-1 rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-[11px] font-semibold text-amber-800">
                              <TriangleAlert className="h-3 w-3" />
                              warning
                            </span>
                          ) : null}
                        </div>
                        <p className="mt-1 text-xs text-muted-foreground">
                          in {scoreLabel(step.input_score)} → out {scoreLabel(step.output_score)} · delta {scoreLabel(step.delta)}
                        </p>
                      </div>
                      <div className="text-xs text-muted-foreground">{step.timestamp ?? ""}</div>
                    </div>
                  </summary>

                  {density === "full" ? (
                    <div className="mt-4 grid gap-3 md:grid-cols-2">
                      <Metric label="Input Score" value={scoreLabel(step.input_score)} />
                      <Metric label="Output Score" value={scoreLabel(step.output_score)} />
                      <Metric label="Delta" value={scoreLabel(step.delta)} />
                      <Metric label="Passed" value={step.passed === false ? "No" : step.passed === true ? "Yes" : "-"} />
                      <Metric label="Timestamp" value={step.timestamp ?? "-"} />
                      <Metric label="Warnings" value={warnings.length ? String(warnings.length) : "0"} />
                    </div>
                  ) : null}

                  {warnings.length ? (
                    <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
                      <p className="font-medium">Warnings</p>
                      <ul className="mt-1 space-y-1">
                        {warnings.map((warning) => (
                          <li key={warning}>• {warning}</li>
                        ))}
                      </ul>
                    </div>
                  ) : null}

                  {density === "full" || hasExpandedContent ? (
                    <details className="mt-4 rounded-lg border border-border bg-background/40 p-3">
                      <summary className="cursor-pointer text-sm font-medium">Details JSON</summary>
                      <pre className="mt-2 max-h-72 overflow-auto rounded bg-muted p-3 text-xs">
                        {JSON.stringify(step.details ?? {}, null, 2)}
                      </pre>
                    </details>
                  ) : null}
                </details>
              );
            })}
          </div>
        ) : (
          <div className="rounded-lg border border-dashed border-border p-6 text-sm text-muted-foreground">
            No decision trace available.
          </div>
        )}
      </div>
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border bg-background/50 p-3">
      <p className="text-[11px] uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="mt-1 text-sm font-medium text-foreground">{value}</p>
    </div>
  );
}
