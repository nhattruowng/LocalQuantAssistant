import { MetricCard } from "@/components/cards/MetricCard";
import type { ModelCalibration } from "@/types";
import { formatNumber } from "@/lib/utils";

type ProbabilityRow = { label: string; raw?: number | null; calibrated?: number | null };

export function CalibrationPanel({ calibration, probabilities }: { calibration?: ModelCalibration | null; probabilities?: ProbabilityRow[] }) {
  return (
    <section className="rounded-lg border border-border bg-white p-4 shadow-sm">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h3 className="text-sm font-semibold">Calibration</h3>
        <span className="rounded-full bg-muted px-3 py-1 text-xs text-muted-foreground">
          {calibration?.calibration_enabled ? "Enabled" : "Disabled"}
        </span>
      </div>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Brier Score Before" value={formatNumber(calibration?.brier_score_before ?? null, 2)} />
        <MetricCard label="Brier Score After" value={formatNumber(calibration?.brier_score_after ?? null, 2)} />
        <MetricCard label="Log Loss Before" value={formatNumber(calibration?.log_loss_before ?? null, 2)} />
        <MetricCard label="Log Loss After" value={formatNumber(calibration?.log_loss_after ?? null, 2)} />
        <MetricCard label="ECE Before" value={formatNumber(calibration?.expected_calibration_error_before ?? null, 2)} />
        <MetricCard label="ECE After" value={formatNumber(calibration?.expected_calibration_error_after ?? null, 2)} />
      </div>
      <div className="mt-4 overflow-x-auto">
        <table className="min-w-full text-left text-sm">
          <thead className="text-xs uppercase tracking-wide text-muted-foreground">
            <tr>
              <th className="py-2 pr-4">Signal</th>
              <th className="py-2 pr-4">Raw</th>
              <th className="py-2 pr-4">Calibrated</th>
            </tr>
          </thead>
          <tbody>
            {probabilities?.length ? (
              probabilities.map((row) => (
                <tr key={row.label} className="border-t border-border">
                  <td className="py-2 pr-4 font-medium text-foreground">{row.label}</td>
                  <td className="py-2 pr-4 text-muted-foreground">{formatProbability(row.raw)}</td>
                  <td className="py-2 pr-4 text-muted-foreground">{formatProbability(row.calibrated)}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={3} className="py-3 text-sm text-muted-foreground">
                  No calibration probability comparison available.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function formatProbability(value?: number | null) {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  const normalized = Math.abs(value) <= 1 ? value * 100 : value;
  return `${normalized.toFixed(1)}%`;
}
