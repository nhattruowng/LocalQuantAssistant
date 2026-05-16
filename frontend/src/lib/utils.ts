import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import type { SignalType } from "@/types";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatNumber(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  return value.toLocaleString(undefined, {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  });
}

export function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  return `${(value * 100).toFixed(2)}%`;
}

export function signalClass(signal?: SignalType | string): string {
  if (signal === "BUY") return "text-emerald-700 bg-emerald-50 border-emerald-200";
  if (signal === "SELL") return "text-red-700 bg-red-50 border-red-200";
  return "text-amber-700 bg-amber-50 border-amber-200";
}

export function shortDate(value?: string): string {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}
