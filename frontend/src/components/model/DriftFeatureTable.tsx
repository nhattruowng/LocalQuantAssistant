import { DataTable } from "@/components/tables/DataTable";
import { formatNumber } from "@/lib/utils";

export interface DriftFeatureRow {
  feature: string;
  psi?: number;
  driftScore?: number;
  trainMean?: number;
  recentMean?: number;
  severity?: string;
}

export function DriftFeatureTable({ rows, emptyText }: { rows: DriftFeatureRow[]; emptyText: string }) {
  return (
    <DataTable<DriftFeatureRow>
      rows={rows}
      emptyText={emptyText}
      columns={[
        { key: "feature", label: "Feature" },
        { key: "psi", label: "PSI", render: (value) => formatNumber(Number(value), 2) },
        { key: "driftScore", label: "Drift Score", render: (value) => formatNumber(Number(value), 2) },
        { key: "trainMean", label: "Train Mean", render: (value) => formatNumber(Number(value), 4) },
        { key: "recentMean", label: "Recent Mean", render: (value) => formatNumber(Number(value), 4) },
        { key: "severity", label: "Severity" },
      ]}
    />
  );
}
