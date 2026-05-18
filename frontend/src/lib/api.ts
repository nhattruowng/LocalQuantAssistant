import axios from "axios";
import type {
  BacktestResponse,
  Candle,
  ModelCalibration,
  ModelInfo,
  RiskStatus,
  SignalHistory,
  TradeSetup,
} from "@/types";

const defaultBaseUrl = "http://localhost:8000";

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || defaultBaseUrl,
  timeout: 30_000,
});

export function setApiBaseUrl(baseURL: string) {
  apiClient.defaults.baseURL = baseURL || defaultBaseUrl;
}

export async function getHealth() {
  const { data } = await apiClient.get<{ status: string; service: string }>("/api/health");
  return data;
}

export async function getSymbols() {
  const { data } = await apiClient.get<{ items: string[] }>("/api/symbols");
  return data.items;
}

export async function getTimeframes() {
  const { data } = await apiClient.get<{ items: string[] }>("/api/timeframes");
  return data.items;
}

export async function getCandles(symbol: string, timeframe: string, limit = 500) {
  const { data } = await apiClient.get<Candle[]>("/api/candles", {
    params: { symbol, timeframe, limit },
  });
  return data;
}

export async function updateData(symbol: string, timeframe: string, limit = 1000) {
  const { data } = await apiClient.post<{ inserted: number }>("/api/data/update", {
    symbol,
    timeframe,
    limit,
  });
  return data;
}

export async function buildFeatures(symbol: string, timeframe: string) {
  const { data } = await apiClient.post<{ rows: number; columns: string[] }>("/api/features/build", {
    symbol,
    timeframe,
  });
  return data;
}

export async function generateSignal(params: {
  symbol: string;
  timeframe: string;
  account_balance: number;
  risk_percent: number;
  multi_timeframe?: boolean;
}) {
  const { data } = await apiClient.post<TradeSetup>("/api/signals/generate", params);
  return data;
}

export async function runBacktest(params: {
  symbol: string;
  timeframe: string;
  initial_balance: number;
  risk_percent: number;
}) {
  const { data } = await apiClient.post<BacktestResponse>("/api/backtest/run", params);
  return data;
}

export async function getLatestBacktest(symbol: string, timeframe: string) {
  const { data } = await apiClient.get<BacktestResponse | null>("/api/backtest/latest", {
    params: { symbol, timeframe },
  });
  return data;
}

export async function getRiskStatus(symbol: string, timeframe: string) {
  const { data } = await apiClient.get<RiskStatus>("/api/risk/status", {
    params: { symbol, timeframe },
  });
  return data;
}

export async function getModelInfo(symbol?: string, timeframe?: string) {
  const { data } = await apiClient.get<ModelInfo>("/api/model/info", {
    params: { symbol, timeframe },
  });
  return data;
}

export async function getModelCalibration(symbol?: string, timeframe?: string) {
  const { data } = await apiClient.get<ModelCalibration>("/api/model/calibration", {
    params: { symbol, timeframe },
  });
  return data;
}

export async function trainModel(symbol: string, timeframe: string) {
  const { data } = await apiClient.post<ModelInfo>("/api/model/train", { symbol, timeframe });
  return data;
}

export async function getSignalHistory(symbol?: string, timeframe?: string) {
  const { data } = await apiClient.get<SignalHistory[]>("/api/signals/history", {
    params: { symbol, timeframe },
  });
  return data;
}
