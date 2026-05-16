import { useMemo, useState } from "react";
import { Input } from "@/components/forms/Input";
import { Select } from "@/components/forms/Select";
import { PageHeader } from "@/components/layout/PageHeader";
import { DataTable } from "@/components/tables/DataTable";
import { useHistoryQuery } from "@/hooks/useApiQueries";
import { formatNumber } from "@/lib/utils";
import type { SignalHistory, SignalType } from "@/types";

const signalOptions: Array<SignalType | "ALL"> = ["ALL", "BUY", "SELL", "WAIT"];

export function HistoryPage() {
  const history = useHistoryQuery();
  const [signal, setSignal] = useState<SignalType | "ALL">("ALL");
  const [strategy, setStrategy] = useState("");

  const rows = useMemo(() => {
    return (history.data ?? []).filter((item) => {
      const signalMatch = signal === "ALL" || item.signal === signal;
      const strategyMatch = !strategy || item.strategy?.toLowerCase().includes(strategy.toLowerCase());
      return signalMatch && strategyMatch;
    });
  }, [history.data, signal, strategy]);

  return (
    <div>
      <PageHeader title="History" description="Stored signal history with simple filters." />
      <div className="mb-4 flex flex-wrap gap-3">
        <Select options={signalOptions} value={signal} onChange={(event) => setSignal(event.target.value as SignalType | "ALL")} />
        <Input placeholder="Filter strategy" value={strategy} onChange={(event) => setStrategy(event.target.value)} />
      </div>
      <DataTable<SignalHistory>
        rows={rows}
        emptyText="No signal history found."
        columns={[
          { key: "recorded_at", label: "Recorded" },
          { key: "symbol", label: "Symbol" },
          { key: "timeframe", label: "Timeframe" },
          { key: "signal", label: "Signal" },
          { key: "strategy", label: "Strategy" },
          { key: "market_regime", label: "Regime" },
          { key: "confidence", label: "Confidence", render: (value) => formatNumber(Number(value), 4) },
        ]}
      />
    </div>
  );
}
