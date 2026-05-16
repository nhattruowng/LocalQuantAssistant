import { Save } from "lucide-react";
import { Button } from "@/components/forms/Button";
import { Input } from "@/components/forms/Input";
import { PageHeader } from "@/components/layout/PageHeader";
import { useAppSettings } from "@/hooks/useAppSettings";

export function SettingsPage() {
  const {
    apiBaseUrl,
    symbol,
    timeframe,
    accountBalance,
    riskPercent,
    setApiBaseUrlValue,
    setSymbol,
    setTimeframe,
    setAccountBalance,
    setRiskPercent,
  } = useAppSettings();

  return (
    <div>
      <PageHeader title="Settings" description="Local UI preferences stored in this browser." />
      <section className="max-w-3xl rounded-lg border border-border bg-white p-5">
        <div className="grid gap-4 md:grid-cols-2">
          <label className="space-y-2">
            <span className="text-sm font-medium">API Base URL</span>
            <Input value={apiBaseUrl} onChange={(event) => setApiBaseUrlValue(event.target.value)} />
          </label>
          <label className="space-y-2">
            <span className="text-sm font-medium">Default Symbol</span>
            <Input value={symbol} onChange={(event) => setSymbol(event.target.value)} />
          </label>
          <label className="space-y-2">
            <span className="text-sm font-medium">Default Timeframe</span>
            <Input value={timeframe} onChange={(event) => setTimeframe(event.target.value)} />
          </label>
          <label className="space-y-2">
            <span className="text-sm font-medium">Account Balance</span>
            <Input
              type="number"
              value={accountBalance}
              onChange={(event) => setAccountBalance(Number(event.target.value))}
            />
          </label>
          <label className="space-y-2">
            <span className="text-sm font-medium">Risk Percent</span>
            <Input type="number" value={riskPercent} onChange={(event) => setRiskPercent(Number(event.target.value))} />
          </label>
        </div>
        <Button className="mt-5" onClick={() => undefined}>
          <Save className="h-4 w-4" />
          Saved Automatically
        </Button>
      </section>
    </div>
  );
}
