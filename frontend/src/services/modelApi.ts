import {
  getModelCalibration as getModelCalibrationRequest,
  getModelDrift as getModelDriftRequest,
  getModelInfo as getModelInfoRequest,
  trainModel as trainModelRequest,
} from "@/lib/api";
import type { ModelCalibration, ModelInfo } from "@/types";
import type { DriftFeatureMetric, DriftReport } from "@/types/model";
import {
  asRecord,
  numberOrNull,
  stringArray,
  toApiResource,
  type ApiResource,
} from "@/services/apiState";

export { getModelCalibration, getModelDrift, getModelInfo, trainModel } from "@/lib/api";

export interface NormalizedModelDriftResponse {
  symbol?: string;
  timeframe?: string;
  model_id?: string;
  model_version?: string;
  report?: DriftReport | null;
}

export function normalizeDriftReport(payload: unknown): DriftReport | null {
  const record = asRecord(payload);
  if (!record) return null;
  return {
    drift_level: nullableString(record.drift_level) ?? undefined,
    drift_score: numberOrNull(record.drift_score),
    drifted: typeof record.drifted === "boolean" ? record.drifted : undefined,
    drifted_features: normalizeDriftFeatures(record.drifted_features),
    feature_metrics: normalizeDriftFeatures(record.feature_metrics),
    prediction_shift: asRecord(record.prediction_shift) ?? undefined,
    prediction_distribution_shift: asRecord(record.prediction_distribution_shift) ?? undefined,
    calibration_shift: asRecord(record.calibration_shift) ?? undefined,
    calibration_drift: asRecord(record.calibration_drift) ?? undefined,
    regime_shift: asRecord(record.regime_shift) ?? undefined,
    regime_drift: asRecord(record.regime_drift) ?? undefined,
    recommended_action: nullableString(record.recommended_action) ?? undefined,
    metadata: asRecord(record.metadata) ?? undefined,
  };
}

export function normalizeModelInfo(payload: unknown): ModelInfo {
  const record = asRecord(payload) ?? {};
  return {
    ...(record as unknown as ModelInfo),
    feature_columns: stringArray(record.feature_columns),
    drift_report: normalizeDriftReport(record.drift_report) as ModelInfo["drift_report"],
  };
}

export function normalizeModelDriftResponse(payload: unknown): NormalizedModelDriftResponse {
  const record = asRecord(payload) ?? {};
  return {
    symbol: nullableString(record.symbol) ?? undefined,
    timeframe: nullableString(record.timeframe) ?? undefined,
    model_id: nullableString(record.model_id) ?? undefined,
    model_version: nullableString(record.model_version) ?? undefined,
    report: normalizeDriftReport(record.report),
  };
}

export async function getModelInfoResource(
  symbol?: string,
  timeframe?: string,
): Promise<ApiResource<ModelInfo>> {
  return toApiResource(() => getModelInfoRequest(symbol, timeframe), normalizeModelInfo);
}

export async function getModelCalibrationResource(
  symbol?: string,
  timeframe?: string,
): Promise<ApiResource<ModelCalibration>> {
  return toApiResource(
    () => getModelCalibrationRequest(symbol, timeframe),
    (payload) => (asRecord(payload) ?? {}) as unknown as ModelCalibration,
  );
}

export async function getModelDriftResource(
  symbol?: string,
  timeframe?: string,
  recentWindow = 200,
): Promise<ApiResource<NormalizedModelDriftResponse>> {
  return toApiResource(
    () => getModelDriftRequest(symbol, timeframe, recentWindow),
    normalizeModelDriftResponse,
  );
}

export async function trainModelResource(
  symbol: string,
  timeframe: string,
): Promise<ApiResource<ModelInfo>> {
  return toApiResource(() => trainModelRequest(symbol, timeframe), normalizeModelInfo);
}

function normalizeDriftFeatures(payload: unknown): DriftFeatureMetric[] {
  if (!Array.isArray(payload)) return [];
  return payload.map((item) => {
    const record = asRecord(item) ?? {};
    return {
      feature: nullableString(record.feature) ?? undefined,
      psi: numberOrNull(record.psi),
      ks_stat: numberOrNull(record.ks_stat),
      ks_pvalue: numberOrNull(record.ks_pvalue),
      drift_score: numberOrNull(record.drift_score),
      drifted: typeof record.drifted === "boolean" ? record.drifted : undefined,
    };
  });
}

function nullableString(value: unknown): string | null {
  if (value === null || value === undefined) return null;
  return String(value);
}
