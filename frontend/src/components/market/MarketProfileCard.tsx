import { AlertTriangle, BadgeDollarSign } from "lucide-react";
import {
  createMarketSelectionPayload,
  findMarketPreset,
  MARKET_UNAVAILABLE_MESSAGE,
  type MarketPreset,
} from "@/constants/marketPresets";
import { cn } from "@/lib/utils";

interface MarketProfileCardProps {
  preset?: MarketPreset | null;
  symbol?: string | null;
  timeframe?: string;
  unavailable?: boolean;
  className?: string;
}

export function MarketProfileCard({
  preset,
  symbol,
  timeframe = "15m",
  unavailable = false,
  className,
}: MarketProfileCardProps) {
  const resolved = preset ?? findMarketPreset(symbol);
  const isUnavailable = unavailable || !resolved;

  if (isUnavailable || !resolved) {
    return (
      <section className={cn("rounded-xl border border-amber-200 bg-amber-50 p-5 text-amber-900 shadow-sm", className)}>
        <div className="flex items-start gap-3">
          <AlertTriangle className="mt-0.5 h-5 w-5" />
          <div>
            <h3 className="text-sm font-semibold">Unsupported market</h3>
            <p className="mt-1 text-sm">{MARKET_UNAVAILABLE_MESSAGE}</p>
            {symbol ? <p className="mt-2 text-xs uppercase tracking-wide opacity-80">Requested: {symbol}</p> : null}
          </div>
        </div>
      </section>
    );
  }

  const payload = createMarketSelectionPayload(resolved, timeframe);

  return (
    <section className={cn("rounded-xl border border-border bg-white p-5 shadow-sm", className)}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-muted-foreground">
            <BadgeDollarSign className="h-4 w-4" />
            <p className="text-xs font-semibold uppercase tracking-wide">Market Profile</p>
          </div>
          <h3 className="mt-2 text-2xl font-bold tracking-tight text-foreground">{resolved.name}</h3>
          <p className="mt-1 text-sm text-muted-foreground">{resolved.symbol}</p>
        </div>
        <span className="rounded-full bg-slate-900 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-white">
          {resolved.asset_class}
        </span>
      </div>
      <p className="mt-4 text-sm leading-6 text-foreground/80">{resolved.description}</p>
      <div className="mt-4 grid gap-3 sm:grid-cols-3">
        <ProfileMetric label="Asset Group" value={resolved.asset_group.replace(/_/g, " ")} />
        <ProfileMetric label="Quote" value={resolved.quote ?? "-"} />
        <ProfileMetric label="Timeframe" value={payload.timeframe} />
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        {resolved.tags.map((tag) => (
          <span key={tag} className="rounded-full border border-border bg-muted px-2.5 py-1 text-xs text-muted-foreground">
            {tag}
          </span>
        ))}
      </div>
      <details className="mt-4 rounded-lg border border-border bg-background/40 p-3">
        <summary className="cursor-pointer text-sm font-medium">Selection payload</summary>
        <pre className="mt-2 overflow-auto rounded bg-muted p-3 text-xs">{JSON.stringify(payload, null, 2)}</pre>
      </details>
    </section>
  );
}

function ProfileMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border bg-muted/40 p-3">
      <p className="text-[11px] uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="mt-1 text-sm font-semibold text-foreground">{value}</p>
    </div>
  );
}
