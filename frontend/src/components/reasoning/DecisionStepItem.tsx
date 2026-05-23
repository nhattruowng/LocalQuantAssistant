import { TriangleAlert } from "lucide-react";
import { cn, formatNumber } from "@/lib/utils";
import type { DecisionStepPayload } from "@/types";

export function DecisionStepItem({ step, index }: { step: DecisionStepPayload; index: number }) {
  const warnings = Array.isArray(step.warnings) ? step.warnings : [];
  const failed = step.passed === false;
  const warned = warnings.length > 0;

  return (
    <details
      open={failed || warned}
      className={cn(
        "rounded-lg border p-4",
        failed ? "border-red-200 bg-red-50" : warned ? "border-amber-200 bg-amber-50" : "border-border bg-white",
      )}
    >
      <summary className="cursor-pointer list-none">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="flex h-8 w-8 items-center justify-center rounded-full border border-border bg-white text-xs font-bold">
                {index + 1}
              </span>
              <span className="font-semibold text-foreground">{step.step_name}</span>
              {failed ? (
                <span className="inline-flex items-center gap-1 rounded-full border border-red-200 bg-red-100 px-2 py-0.5 text-[11px] font-semibold text-red-800">
                  <TriangleAlert className="h-3 w-3" />
                  failed
                </span>
              ) : null}
              {!failed && warned ? (
                <span className="inline-flex items-center gap-1 rounded-full border border-amber-200 bg-amber-100 px-2 py-0.5 text-[11px] font-semibold text-amber-800">
                  <TriangleAlert className="h-3 w-3" />
                  warning
                </span>
              ) : null}
            </div>
            <p className="mt-1 text-xs text-muted-foreground">
              in {formatNumber(step.input_score ?? null, 2)} → out {formatNumber(step.output_score ?? null, 2)} · delta {formatNumber(step.delta ?? null, 2)}
            </p>
          </div>
          {step.timestamp ? <div className="text-xs text-muted-foreground">{step.timestamp}</div> : null}
        </div>
      </summary>
      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <Metric label="Input Score" value={formatNumber(step.input_score ?? null, 2)} />
        <Metric label="Output Score" value={formatNumber(step.output_score ?? null, 2)} />
        <Metric label="Delta" value={formatNumber(step.delta ?? null, 2)} />
        <Metric label="Passed" value={step.passed === false ? "No" : step.passed === true ? "Yes" : "-"} />
        <Metric label="Warnings" value={String(warnings.length)} />
        <Metric label="Timestamp" value={step.timestamp ?? "-"} />
      </div>
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
        <pre className="mt-2 max-h-72 overflow-auto rounded bg-muted p-3 text-xs">{JSON.stringify(step.details ?? {}, null, 2)}</pre>
      </details>
    </details>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border bg-white p-3">
      <p className="text-xs uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="mt-1 text-sm font-medium text-foreground">{value}</p>
    </div>
  );
}
