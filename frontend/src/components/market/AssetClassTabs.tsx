import { MARKET_ASSET_TABS, type MarketAssetGroup } from "@/constants/marketPresets";
import { cn } from "@/lib/utils";

interface AssetClassTabsProps {
  value: MarketAssetGroup | "ALL";
  onChange: (value: MarketAssetGroup | "ALL") => void;
  counts?: Partial<Record<MarketAssetGroup | "ALL", number>>;
  className?: string;
}

export function AssetClassTabs({ value, onChange, counts, className }: AssetClassTabsProps) {
  return (
    <div className={cn("flex flex-wrap gap-2", className)} role="tablist" aria-label="Asset classes">
      {MARKET_ASSET_TABS.map((tab) => {
        const active = value === tab.id;
        const count = counts?.[tab.id];
        return (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onChange(tab.id)}
            className={cn(
              "rounded-full border px-3 py-2 text-xs font-semibold uppercase tracking-wide transition",
              active
                ? "border-slate-900 bg-slate-900 text-white shadow-sm"
                : "border-border bg-white text-muted-foreground hover:border-slate-300 hover:text-foreground",
            )}
          >
            {tab.label}
            {typeof count === "number" ? <span className="ml-2 opacity-70">{count}</span> : null}
          </button>
        );
      })}
    </div>
  );
}
