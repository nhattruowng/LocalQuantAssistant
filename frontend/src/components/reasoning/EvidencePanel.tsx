import { useMemo, useState } from "react";
import { EvidenceItem } from "@/components/reasoning/EvidenceItem";
import { cn } from "@/lib/utils";
import type { ReasoningEvidencePayload } from "@/types";

type EvidenceTab = "FOR" | "AGAINST" | "WARNINGS";

export function EvidencePanel({
  evidenceFor,
  evidenceAgainst,
  warnings,
  className,
}: {
  evidenceFor?: ReasoningEvidencePayload[] | null;
  evidenceAgainst?: ReasoningEvidencePayload[] | null;
  warnings?: ReasoningEvidencePayload[] | null;
  className?: string;
}) {
  const [tab, setTab] = useState<EvidenceTab>("FOR");

  const items = useMemo(() => {
    const selected = tab === "AGAINST" ? evidenceAgainst : tab === "WARNINGS" ? warnings : evidenceFor;
    return [...(selected ?? [])].sort((left, right) => {
      const criticalDelta = Number(Boolean(right.is_critical)) - Number(Boolean(left.is_critical));
      if (criticalDelta !== 0) return criticalDelta;
      return Math.abs(Number(right.impact_on_score ?? right.score ?? 0)) - Math.abs(Number(left.impact_on_score ?? left.score ?? 0));
    });
  }, [evidenceAgainst, evidenceFor, tab, warnings]);

  const tabs: Array<{ id: EvidenceTab; label: string; count: number }> = [
    { id: "FOR", label: "Evidence For", count: evidenceFor?.length ?? 0 },
    { id: "AGAINST", label: "Evidence Against", count: evidenceAgainst?.length ?? 0 },
    { id: "WARNINGS", label: "Warnings", count: warnings?.length ?? 0 },
  ];

  return (
    <section className={cn("rounded-2xl border border-border bg-white p-5 shadow-sm", className)}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Evidence Panel</p>
          <h3 className="mt-1 text-lg font-semibold text-foreground">Reasoning Evidence</h3>
        </div>
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-2" role="tablist" aria-label="Evidence tabs">
        {tabs.map((item) => {
          const active = tab === item.id;
          return (
            <button
              key={item.id}
              type="button"
              role="tab"
              aria-selected={active}
              onClick={() => setTab(item.id)}
              className={cn(
                "rounded-full border px-3 py-2 text-xs font-semibold uppercase tracking-wide transition",
                active
                  ? "border-slate-900 bg-slate-900 text-white"
                  : "border-border bg-muted text-muted-foreground hover:text-foreground",
              )}
            >
              {item.label} ({item.count})
            </button>
          );
        })}
      </div>
      <div className="mt-4 space-y-3">
        {items.length ? (
          items.map((item, index) => <EvidenceItem key={`${item.name ?? tab}-${index}`} evidence={item} />)
        ) : (
          <div className="rounded-xl border border-dashed border-border p-6 text-sm text-muted-foreground">
            No evidence available for this tab.
          </div>
        )}
      </div>
    </section>
  );
}
