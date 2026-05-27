import { useMemo, useState } from "react";
import { Copy, Filter } from "lucide-react";
import { Button } from "@/components/forms/Button";
import { Select } from "@/components/forms/Select";
import { DecisionStepItem } from "@/components/reasoning/DecisionStepItem";
import { cn } from "@/lib/utils";
import type { DecisionStepPayload, DecisionTracePayload } from "@/types";

export type DecisionTraceFilter = "all" | "failed" | "warning" | "score_changes";
export type DecisionTraceMode = "timeline" | "accordion";
export type DecisionTraceDensity = "compact" | "full";

interface DecisionTraceViewerProps {
  trace?: DecisionTracePayload | null;
  title?: string;
  className?: string;
}

const FILTER_OPTIONS: Array<{ value: DecisionTraceFilter; label: string }> = [
  { value: "all", label: "All" },
  { value: "failed", label: "Failed" },
  { value: "warning", label: "Warning" },
  { value: "score_changes", label: "Score Changes" },
];

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
            options={FILTER_OPTIONS.map((option) => option.label)}
            aria-label="Decision trace filter"
            value={FILTER_OPTIONS.find((option) => option.value === filter)?.label ?? "All"}
            onChange={(event) => {
              const selected = FILTER_OPTIONS.find((option) => option.label === event.target.value);
              setFilter(selected?.value ?? "all");
            }}
          />
          <Button
            type="button"
            onClick={() => setMode((current) => (current === "timeline" ? "accordion" : "timeline"))}
            className="h-9 bg-muted px-3 text-foreground hover:opacity-100"
            aria-label="Toggle trace mode"
          >
            <Filter className="h-4 w-4" />
            {mode === "timeline" ? "Timeline mode" : "Accordion mode"}
          </Button>
          <Button
            type="button"
            onClick={() => setDensity((current) => (current === "compact" ? "full" : "compact"))}
            className="h-9 bg-muted px-3 text-foreground hover:opacity-100"
            aria-label="Toggle detail mode"
          >
            {density === "compact" ? "Compact mode" : "Full detail mode"}
          </Button>
          <Button type="button" onClick={copyTrace} className="h-9" aria-label="Copy trace json">
            <Copy className="h-4 w-4" />
            {copied ? "Copied" : "Copy Trace JSON"}
          </Button>
        </div>
      </div>

      <div className="mt-4">
        {filteredSteps.length ? (
          <div className={cn(mode === "timeline" ? "space-y-3" : "space-y-2")}>
            {filteredSteps.map((step, index) => (
              <DecisionStepItem
                key={`${step.step_name ?? "step"}-${index}`}
                step={step}
                index={index}
                mode={mode}
                density={density}
              />
            ))}
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
