import { MetricCard } from "@/components/cards/MetricCard";
import type { ModelInfo } from "@/types";
import { formatNumber } from "@/lib/utils";

export function ModelStatusCard({ model, symbol, timeframe }: { model?: ModelInfo | null; symbol?: string; timeframe?: string }) {
  return (
    <section className="rounded-lg border border-border bg-white p-4 shadow-sm">
      <h3 className="mb-3 text-sm font-semibold">Model Status</h3>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <MetricCard label="Model ID" value={model?.model_id ?? "-"} />
        <MetricCard label="Model Version" value={model?.model_version ?? "-"} />
        <MetricCard label="Model Scope" value={model?.model_scope ?? "global"} />
        <MetricCard label="Symbol" value={model?.symbol ?? symbol ?? "-"} />
        <MetricCard label="Timeframe" value={model?.timeframe ?? timeframe ?? "-"} />
        <MetricCard label="Trained At" value={model?.trained_at ?? "-"} />
        <MetricCard label="Validation Method" value={model?.validation_method ?? model?.calibration_method ?? "time_split"} />
        <MetricCard label="Calibration Enabled" value={model?.calibration_enabled ? "Yes" : "No"} />
        <MetricCard label="Probability Source" value={model?.probability_source ?? "-"} />
        <MetricCard label="Feature Count" value={formatNumber(model?.feature_columns?.length ?? 0, 0)} />
      </div>
    </section>
  );
}
