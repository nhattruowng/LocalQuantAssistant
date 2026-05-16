import { Brain } from "lucide-react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { MetricCard } from "@/components/cards/MetricCard";
import { Button } from "@/components/forms/Button";
import { PageHeader } from "@/components/layout/PageHeader";
import { useActions, useModelInfoQuery } from "@/hooks/useApiQueries";
import { formatNumber } from "@/lib/utils";

function featureImportance(metrics?: Record<string, unknown>) {
  const raw = metrics?.feature_importance;
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return [];
  return Object.entries(raw as Record<string, number>)
    .map(([feature, impact]) => ({ feature, impact: Number(impact) }))
    .filter((item) => Number.isFinite(item.impact))
    .sort((a, b) => Math.abs(b.impact) - Math.abs(a.impact))
    .slice(0, 15);
}

export function ModelPage() {
  const model = useModelInfoQuery();
  const actions = useActions();
  const info = model.data;
  const importance = featureImportance(info?.metrics);

  return (
    <div>
      <PageHeader
        title="Model"
        description="Current trained model metadata, validation metrics, and feature importance when available."
        actions={
          <Button onClick={() => actions.trainModel.mutate()} disabled={actions.trainModel.isPending}>
            <Brain className="h-4 w-4" />
            Train Model
          </Button>
        }
      />
      {model.isError ? <div className="mb-4 rounded-lg border border-dashed border-border p-6 text-muted-foreground">No model trained</div> : null}
      <div className="mb-4 grid gap-4 md:grid-cols-4">
        <MetricCard label="Model Type" value={info?.model_type ?? "-"} />
        <MetricCard label="Trained At" value={info?.trained_at ?? "-"} />
        <MetricCard label="Feature Count" value={info?.feature_columns?.length ?? "-"} />
        <MetricCard label="Accuracy" value={formatNumber(Number(info?.metrics?.accuracy), 4)} />
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
        <h3 className="mb-3 text-sm font-semibold">Metrics</h3>
        <pre className="max-h-80 overflow-auto rounded-md bg-muted p-3 text-xs">
          {JSON.stringify(info?.metrics ?? {}, null, 2)}
        </pre>
      </section>
    </div>
  );
}
