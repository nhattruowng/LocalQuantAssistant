import { DataTable } from "@/components/tables/DataTable";
import { shortDate } from "@/lib/utils";
import type { RiskStatus } from "@/types";

type RiskEvent = NonNullable<RiskStatus["events"]>[number];

export function RiskEventsTable({ events }: { events?: RiskEvent[] | null }) {
  const rows = (events ?? []).map((event) => ({
    timestamp: event.timestamp,
    event_type: event.event_type ?? event.state ?? "EVENT",
    severity: event.severity ?? inferSeverity(event.state),
    message: event.message ?? event.reason ?? "-",
    affected_symbol: event.affected_symbol ?? event.symbol ?? "-",
    action_taken: event.action_taken ?? inferAction(event.state),
  }));

  return (
    <DataTable
      rows={rows}
      emptyText="No risk events recorded yet."
      columns={[
        { key: "timestamp", label: "Timestamp", render: (value) => shortDate(String(value ?? "-")) },
        { key: "event_type", label: "Event Type" },
        { key: "severity", label: "Severity" },
        { key: "message", label: "Message" },
        { key: "affected_symbol", label: "Affected Symbol" },
        { key: "action_taken", label: "Action Taken" },
      ]}
    />
  );
}

function inferSeverity(state?: string) {
  const normalized = String(state ?? "").toUpperCase();
  if (normalized.includes("BLOCK")) return "HIGH";
  if (normalized.includes("COOLDOWN")) return "MEDIUM";
  if (normalized.includes("WARN")) return "MEDIUM";
  return "LOW";
}

function inferAction(state?: string) {
  const normalized = String(state ?? "").toUpperCase();
  if (normalized.includes("BLOCK")) return "Blocked new entries";
  if (normalized.includes("COOLDOWN")) return "Cooldown enforced";
  if (normalized.includes("WARN")) return "Warned trader";
  return "Continue";
}
