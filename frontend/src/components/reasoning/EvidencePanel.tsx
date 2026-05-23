import { useMemo, useState } from "react";
import { EvidenceItem } from "@/components/reasoning/EvidenceItem";
import { cn } from "@/lib/utils";
import type { ReasoningEvidencePayload } from "@/types";

type EvidenceTab = "FOR" | "AGAINST" | "WARNINGS";

export function EvidencePanel({
  evidenceFor,
  evidenceAgainst,
  warnings,
}: {
  evidenceFor?: ReasoningEvidencePayload[] | null;
  evidenceAgainst?: ReasoningEvidencePayload[] | null;
  warnings?: ReasoningEvidencePayload[] | null;
}) {
  const [tab, setTab] = useState<EvidenceTab>("FOR");

  const items = useMemo(() => {
    if (tab === "AGAINST") return evidenceAgainst ?? [];
    if (tab === "WARNINGS") return warnings ?? [];
    return evidenceFor ?? [];
  }, [evidenceAgainst, evidenceFor, tab, warnings]);

  const tabs: Array<{ id: EvidenceTab; label: string; count: number }> = [
    { id: "FOR", label: "Evidence For", count: evidenceFor?.length ?? 0 },
    { id: "AGAINST", label: "Evidence Against", count: evidenceAgainst?.length ?? 0 },
    { id: "WARNINGS", label: "Warnings", count: warnings?.length ?? 0 },
  ];

  return (
    <section className="rounded-xl border border-border bg-white p-4 shadow-sm">
      <div className="flex flex-wrap items-center gap-2">
        {tabs.map((item) => {
          const active = tab === item.id;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => setTab(item.id)}
              className={cn(
                "rounded-full border px-3 py-1 text-xs font-medium transition",
                active ? "border-primary bg-primary text-primary-foreground" : "border-border bg-muted text-muted-foreground",
              )}
            >
              {item.label} ({item.count})
            </button>
          );
        })}
      </div>
      <div className="mt-4 space-y-3">
        {items.length ? items.map((item, index) => <EvidenceItem key={`${item.name ?? "evidence"}-${index}`} evidence={item} />) : <p className="text-sm text-muted-foreground">No evidence available.</p>}
      </div>
    </section>
  );
}
