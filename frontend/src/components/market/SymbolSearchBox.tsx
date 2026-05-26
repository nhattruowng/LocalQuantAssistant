import { Search } from "lucide-react";
import { Input } from "@/components/forms/Input";
import { MARKET_UNAVAILABLE_MESSAGE, type MarketPreset } from "@/constants/marketPresets";
import { cn } from "@/lib/utils";

interface SymbolSearchBoxProps {
  query: string;
  onQueryChange: (value: string) => void;
  results: MarketPreset[];
  onSelect: (preset: MarketPreset) => void;
  selectedSymbol?: string | null;
  className?: string;
}

export function SymbolSearchBox({
  query,
  onQueryChange,
  results,
  onSelect,
  selectedSymbol,
  className,
}: SymbolSearchBoxProps) {
  const hasQuery = query.trim().length > 0;
  const showUnsupported = hasQuery && results.length === 0;

  return (
    <div className={cn("rounded-xl border border-border bg-white p-4 shadow-sm", className)}>
      <label className="text-xs font-semibold uppercase tracking-wide text-muted-foreground" htmlFor="market-symbol-search">
        Search symbol or market
      </label>
      <div className="relative mt-2">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          id="market-symbol-search"
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          placeholder="Search XAUUSD, Gold, EURUSD, Bitcoin..."
          className="w-full pl-9"
        />
      </div>
      {showUnsupported ? (
        <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
          {MARKET_UNAVAILABLE_MESSAGE}
        </div>
      ) : null}
      <div className="mt-3 max-h-72 overflow-auto rounded-lg border border-border/70">
        {results.map((preset) => {
          const active = preset.symbol === selectedSymbol;
          return (
            <button
              key={preset.symbol}
              type="button"
              onClick={() => onSelect(preset)}
              className={cn(
                "flex w-full items-start justify-between gap-3 border-b border-border/60 px-3 py-3 text-left transition last:border-b-0",
                active ? "bg-slate-900 text-white" : "bg-white hover:bg-muted/60",
              )}
            >
              <span>
                <span className="block text-sm font-semibold">{preset.symbol}</span>
                <span className={cn("mt-0.5 block text-xs", active ? "text-white/70" : "text-muted-foreground")}>
                  {preset.name}
                </span>
              </span>
              <span className={cn("rounded-full px-2 py-1 text-[11px] font-semibold", active ? "bg-white/15" : "bg-muted")}>
                {preset.asset_class}
              </span>
            </button>
          );
        })}
        {!results.length && !showUnsupported ? (
          <div className="px-3 py-4 text-sm text-muted-foreground">No presets in this asset class.</div>
        ) : null}
      </div>
    </div>
  );
}
