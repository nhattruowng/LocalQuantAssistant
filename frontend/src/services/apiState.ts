import axios from "axios";

export interface ApiClientError {
  message: string;
  status?: number;
  code?: string;
  details?: unknown;
}

export interface ApiResource<T> {
  data: T | null;
  loading: boolean;
  error: ApiClientError | null;
}

export function initialApiResource<T>(data: T | null = null): ApiResource<T> {
  return {
    data,
    loading: true,
    error: null,
  };
}

export async function toApiResource<T>(
  request: () => Promise<unknown>,
  normalize: (payload: unknown) => T,
  fallback: T | null = null,
): Promise<ApiResource<T>> {
  try {
    return {
      data: normalize(await request()),
      loading: false,
      error: null,
    };
  } catch (error) {
    return {
      data: fallback,
      loading: false,
      error: normalizeApiError(error),
    };
  }
}

export function normalizeApiError(error: unknown): ApiClientError {
  if (axios.isAxiosError(error)) {
    const response = error.response;
    const payload = asRecord(response?.data);
    const messageFromPayload = payload ? payload.message ?? asRecord(payload.error)?.message : undefined;
    return {
      message: String(messageFromPayload ?? error.message ?? "API request failed"),
      status: response?.status,
      code: error.code,
      details: response?.data,
    };
  }
  if (error instanceof Error) {
    return { message: error.message };
  }
  return { message: "API request failed", details: error };
}

export function asRecord(value: unknown): Record<string, unknown> | null {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return null;
}

export function stringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.map((item) => String(item));
}

export function numberOrNull(value: unknown): number | null {
  if (value === null || value === undefined) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

export function boolOrDefault(value: unknown, fallback: boolean): boolean {
  return typeof value === "boolean" ? value : fallback;
}
