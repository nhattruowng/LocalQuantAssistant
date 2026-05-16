import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface MetricCardProps {
  label: string;
  value: ReactNode;
  helper?: ReactNode;
  className?: string;
}

export function MetricCard({ label, value, helper, className }: MetricCardProps) {
  return (
    <section className={cn("rounded-lg border border-border bg-card p-4 shadow-sm", className)}>
      <p className="text-sm text-muted-foreground">{label}</p>
      <div className="mt-2 text-2xl font-semibold tracking-normal">{value}</div>
      {helper ? <div className="mt-2 text-xs text-muted-foreground">{helper}</div> : null}
    </section>
  );
}
