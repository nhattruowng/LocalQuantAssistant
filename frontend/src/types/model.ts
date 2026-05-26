export type { ModelCalibration, ModelDriftResponse, ModelInfo } from "./index";

export interface DriftFeatureMetric {
  feature?: string;
  psi?: number | null;
  ks_stat?: number | null;
  ks_pvalue?: number | null;
  drift_score?: number | null;
  drifted?: boolean;
}

export interface DriftReport {
  drift_level?: "NONE" | "LOW" | "MEDIUM" | "HIGH" | string;
  drift_score?: number | null;
  drifted?: boolean;
  drifted_features?: DriftFeatureMetric[];
  feature_metrics?: DriftFeatureMetric[];
  prediction_shift?: Record<string, unknown>;
  prediction_distribution_shift?: Record<string, unknown>;
  calibration_shift?: Record<string, unknown>;
  calibration_drift?: Record<string, unknown>;
  regime_shift?: Record<string, unknown>;
  regime_drift?: Record<string, unknown>;
  recommended_action?: "CONTINUE" | "WARN" | "RETRAIN_CANDIDATE" | "DISABLE_MODEL" | string;
  metadata?: Record<string, unknown>;
}

export type DriftReportPayload = DriftReport;
