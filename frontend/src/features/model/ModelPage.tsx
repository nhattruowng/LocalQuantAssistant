import { AlertTriangle, Brain } from "lucide-react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { MetricCard } from "@/components/cards/MetricCard";
import { Button } from "@/components/forms/Button";
import { PageHeader } from "@/components/layout/PageHeader";
import { useActions, useModelCalibrationQuery, useModelDriftQuery, useModelInfoQuery } from "@/hooks/useApiQueries";
import { formatNumber } from "@/lib/utils";
import type { DriftReportPayload } from "@/types";

function featureImportance(metrics?: Record<string, unknown>) {
  const raw = metrics?.feature_importance;
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return [];
  return Object.entries(raw as Record<string, number>)
    .map(([feature, impact]) => ({ feature, impact: Number(impact) }))
    .filter((item) => Number.isFinite(item.impact))
    .sort((a, b) => Math.abs(b.impact) - Math.abs(a.impact))
    .slice(0, 15);
}

function driftFeatures(report?: DriftReportPayload) {
  if (!report?.drifted_features || !Array.isArray(report.drifted_features)) return [];
  return report.drifted_features.slice(0, 20);
}

export function ModelPage() {
  const model = useModelInfoQuery();
  const calibration = useModelCalibrationQuery();
  const drift = useModelDriftQuery(200);
  const actions = useActions();
  const info = model.data;
  const calibrationInfo = calibration.data;
  const driftReport = drift.data?.report;
  const importance = featureImportance((info?.metrics ?? {}) as Record<string, unknown>);
  const drifted = driftFeatures(driftReport);
  const predictionShift = driftReport?.prediction_shift ?? {};

  return (
    <div>
      <PageHeader
        title="Model"
        description="Model quality, calibration stability, and drift diagnostics."
        actions={(
          <Button onClick={() => actions.trainModel.mutate()} disabled={actions.trainModel.isPending}>
            <Brain className="h-4 w-4" />
            {actions.trainModel.isPending ? "Training..." : "Train Model"}
          </Button>
        )}
      />
      {model.isLoading ? (
        <div className="mb-4 rounded-lg border border-border bg-white p-4 text-sm text-muted-foreground">Loading model metadata...</div>
      ) : null}
      {model.isError ? (
        <div className="mb-4 rounded-lg border border-dashed border-border p-6 text-muted-foreground">No model trained</div>
      ) : null}
      <div className="mb-4 grid gap-4 md:grid-cols-4">
        <MetricCard label="Model Type" value={info?.model_type ?? "-"} />
        <MetricCard label="Trained At" value={info?.trained_at ?? "-"} />
        <MetricCard label="Feature Count" value={info?.feature_columns?.length ?? "-"} />
        <MetricCard label="Version" value={info?.model_version ?? "-"} />
        <MetricCard label="Scope" value={info?.model_scope ?? "global"} />
        <MetricCard label="Status" value={info?.status ?? "-"} />
        <MetricCard label="Calibration Method" value={calibrationInfo?.calibration_method ?? "none"} />
        <MetricCard label="Drift Level" value={driftReport?.drift_level ?? "-"} />
      </div>
      <section className="rounded-lg border border-border bg-white p-4">
        <h3 className="mb-4 text-sm font-semibold">Feature Importance</h3>
        {importance.length ? (
          <div className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={importance} layout="vertical" margin={{ left: 80 }}>
                <CartesianGrid stroke="#e5e7eb" horizontal={false} />
                <XAxis type="number" />
                <YAxis type="category" dataKey="feature" width={130} />
                <Tooltip formatter={(value) => formatNumber(Number(value), 4)} />
                <Bar dataKey="impact" fill="#2563eb" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">No feature importance available.</p>
        )}
      </section>
      <section className="mt-4 rounded-lg border border-border bg-white p-4">
        <div className="mb-4 flex items-center justify-between gap-3">
          <h3 className="text-sm font-semibold">Calibration Metrics</h3>
          <span className="rounded-full bg-muted px-3 py-1 text-xs text-muted-foreground">
            {calibrationInfo?.calibration_method ?? "none"}
          </span>
        </div>
        {calibration.isError || !calibrationInfo?.calibration_enabled ? (
          <div className="mb-4 flex items-center gap-2 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
            <AlertTriangle className="h-4 w-4" />
            Model probabilities are not calibrated yet. Confidence may be unstable.
          </div>
        ) : null}
        <div className="grid gap-4 md:grid-cols-4">
          <MetricCard label="Brier Before" value={formatNumber(Number(calibrationInfo?.brier_score_before), 4)} />
          <MetricCard label="Brier After" value={formatNumber(Number(calibrationInfo?.brier_score_after), 4)} />
          <MetricCard label="Log Loss Before" value={formatNumber(Number(calibrationInfo?.log_loss_before), 4)} />
          <MetricCard label="Log Loss After" value={formatNumber(Number(calibrationInfo?.log_loss_after), 4)} />
          <MetricCard label="ECE Before" value={formatNumber(Number(calibrationInfo?.expected_calibration_error_before), 4)} />
          <MetricCard label="ECE After" value={formatNumber(Number(calibrationInfo?.expected_calibration_error_after), 4)} />
        </div>
      </section>
      <section className="mt-4 rounded-lg border border-border bg-white p-4">
        <h3 className="mb-3 text-sm font-semibold">Drift Report</h3>
        {drift.isLoading ? <p className="text-sm text-muted-foreground">Loading drift report...</p> : null}
        {drift.isError ? <p className="text-sm text-muted-foreground">Drift report is unavailable.</p> : null}
        {!drift.isLoading && !drift.isError ? (
          <div className="grid gap-4 md:grid-cols-4">
            <MetricCard label="Drift Level" value={driftReport?.drift_level ?? "-"} />
            <MetricCard label="Drift Score" value={formatNumber(Number(driftReport?.drift_score), 4)} />
            <MetricCard label="Action" value={driftReport?.recommended_action ?? "-"} />
            <MetricCard label="Drifted Features" value={drifted.length} />
          </div>
        ) : null}
        {Object.keys(predictionShift).length ? (
          <div className="mt-4 grid gap-4 md:grid-cols-3">
            <MetricCard label="Prediction Dist Shift" value={formatNumber(Number(predictionShift.distribution_shift), 4)} />
            <MetricCard label="Probability Shift" value={formatNumber(Number(predictionShift.probability_shift), 4)} />
            <MetricCard label="Prediction Shift Score" value={formatNumber(Number(predictionShift.score), 4)} />
          </div>
        ) : null}
        <div className="mt-4 grid gap-4 xl:grid-cols-2">
          <section className="rounded border border-border p-3">
            <h4 className="mb-2 text-sm font-medium">Drifted Features</h4>
            {drifted.length ? (
              <ul className="space-y-1 text-sm text-muted-foreground">
                {drifted.map((item, index) => (
                  <li key={`${String(item.feature ?? "f")}-${index}`}>
                    {String(item.feature ?? "feature")} | psi {formatNumber(Number(item.psi), 4)} | score {formatNumber(Number(item.drift_score), 4)}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-muted-foreground">No drifted features detected.</p>
            )}
          </section>
          <section className="rounded border border-border p-3">
            <h4 className="mb-2 text-sm font-medium">Raw Drift Payload</h4>
            <pre className="max-h-64 overflow-auto rounded bg-muted p-2 text-xs">
              {JSON.stringify(driftReport ?? {}, null, 2)}
            </pre>
          </section>
        </div>
      </section>
      <section className="mt-4 rounded-lg border border-border bg-white p-4">
        <h3 className="mb-3 text-sm font-semibold">Metrics</h3>
        <pre className="max-h-80 overflow-auto rounded-md bg-muted p-3 text-xs">
          {JSON.stringify(info?.metrics ?? {}, null, 2)}
        </pre>
      </section>
    </div>
  );
}
