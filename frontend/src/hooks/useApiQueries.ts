import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  buildFeatures,
  generateSignal,
  getCandles,
  getHealth,
  getModelCalibration,
  getModelInfo,
  getRiskStatus,
  getSignalHistory,
  getSymbols,
  getTimeframes,
  runBacktest,
  trainModel,
  updateData,
} from "@/lib/api";
import { useAppSettings } from "@/hooks/useAppSettings";

export function useHealthQuery() {
  return useQuery({ queryKey: ["health"], queryFn: getHealth, retry: 1, refetchInterval: 30_000 });
}

export function useSymbolsQuery() {
  return useQuery({ queryKey: ["symbols"], queryFn: getSymbols });
}

export function useTimeframesQuery() {
  return useQuery({ queryKey: ["timeframes"], queryFn: getTimeframes });
}

export function useCandlesQuery(limit = 500) {
  const { symbol, timeframe } = useAppSettings();
  return useQuery({
    queryKey: ["candles", symbol, timeframe, limit],
    queryFn: () => getCandles(symbol, timeframe, limit),
    retry: 1,
  });
}

export function useModelInfoQuery() {
  const { symbol, timeframe } = useAppSettings();
  return useQuery({
    queryKey: ["model", symbol, timeframe],
    queryFn: () => getModelInfo(symbol, timeframe),
    retry: false,
  });
}

export function useModelCalibrationQuery() {
  const { symbol, timeframe } = useAppSettings();
  return useQuery({
    queryKey: ["model-calibration", symbol, timeframe],
    queryFn: () => getModelCalibration(symbol, timeframe),
    retry: false,
  });
}

export function useHistoryQuery() {
  const { symbol, timeframe } = useAppSettings();
  return useQuery({
    queryKey: ["history", symbol, timeframe],
    queryFn: () => getSignalHistory(symbol, timeframe),
    retry: 1,
  });
}

export function useRiskStatusQuery() {
  const { symbol, timeframe } = useAppSettings();
  return useQuery({
    queryKey: ["risk-status", symbol, timeframe],
    queryFn: () => getRiskStatus(symbol, timeframe),
    retry: 1,
  });
}

export function useActions() {
  const queryClient = useQueryClient();
  const { symbol, timeframe, accountBalance, riskPercent } = useAppSettings();

  const invalidate = async () => {
    await queryClient.invalidateQueries();
  };

  return {
    updateData: useMutation({
      mutationFn: () => updateData(symbol, timeframe),
      onSuccess: invalidate,
    }),
    buildFeatures: useMutation({
      mutationFn: () => buildFeatures(symbol, timeframe),
      onSuccess: invalidate,
    }),
    generateSignal: useMutation({
      mutationFn: (multiTimeframe?: boolean) =>
        generateSignal({
          symbol,
          timeframe,
          account_balance: accountBalance,
          risk_percent: riskPercent,
          multi_timeframe: multiTimeframe,
        }),
      onSuccess: invalidate,
    }),
    runBacktest: useMutation({
      mutationFn: () =>
        runBacktest({
          symbol,
          timeframe,
          initial_balance: accountBalance,
          risk_percent: riskPercent,
        }),
      onSuccess: invalidate,
    }),
    trainModel: useMutation({
      mutationFn: () => trainModel(symbol, timeframe),
      onSuccess: invalidate,
    }),
  };
}
