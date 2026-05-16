import { create } from "zustand";
import { persist } from "zustand/middleware";
import { setApiBaseUrl } from "@/lib/api";

interface AppSettingsState {
  apiBaseUrl: string;
  symbol: string;
  timeframe: string;
  accountBalance: number;
  riskPercent: number;
  setApiBaseUrlValue: (value: string) => void;
  setSymbol: (value: string) => void;
  setTimeframe: (value: string) => void;
  setAccountBalance: (value: number) => void;
  setRiskPercent: (value: number) => void;
}

const initialApiBaseUrl = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export const useAppSettings = create<AppSettingsState>()(
  persist(
    (set) => ({
      apiBaseUrl: initialApiBaseUrl,
      symbol: "BTC/USDT",
      timeframe: "15m",
      accountBalance: 1000,
      riskPercent: 1,
      setApiBaseUrlValue: (value) => {
        setApiBaseUrl(value);
        set({ apiBaseUrl: value });
      },
      setSymbol: (symbol) => set({ symbol }),
      setTimeframe: (timeframe) => set({ timeframe }),
      setAccountBalance: (accountBalance) => set({ accountBalance }),
      setRiskPercent: (riskPercent) => set({ riskPercent }),
    }),
    {
      name: "localquant-ui-settings",
      onRehydrateStorage: () => (state) => {
        if (state?.apiBaseUrl) setApiBaseUrl(state.apiBaseUrl);
      },
    },
  ),
);
