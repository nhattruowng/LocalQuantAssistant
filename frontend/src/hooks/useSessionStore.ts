import { create } from "zustand";
import type { BacktestResponse, TradeSetup } from "@/types";

interface SessionState {
  latestSignal: TradeSetup | null;
  latestBacktest: BacktestResponse | null;
  setLatestSignal: (setup: TradeSetup) => void;
  setLatestBacktest: (report: BacktestResponse) => void;
}

export const useSessionStore = create<SessionState>((set) => ({
  latestSignal: null,
  latestBacktest: null,
  setLatestSignal: (latestSignal) => set({ latestSignal }),
  setLatestBacktest: (latestBacktest) => set({ latestBacktest }),
}));
