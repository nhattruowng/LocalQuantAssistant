import { useMemo } from "react";
import { AlertTriangle, Brain, RefreshCw } from "lucide-react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { MetricCard } from "@/components/cards/MetricCard";
import { Button } from "@/components/forms/Button";
import { PageHeader } from "@/components/layout/PageHeader";
import { useAppSettings } from "@/hooks/useAppSettings";
import { useActions, useModelCalibrationQuery, useModelDriftQuery, useModelInfoQuery } from "@/hooks/useApiQueries";
import { formatNumber } from "@/lib/utils";
import type { DriftReportPayload, ModelCalibration, ModelInfo } from "@/types";

type ProbabilityRow = {
  label: string;
  raw?: number | null;
  calibrated?: number | null;
};

type DriftFeatureRow = {
  feature: string;
  psi?: number;
  driftScore?: number;
  trainMean?: number;
  recentMean?: number;
  trainStd?: number;
  recentStd?: number;
  severity?: string;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function toNumber(value: unknown): number | undefined {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return undefined;
}

function formatDecimal(value: unknown, digits = 2): string {
  const num = toNumber(value);
  return num === undefined ? "-" : formatNumber(num, digits);
}

function formatPercent(value: unknown, digits = 1): string {
  const num = toNumber(value);
  if (num === undefined) return "-";
  const percent = Math.abs(num) <= 1 ? num * 100 : num;
  return `${percent.toFixed(digits)}%`;
}

function pickString(source: unknown, keys: string[], fallback = "-"): string {
  if (!isRecord(source)) return fallback;
  for (const key of keys) {
    const value = source[key];
    if (typeof value === "string" && value.trim()) return value;
  }
  return fallback;
}

function pickNumber(source: unknown, keys: string[]): number | undefined {
  if (!isRecord(source)) return undefined;
  for (const key of keys) {
    const value = toNumber(source[key]);
    if (value !== undefined) return value;
  }
  return undefined;
}

function searchDeep(source: unknown, predicate: (key: string, value: unknown) => boolean, depth = 0): unknown {
  if (!isRecord(source) || depth > 3) return undefined;
  for (const [key, value] of Object.entries(source)) {
    if (predicate(key, value)) return value;
    if (isRecord(value)) {
      const nested = searchDeep(value, predicate, depth + 1);
      if (nested !== undefined) return nested;
    }
  }
  return undefined;
}

function coerceProbabilityMap(value: unknown): Record<string, number> | undefined {
  if (!isRecord(value)) {
    const numeric = toNumber(value);
    return numeric === undefined ? undefined : { probability: numeric };
  }

  const entries = Object.entries(value)
    .map(([key, raw]) => [key, toNumber(raw)] as const)
    .filter(([, num]) => num !== undefined) as Array<readonly [string, number]>;

  if (!entries.length) return undefined;

  return entries.reduce<Record<string, number>>((acc, [key, num]) => {
    acc[key] = num;
    return acc;
  }, {});
}

function extractProbabilityMap(source: unknown, keys: string[]): Record<string, number> | undefined {
  const direct = searchDeep(source, (key, value) => keys.some((candidate) => key.toLowerCase().includes(candidate.toLowerCase())) && (isRecord(value) || toNumber(value) !== undefined));
  return coerceProbabilityMap(direct);
}

function buildProbabilityComparison(info?: ModelInfo, calibrationInfo?: ModelCalibration): ProbabilityRow[] {
  const rawMap =
    extractProbabilityMap(calibrationInfo, ["raw_probabilities", "probabilities_raw", "raw_probability", "rawprobability"]) ??
    extractProbabilityMap(calibrationInfo?.report, ["raw_probabilities", "probabilities_raw", "raw_probability", "rawprobability"]) ??
    extractProbabilityMap(info?.metrics, ["raw_probabilities", "probabilities_raw", "raw_probability", "rawprobability"]);

  const calibratedMap =
    extractProbabilityMap(calibrationInfo, ["calibrated_probabilities", "probabilities_calibrated", "calibrated_probability", "calibratedprobability"]) ??
    extractProbabilityMap(calibrationInfo?.report, ["calibrated_probabilities", "probabilities_calibrated", "calibrated_probability", "calibratedprobability"]) ??
    extractProbabilityMap(info?.metrics, ["calibrated_probabilities", "probabilities_calibrated", "calibrated_probability", "calibratedprobability"]);

  if (!rawMap && !calibratedMap) return [];

  const labels = new Set<string>([...(rawMap ? Object.keys(rawMap) : []), ...(calibratedMap ? Object.keys(calibratedMap) : [])]);
  if (!labels.size) return [];

  return Array.from(labels)
    .sort((left, right) => left.localeCompare(right))
    .map((label) => ({
      label,
      raw: rawMap?.[label],
      calibrated: calibratedMap?.[label],
    }));
}

function normalizeFeatureDriftRows(features: DriftReportPayload["drifted_features"]): DriftFeatureRow[] {
  if (!Array.isArray(features)) return [];

  return features
    .map((item, index) => {
      if (!isRecord(item)) return null;

      const feature =
        pickString(item, ["feature", "name", "column", "field", "metric"], `feature_${index}`) ||
        `feature_${index}`;

      return {
        feature,
        psi: pickNumber(item, ["psi", "population_stability_index"]),
        driftScore: pickNumber(item, ["drift_score", "driftScore", "score"]),
        trainMean: pickNumber(item, ["train_mean", "baseline_mean", "mean_train"]),
        recentMean: pickNumber(item, ["recent_mean", "current_mean", "mean_recent"]),
        trainStd: pickNumber(item, ["train_std", "baseline_std", "std_train"]),
        recentStd: pickNumber(item, ["recent_std", "current_std", "std_recent"]),
        severity: pickString(item, ["severity", "status", "level"], ""),
      };
    })
    .filter(Boolean)
    .sort((left, right) => (right?.driftScore ?? right?.psi ?? 0) - (left?.driftScore ?? left?.psi ?? 0)) as DriftFeatureRow[];
}

function normalizeDistribution(input: unknown): { rows: Array<Record<string, string | number>>; seriesKeys: string[] } {
  if (Array.isArray(input)) {
    const rows = input
      .map((item, index) => {
        if (!isRecord(item)) return null;
        const label = pickString(item, ["label", "name", "category", "key", "state", "regime", "signal"], `item_${index}`);
        const numericEntries = Object.entries(item)
          .filter(([key, value]) => key !== "label" && key !== "name" && key !== "category" && key !== "key" && key !== "state" && key !== "regime" && key !== "signal" && toNumber(value) !== undefined)
          .map(([key, value]) => [key, toNumber(value) as number] as const);

        if (!numericEntries.length) return null;

        const row: Record<string, string | number> = { label };
        numericEntries.forEach(([key, value]) => {
          row[key] = value;
        });
        return row;
      })
      .filter(Boolean) as Array<Record<string, string | number>>;

    const seriesKeys = Array.from(new Set(rows.flatMap((row) => Object.keys(row).filter((key) => key !== "label"))));
    return { rows, seriesKeys };
  }

  if (!isRecord(input)) return { rows: [], seriesKeys: [] };

  const numericEntries = Object.entries(input)
    .filter(([, value]) => toNumber(value) !== undefined)
    .map(([key, value]) => [key, toNumber(value) as number] as const);

  if (numericEntries.length) {
    return {
      rows: numericEntries.map(([label, value]) => ({
        label,
        value,
      })),
      seriesKeys: ["value"],
    };
  }

  const nestedEntries = Object.entries(input).filter(([, value]) => isRecord(value));
  if (!nestedEntries.length) return { rows: [], seriesKeys: [] };

  const labels = new Set<string>();
  nestedEntries.forEach(([, nested]) => {
    Object.entries(nested as Record<string, unknown>).forEach(([label, value]) => {
      if (toNumber(value) !== undefined) labels.add(label);
    });
  });

  if (!labels.size) return { rows: [], seriesKeys: [] };

  const rows = Array.from(labels).sort().map((label) => {
    const row: Record<string, string | number> = { label };
    nestedEntries.forEach(([seriesKey, nested]) => {
      row[seriesKey] = toNumber((nested as Record<string, unknown>)[label]) ?? 0;
    });
    return row;
  });

  return {
    rows,
    seriesKeys: nestedEntries.map(([key]) => key),
  };
}

function probabilitySnapshotRow(row: ProbabilityRow) {
  return [
    row.label,
    row.raw === undefined || row.raw === null ? "-" : formatPercent(row.raw, 1),
    row.calibrated === undefined || row.calibrated === null ? "-" : formatPercent(row.calibrated, 1),
  ] as const;
}

function DistributionChart({
  title,
  data,
  emptyLabel,
}: {
  title: string;
  data: { rows: Array<Record<string, string | number>>; seriesKeys: string[] };
  emptyLabel: string;
}) {
  const palette = ["#2563eb", "#0f766e", "#d97706", "#7c3aed", "#64748b"];

  return (
    <section className="rounded-lg border border-border bg-white p-4">
      <h3 className="mb-4 text-sm font-semibold text-foreground">{title}</h3>
      {data.rows.length ? (
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data.rows} margin={{ top: 8, right: 8, left: 8, bottom: 8 }}>
              <CartesianGrid stroke="#e5e7eb" vertical={false} />
              <XAxis dataKey="label" tick={{ fontSize: 12 }} interval={0} />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip formatter={(value) => formatNumber(Number(value), 2)} />
              {data.seriesKeys.map((seriesKey, index) => (
                <Bar
                  key={seriesKey}
                  dataKey={seriesKey}
                  fill={palette[index % palette.length]}
                  radius={[4, 4, 0, 0]}
                />
              ))}
            </BarChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">{emptyLabel}</p>
      )}
    </section>
  );
}

export function ModelPage() {
  const { symbol, timeframe } = useAppSettings();
  const model = useModelInfoQuery();
  const calibration = useModelCalibrationQuery();
  const drift = useModelDriftQuery(200);
  const actions = useActions();

  const info = model.data;
  const calibrationInfo = calibration.data;
  const driftReport = info?.drift_report ?? drift.data?.report;
  const resolvedSymbol = info?.symbol ?? calibrationInfo?.symbol ?? drift.data?.symbol ?? symbol;
  const resolvedTimeframe = info?.timeframe ?? calibrationInfo?.timeframe ?? drift.data?.timeframe ?? timeframe;
  const modelId = info?.model_id ?? drift.data?.model_id ?? "-";
  const modelVersion = info?.model_version ?? drift.data?.model_version ?? "-";

  const validationMethod =
    info?.validation_method ||
    pickString(info?.metrics, ["validation_method", "validationMethod", "validation"], "") ||
    pickString(calibrationInfo?.report, ["validation_method", "validationMethod"], "") ||
    "time_split";

  const probabilitySource =
    info?.probability_source ||
    pickString(info?.metrics, ["probability_source", "probabilitySource"], "") ||
    (calibrationInfo?.calibration_enabled ? "calibrated" : "raw");

  const modelScope = info?.model_scope ?? pickString(info?.metrics, ["model_scope", "modelScope"], "global");
  const trainedAt = info?.trained_at ?? calibrationInfo?.trained_at ?? "-";
  const driftLevel = driftReport?.drift_level ?? "NONE";
  const driftScore = driftReport?.drift_score;
  const driftedFeatures = normalizeFeatureDriftRows(driftReport?.drifted_features);
  const predictionChart = normalizeDistribution(driftReport?.prediction_shift);
  const regimeChart = normalizeDistribution(driftReport?.regime_shift);
  const probabilityRows = useMemo(() => buildProbabilityComparison(info, calibrationInfo), [info, calibrationInfo]);
  const calibrationEnabled = calibrationInfo?.calibration_enabled ?? info?.calibration_enabled ?? false;
  const calibrationStatus = calibrationEnabled ? "Enabled" : "Disabled";
  const highDrift = driftLevel === "HIGH";

  const brierScore =
    calibrationInfo?.brier_score_after ??
    calibrationInfo?.brier_score_before ??
    info?.brier_score_after ??
    info?.brier_score_before;
  const logLoss =
    calibrationInfo?.log_loss_after ??
    calibrationInfo?.log_loss_before ??
    info?.log_loss_after ??
    info?.log_loss_before;

  const predictionShiftScore = pickNumber(driftReport?.prediction_shift, ["score", "drift_score", "shift_score", "distribution_shift"]);
  const calibrationShiftScore = pickNumber(driftReport?.calibration_shift, ["score", "drift_score", "shift_score"]);
  const regimeShiftScore = pickNumber(driftReport?.regime_shift, ["score", "drift_score", "shift_score"]);

  return (
    <div>
      <PageHeader
        title="Model"
        description="Model status, calibration, and drift diagnostics."
        actions={(
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => actions.trainModel.mutate()} disabled={actions.trainModel.isPending}>
              <Brain className="h-4 w-4" />
              {actions.trainModel.isPending ? "Training..." : "Train Model"}
            </Button>
            <Button
              onClick={() => drift.refetch()}
              disabled={drift.isFetching}
              className="bg-muted text-foreground hover:bg-muted/80"
            >
              <RefreshCw className={`h-4 w-4 ${drift.isFetching ? "animate-spin" : ""}`} />
              Refresh Drift
            </Button>
          </div>
        )}
      />

      {model.isLoading ? (
        <div className="mb-4 rounded-lg border border-border bg-white p-4 text-sm text-muted-foreground">
          Loading model metadata...
        </div>
      ) : null}

      {model.isError ? (
        <div className="mb-4 rounded-lg border border-dashed border-border bg-white p-6 text-sm text-muted-foreground">
          No model metadata available yet.
        </div>
      ) : null}

      {highDrift ? (
        <div className="mb-4 flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <div>
            <p className="font-medium">High drift detected</p>
            <p className="mt-1">
              This model may be stale. Recommended action: {driftReport?.recommended_action ?? "WARN"}.
            </p>
          </div>
        </div>
      ) : null}

      <section className="rounded-lg border border-border bg-white p-4">
        <div className="mb-4 flex items-center justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold text-foreground">Model Status</h3>
            <p className="text-xs text-muted-foreground">
              Active context: {resolvedSymbol} / {resolvedTimeframe}
            </p>
          </div>
        </div>
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          <MetricCard label="Model ID" value={modelId} />
          <MetricCard label="Model Version" value={modelVersion} />
          <MetricCard label="Model Scope" value={modelScope} />
          <MetricCard label="Symbol" value={resolvedSymbol ?? "-"} />
          <MetricCard label="Timeframe" value={resolvedTimeframe ?? "-"} />
          <MetricCard label="Trained At" value={trainedAt} />
          <MetricCard label="Validation Method" value={validationMethod || "time_split"} />
          <MetricCard label="Calibration Enabled" value={calibrationEnabled ? "Yes" : "No"} />
          <MetricCard label="Probability Source" value={probabilitySource} />
        </div>
      </section>

      <section className="mt-4 rounded-lg border border-border bg-white p-4">
        <div className="mb-4 flex items-center justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold text-foreground">Calibration</h3>
            <p className="text-xs text-muted-foreground">
              Calibration status and probability stability.
            </p>
          </div>
          <span className="rounded-full bg-muted px-3 py-1 text-xs text-muted-foreground">
            {calibrationStatus}
          </span>
        </div>

        {!calibrationEnabled ? (
          <div className="mb-4 flex items-start gap-3 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
            <p>Calibration is not enabled for this model yet.</p>
          </div>
        ) : null}

        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <MetricCard label="Brier Score" value={formatDecimal(brierScore, 2)} />
          <MetricCard label="Log Loss" value={formatDecimal(logLoss, 2)} />
          <MetricCard label="Calibration Status" value={calibrationStatus} />
          <MetricCard label="Calibration Method" value={calibrationInfo?.calibration_method ?? info?.calibration_method ?? "-"} />
        </div>

        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <section className="rounded-lg border border-border p-4">
            <h4 className="text-sm font-medium text-foreground">Raw vs Calibrated Probability</h4>
            {probabilityRows.length ? (
              <div className="mt-3 overflow-x-auto">
                <table className="min-w-full text-left text-sm">
                  <thead className="text-xs uppercase tracking-wide text-muted-foreground">
                    <tr>
                      <th className="py-2 pr-4">Signal</th>
                      <th className="py-2 pr-4">Raw</th>
                      <th className="py-2 pr-4">Calibrated</th>
                    </tr>
                  </thead>
                  <tbody>
                    {probabilityRows.map((row) => {
                      const [label, raw, calibrated] = probabilitySnapshotRow(row);
                      return (
                        <tr key={label} className="border-t border-border">
                          <td className="py-2 pr-4 font-medium text-foreground">{label}</td>
                          <td className="py-2 pr-4 text-muted-foreground">{raw}</td>
                          <td className="py-2 pr-4 text-muted-foreground">{calibrated}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="mt-3 text-sm text-muted-foreground">No raw vs calibrated probability data available.</p>
            )}
          </section>

          <section className="rounded-lg border border-border p-4">
            <h4 className="text-sm font-medium text-foreground">Calibration Notes</h4>
            <div className="mt-3 grid gap-3 text-sm text-muted-foreground">
              <div>
                <span className="font-medium text-foreground">Status:</span> {calibrationStatus}
              </div>
              <div>
                <span className="font-medium text-foreground">Method:</span> {calibrationInfo?.calibration_method ?? "-"}
              </div>
              <div>
                <span className="font-medium text-foreground">Source:</span> {probabilitySource}
              </div>
            </div>
            <details className="mt-4 rounded-md border border-border p-3">
              <summary className="cursor-pointer text-sm font-medium text-foreground">Calibration payload</summary>
              <pre className="mt-3 max-h-64 overflow-auto rounded bg-muted p-3 text-xs text-foreground">
                {JSON.stringify(calibrationInfo ?? {}, null, 2)}
              </pre>
            </details>
          </section>
        </div>
      </section>

      <section className="mt-4 rounded-lg border border-border bg-white p-4">
        <div className="mb-4 flex items-center justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold text-foreground">Drift Report</h3>
            <p className="text-xs text-muted-foreground">Feature, prediction, and regime drift diagnostics.</p>
          </div>
          <span className="rounded-full bg-muted px-3 py-1 text-xs text-muted-foreground">
            {driftLevel}
          </span>
        </div>

        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
          <MetricCard label="Drift Level" value={driftLevel} />
          <MetricCard label="Drift Score" value={formatDecimal(driftScore, 2)} />
          <MetricCard label="Prediction Shift" value={formatDecimal(predictionShiftScore, 2)} />
          <MetricCard label="Calibration Shift" value={formatDecimal(calibrationShiftScore, 2)} />
          <MetricCard label="Regime Shift" value={formatDecimal(regimeShiftScore, 2)} />
          <MetricCard label="Recommended Action" value={driftReport?.recommended_action ?? "-"} />
          <MetricCard label="Drifted Features" value={driftedFeatures.length} />
          <MetricCard label="Prediction Shift Type" value={pickString(driftReport?.prediction_shift, ["type", "kind"], "-")} />
          <MetricCard label="Regime Shift Type" value={pickString(driftReport?.regime_shift, ["type", "kind"], "-")} />
          <MetricCard label="Calibration Shift Type" value={pickString(driftReport?.calibration_shift, ["type", "kind"], "-")} />
        </div>

        <div className="mt-4 grid gap-4 xl:grid-cols-2">
          <section className="rounded-lg border border-border p-4">
            <h4 className="text-sm font-medium text-foreground">Feature Drift Table</h4>
            {driftedFeatures.length ? (
              <div className="mt-3 overflow-x-auto">
                <table className="min-w-full text-left text-sm">
                  <thead className="text-xs uppercase tracking-wide text-muted-foreground">
                    <tr>
                      <th className="py-2 pr-4">Feature</th>
                      <th className="py-2 pr-4">PSI</th>
                      <th className="py-2 pr-4">Drift Score</th>
                      <th className="py-2 pr-4">Train Mean</th>
                      <th className="py-2 pr-4">Recent Mean</th>
                    </tr>
                  </thead>
                  <tbody>
                    {driftedFeatures.map((row) => (
                      <tr key={row.feature} className="border-t border-border">
                        <td className="py-2 pr-4 font-medium text-foreground">
                          <div>{row.feature}</div>
                          {row.severity ? <div className="text-xs text-muted-foreground">{row.severity}</div> : null}
                        </td>
                        <td className="py-2 pr-4 text-muted-foreground">{formatDecimal(row.psi, 2)}</td>
                        <td className="py-2 pr-4 text-muted-foreground">{formatDecimal(row.driftScore, 2)}</td>
                        <td className="py-2 pr-4 text-muted-foreground">{formatDecimal(row.trainMean, 4)}</td>
                        <td className="py-2 pr-4 text-muted-foreground">{formatDecimal(row.recentMean, 4)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="mt-3 text-sm text-muted-foreground">No drifted features detected.</p>
            )}
          </section>

          <section className="rounded-lg border border-border p-4">
            <h4 className="text-sm font-medium text-foreground">Raw Drift Payload</h4>
            <details className="mt-3 rounded-md border border-border p-3">
              <summary className="cursor-pointer text-sm font-medium text-foreground">Open drift report JSON</summary>
              <pre className="mt-3 max-h-72 overflow-auto rounded bg-muted p-3 text-xs text-foreground">
                {JSON.stringify(driftReport ?? {}, null, 2)}
              </pre>
            </details>
          </section>
        </div>
      </section>

      <section className="mt-4 grid gap-4 xl:grid-cols-2">
        <DistributionChart
          title="Prediction Distribution"
          data={predictionChart}
          emptyLabel="No prediction distribution data available."
        />
        <DistributionChart title="Regime Distribution" data={regimeChart} emptyLabel="No regime distribution data available." />
      </section>

      <section className="mt-4 rounded-lg border border-border bg-white p-4">
        <details>
          <summary className="cursor-pointer text-sm font-semibold text-foreground">Raw model metrics</summary>
          <pre className="mt-3 max-h-80 overflow-auto rounded-md bg-muted p-3 text-xs text-foreground">
            {JSON.stringify(info?.metrics ?? {}, null, 2)}
          </pre>
        </details>
      </section>
    </div>
  );
}
