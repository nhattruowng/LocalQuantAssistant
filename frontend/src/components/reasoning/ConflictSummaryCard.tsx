import type { TradeSetup } from "@/types";
import { AlertTriangle, ShieldCheck } from "lucide-react";
import { resolveSignalIntelligence } from "@/components/reasoning/signalIntelligence";

export function ConflictSummaryCard({ setup }: { setup?: TradeSetup | null }) {
  const snapshot = resolveSignalIntelligence(setup);
  const level = snapshot.conflictLevel.toUpperCase();
  const highConflict = level === "HIGH";
  const details = snapshot.reasoning?.conflict_details ?? setup?.conflict_details ?? null;
  const warnings = snapshot.reasoning?.warnings ?? [];

  return (
    <section className={`rounded-2xl border p-5 shadow-sm ${highConflict ? "border-red-300 bg-red-50" : "border-border bg-white"}`}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Conflict Summary</p>
          <h3 className={`mt-2 text-xl font-semibold ${highConflict ? "text-red-900" : "text-foreground"}`}>
            {level || "NONE"}
          </h3>
        </div>
        {highConflict ? (
          <span className="inline-flex items-center gap-1 rounded-full border border-red-300 bg-white px-3 py-1 text-xs font-semibold text-red-800">
            <AlertTriangle className="h-3.5 w-3.5" />
            Action required
          </span>
        ) : (
          <span className="inline-flex items-center gap-1 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-800">
            <ShieldCheck className="h-3.5 w-3.5" />
            No high conflict
          </span>
        )}
      </div>

      {highConflict ? (
        <p className="mt-3 text-sm text-red-900">
          High conflict is strong enough to reduce confidence or force a WAIT decision.
        </p>
      ) : (
        <p className="mt-3 text-sm text-muted-foreground">
          No high-severity evidence conflict is present in the current payload.
        </p>
      )}

      {warnings.length ? (
        <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
          <p className="font-semibold">Conflict warnings</p>
          <ul className="mt-2 space-y-1">
            {warnings.slice(0, 5).map((warning) => (
              <li key={warning}>• {warning}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {details ? (
        <details className="mt-4 rounded-xl border border-border bg-white/70 p-3">
          <summary className="cursor-pointer text-sm font-medium">Raw conflict details</summary>
          <pre className="mt-2 max-h-56 overflow-auto rounded bg-muted p-3 text-xs">
            {JSON.stringify(details, null, 2)}
          </pre>
        </details>
      ) : null}
    </section>
  );
}
