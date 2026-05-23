import { AlertTriangle } from "lucide-react";
import { MetricCard } from "@/components/cards/MetricCard";
import type { DriftReportPayload } from "@/types";
import { formatNumber } from "@/lib/utils";

export function DriftReportCard({ report }: { report?: DriftReportPayload | null }) {
  const high = String(report?.drift_level ?? "").toUpperCase() === "HIGH";

  return (
    <section className="rounded-lg border border-border bg-white p-4 shadow-sm">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h3 className="text-sm font-semibold">Drift Report</h3>
        <span className="rounded-full bg-muted px-3 py-1 text-xs text-muted-foreground">{report?.drift_level ?? "NONE"}</span>
      </div>
      {high ? (
        <div className="mb-4 flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <p>High drift detected. Recommended action: {report?.recommended_action ?? "WARN"}.</p>
        </div>
      ) : null}
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <MetricCard label="Drift Score" value={formatNumber(report?.drift_score ?? null, 2)} />
        <MetricCard label="Prediction Shift" value={formatNumber(extractScore(report?.prediction_shift), 2)} />
        <MetricCard label="Calibration Shift" value={formatNumber(extractScore(report?.calibration_shift), 2)} />
        <MetricCard label="Regime Shift" value={formatNumber(extractScore(report?.regime_shift), 2)} />
        <MetricCard label="Recommended Action" value={report?.recommended_action ?? "-"} />
        <MetricCard label="Drifted Features" value={String(report?.drifted_features?.length ?? 0)} />
      </div>
    </section>
  );
}

function extractScore(input: unknown): number | null {
  if (!input || typeof input !== "object" || Array.isArray(input)) return null;
  const record = input as Record<string, unknown>;
  const candidate = record.score ?? record.drift_score ?? record.shift_score ?? record.distribution_shift;
  return typeof candidate === "number" ? candidate : Number(candidate);
}
