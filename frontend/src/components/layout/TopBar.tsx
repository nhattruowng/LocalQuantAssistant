import { RefreshCw, Wifi, WifiOff } from "lucide-react";
import { Button } from "@/components/forms/Button";
import { Select } from "@/components/forms/Select";
import { useHealthQuery, useSymbolsQuery, useTimeframesQuery } from "@/hooks/useApiQueries";
import { useAppSettings } from "@/hooks/useAppSettings";
import { cn } from "@/lib/utils";

interface TopBarProps {
  onRefresh: () => void;
}

export function TopBar({ onRefresh }: TopBarProps) {
  const { symbol, timeframe, setSymbol, setTimeframe } = useAppSettings();
  const symbols = useSymbolsQuery();
  const timeframes = useTimeframesQuery();
  const health = useHealthQuery();
  const online = health.data?.status === "ok";

  return (
    <header className="sticky top-0 z-10 border-b border-border bg-background/95 px-4 py-3 backdrop-blur lg:px-6">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <p className="text-sm text-muted-foreground">Frontend for FastAPI backend</p>
          <h2 className="text-xl font-semibold tracking-normal">Trading Setup Workspace</h2>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <Select
            options={symbols.data?.length ? symbols.data : [symbol]}
            value={symbol}
            onChange={(event) => setSymbol(event.target.value)}
          />
          <Select
            options={timeframes.data?.length ? timeframes.data : [timeframe]}
            value={timeframe}
            onChange={(event) => setTimeframe(event.target.value)}
          />
          <Button onClick={onRefresh} className="bg-white text-foreground ring-1 ring-border">
            <RefreshCw className="h-4 w-4" />
            Refresh
          </Button>
          <div
            className={cn(
              "flex h-10 items-center gap-2 rounded-md border px-3 text-sm",
              online
                ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                : "border-red-200 bg-red-50 text-red-700",
            )}
          >
            {online ? <Wifi className="h-4 w-4" /> : <WifiOff className="h-4 w-4" />}
            {online ? "Backend online" : "Backend offline"}
          </div>
        </div>
      </div>
    </header>
  );
}
