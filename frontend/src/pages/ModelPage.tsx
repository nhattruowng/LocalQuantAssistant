import { RefreshCw } from "lucide-react";
import { Button } from "@/components/forms/Button";
import { PageHeader } from "@/components/layout/PageHeader";
import { CalibrationPanel } from "@/components/model/CalibrationPanel";
import { DriftFeatureTable, type DriftFeatureRow } from "@/components/model/DriftFeatureTable";
import { DriftReportCard } from "@/components/model/DriftReportCard";
import { ModelStatusCard } from "@/components/model/ModelStatusCard";
import { useAppSettings } from "@/hooks/useAppSettings";
import { useModelCalibrationQuery, useModelDriftQuery, useModelInfoQuery } from "@/hooks/useApiQueries";
import type { DriftReportPayload, ModelCalibration } from "@/types";

type ProbabilityRow = {
  label: string;
  raw?: number | null;
  calibrated?: number | null;
};

function toNumber(value: unknown): number | undefined {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return undefined;
}

function toRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  return value as Record<string, unknown>;
}

function extractProbabilityRows(calibration?: ModelCalibration | null): ProbabilityRow[] {
  const raw = toRecord(calibration?.raw_probabilities) ?? toRecord(calibration?.report?.raw_probabilities);
  const calibrated =
    toRecord(calibration?.calibrated_probabilities) ?? toRecord(calibration?.report?.calibrated_probabilities);
  const labels = new Set<string>([...Object.keys(raw ?? {}), ...Object.keys(calibrated ?? {})]);
  return [...labels].sort().map((label) => ({
    label,
    raw: toNumber(raw?.[label]),
    calibrated: toNumber(calibrated?.[label]),
  }));
}

function normalizeDriftFeatures(features?: DriftReportPayload["drifted_features"]): DriftFeatureRow[] {
  if (!Array.isArray(features)) return [];
  return features
    .map((item, index) => {
      const row = toRecord(item);
      if (!row) return null;
      return {
        feature: String(row.feature ?? row.name ?? row.column ?? `feature_${index + 1}`),
        psi: toNumber(row.psi ?? row.population_stability_index),
        driftScore: toNumber(row.drift_score ?? row.driftScore ?? row.score),
        trainMean: toNumber(row.train_mean ?? row.baseline_mean ?? row.mean_train),
        recentMean: toNumber(row.recent_mean ?? row.current_mean ?? row.mean_recent),
        severity: String(row.severity ?? row.status ?? row.level ?? ""),
      };
    })
    .filter((row): row is DriftFeatureRow => Boolean(row))
    .sort((left, right) => (right.driftScore ?? right.psi ?? 0) - (left.driftScore ?? left.psi ?? 0));
}

export function ModelPage() {
  const { symbol, timeframe } = useAppSettings();
  const modelQuery = useModelInfoQuery();
  const calibrationQuery = useModelCalibrationQuery();
  const driftQuery = useModelDriftQuery(200);

  const model = modelQuery.data;
  const calibration = calibrationQuery.data;
  const driftReport = model?.drift_report ?? driftQuery.data?.report ?? null;
  const probabilityRows = extractProbabilityRows(calibration);
  const driftFeatures = normalizeDriftFeatures(driftReport?.drifted_features);

  return (
    <div>
      <PageHeader
        title="Model Research Dashboard"
        description="Track model version, calibration quality, and drift behavior."
        actions={
          <Button onClick={() => driftQuery.refetch()} disabled={driftQuery.isFetching}>
            <RefreshCw className={`h-4 w-4 ${driftQuery.isFetching ? "animate-spin" : ""}`} />
            Refresh Drift
          </Button>
        }
      />

      <ModelStatusCard model={model} symbol={symbol} timeframe={timeframe} />

      <div className="mt-4 grid gap-4 xl:grid-cols-2">
        <CalibrationPanel calibration={calibration} probabilities={probabilityRows} />
        <DriftReportCard report={driftReport} />
      </div>

      <section className="mt-4 rounded-lg border border-border bg-white p-4 shadow-sm">
        <h3 className="mb-3 text-sm font-semibold">Drifted Features</h3>
        <DriftFeatureTable rows={driftFeatures} emptyText="No drifted features detected." />
      </section>

      <section className="mt-4 rounded-lg border border-border bg-white p-4 shadow-sm">
        <details>
          <summary className="cursor-pointer text-sm font-semibold">Raw model payload</summary>
          <pre className="mt-3 max-h-80 overflow-auto rounded bg-muted p-3 text-xs">
            {JSON.stringify(
              {
                model,
                calibration,
                drift: driftQuery.data,
              },
              null,
              2,
            )}
          </pre>
        </details>
      </section>
    </div>
  );
}
