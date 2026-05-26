import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { AppShell } from "@/components/layout/AppShell";
import type { PageKey } from "@/components/layout/Sidebar";
import { DashboardPage } from "@/features/dashboard/DashboardPage";
import { HistoryPage } from "@/features/history/HistoryPage";
import { MarketPage } from "@/features/market/MarketPage";
import { SettingsPage } from "@/features/settings/SettingsPage";
import { SignalPage } from "@/pages/SignalPage";
import { BacktestPage } from "@/pages/BacktestPage";
import { ModelPage } from "@/pages/ModelPage";
import { RiskPage } from "@/pages/RiskPage";
import { useSessionStore } from "@/hooks/useSessionStore";

export function App() {
  const [activePage, setActivePage] = useState<PageKey>("dashboard");
  const queryClient = useQueryClient();
  const { latestSignal, latestBacktest, setLatestSignal } = useSessionStore();

  const activeReport = latestBacktest?.ml_enhanced ?? latestBacktest?.rule_only;

  const page = {
    dashboard: (
      <DashboardPage
        latestSignal={latestSignal}
        latestBacktestNetProfit={activeReport?.net_profit ?? null}
        onSignalGenerated={setLatestSignal}
        onBacktestRun={() => undefined}
      />
    ),
    market: <MarketPage />,
    signal: <SignalPage latestSignal={latestSignal} onSignalGenerated={setLatestSignal} />,
    backtest: <BacktestPage />,
    risk: <RiskPage />,
    model: <ModelPage />,
    history: <HistoryPage />,
    settings: <SettingsPage />,
  }[activePage];

  return (
    <AppShell activePage={activePage} onNavigate={setActivePage} onRefresh={() => queryClient.invalidateQueries()}>
      {page}
    </AppShell>
  );
}
