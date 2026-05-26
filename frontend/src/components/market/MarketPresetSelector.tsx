import { useEffect, useMemo, useState } from "react";
import { Clock3 } from "lucide-react";
import { AssetClassTabs } from "@/components/market/AssetClassTabs";
import { MarketProfileCard } from "@/components/market/MarketProfileCard";
import { SymbolSearchBox } from "@/components/market/SymbolSearchBox";
import { Select } from "@/components/forms/Select";
import {
  createMarketSelectionPayload,
  DEFAULT_MARKET_TIMEFRAME,
  findMarketPreset,
  MARKET_ASSET_TABS,
  MARKET_PRESETS,
  searchMarketPresets,
  type MarketAssetGroup,
  type MarketPreset,
  type MarketSelectionPayload,
} from "@/constants/marketPresets";
import { cn } from "@/lib/utils";

const TIMEFRAMES = ["5m", "15m", "1h", "4h", "1d"];

interface MarketPresetSelectorProps {
  selectedSymbol?: string | null;
  selectedTimeframe?: string;
  onSelect?: (payload: MarketSelectionPayload, preset: MarketPreset) => void;
  availableSymbols?: string[];
  className?: string;
}

export function MarketPresetSelector({
  selectedSymbol,
  selectedTimeframe = DEFAULT_MARKET_TIMEFRAME,
  onSelect,
  availableSymbols,
  className,
}: MarketPresetSelectorProps) {
  const initialPreset = findMarketPreset(selectedSymbol) ?? (selectedSymbol ? null : MARKET_PRESETS[0]);
  const [assetGroup, setAssetGroup] = useState<MarketAssetGroup | "ALL">(initialPreset?.asset_group ?? "ALL");
  const [query, setQuery] = useState("");
  const [timeframe, setTimeframe] = useState(selectedTimeframe || DEFAULT_MARKET_TIMEFRAME);
  const [selectedPreset, setSelectedPreset] = useState<MarketPreset | null>(initialPreset);

  const counts = useMemo(() => {
    const next: Partial<Record<MarketAssetGroup | "ALL", number>> = { ALL: MARKET_PRESETS.length };
    for (const tab of MARKET_ASSET_TABS) {
      if (tab.id === "ALL") continue;
      next[tab.id] = MARKET_PRESETS.filter((preset) => preset.asset_group === tab.id).length;
    }
    return next;
  }, []);

  const results = useMemo(() => searchMarketPresets(query, assetGroup), [assetGroup, query]);
  const selectedIsAvailable = selectedPreset
    ? !availableSymbols || availableSymbols.includes(selectedPreset.symbol)
    : false;

  useEffect(() => {
    const nextPreset = findMarketPreset(selectedSymbol) ?? (selectedSymbol ? null : MARKET_PRESETS[0]);
    setSelectedPreset(nextPreset);
    if (nextPreset) setAssetGroup(nextPreset.asset_group);
  }, [selectedSymbol]);

  useEffect(() => {
    if (selectedTimeframe) setTimeframe(selectedTimeframe);
  }, [selectedTimeframe]);

  const selectPreset = (preset: MarketPreset) => {
    setSelectedPreset(preset);
    const payload = createMarketSelectionPayload(preset, timeframe);
    onSelect?.(payload, preset);
  };

  const updateTimeframe = (value: string) => {
    setTimeframe(value);
    if (selectedPreset) {
      onSelect?.(createMarketSelectionPayload(selectedPreset, value), selectedPreset);
    }
  };

  return (
    <section className={cn("rounded-2xl border border-border bg-gradient-to-br from-slate-50 to-white p-5 shadow-sm", className)}>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Market Preset Selector</p>
          <h2 className="mt-2 text-2xl font-bold tracking-tight text-foreground">Multi-asset research universe</h2>
          <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
            Pick a preset across crypto, metals, forex, indices, and commodities. Selection emits the backend-ready market payload.
          </p>
        </div>
        <label className="flex items-center gap-2 rounded-lg border border-border bg-white px-3 py-2 text-sm shadow-sm">
          <Clock3 className="h-4 w-4 text-muted-foreground" />
          <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Timeframe</span>
          <Select
            options={TIMEFRAMES}
            value={timeframe}
            onChange={(event) => updateTimeframe(event.target.value)}
            className="h-8 border-0 bg-muted shadow-none"
          />
        </label>
      </div>

      <AssetClassTabs value={assetGroup} onChange={setAssetGroup} counts={counts} className="mt-5" />

      <div className="mt-5 grid gap-4 xl:grid-cols-[0.95fr_1.05fr]">
        <SymbolSearchBox
          query={query}
          onQueryChange={setQuery}
          results={results}
          selectedSymbol={selectedPreset?.symbol ?? null}
          onSelect={selectPreset}
        />
        <MarketProfileCard
          preset={selectedPreset}
          symbol={selectedSymbol}
          timeframe={timeframe}
          unavailable={!selectedIsAvailable}
        />
      </div>
    </section>
  );
}
