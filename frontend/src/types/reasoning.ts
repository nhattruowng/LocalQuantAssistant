export type SignalDirection = "BUY" | "SELL" | "WAIT" | "NEUTRAL" | (string & {});

export type EvidenceType = "SUPPORT" | "AGAINST" | "WARNING" | (string & {});
export type ConflictLevel = "NONE" | "LOW" | "MEDIUM" | "HIGH" | (string & {});
export type RecommendedAction = "CONTINUE" | "REDUCE_SIZE" | "WAIT" | (string & {});

export interface Evidence {
  name?: string;
  source?: string;
  direction?: SignalDirection;
  score?: number | null;
  confidence?: number | null;
  weight?: number | null;
  evidence_type?: EvidenceType;
  reason?: string;
  impact_on_score?: number | null;
  is_critical?: boolean;
}

export interface DecisionStep {
  step_name?: string;
  input_score?: number | null;
  output_score?: number | null;
  delta?: number | null;
  passed?: boolean;
  details?: Record<string, unknown>;
  warnings?: string[];
  timestamp?: string;
}

export interface DecisionTrace {
  trace_id?: string;
  symbol?: string;
  timeframe?: string;
  model_version?: string | null;
  config_hash?: string | null;
  steps?: DecisionStep[];
  final_signal?: SignalDirection | string | null;
  final_confidence?: number | null;
  wait_reason?: string | null;
  created_at?: string;
  warnings?: string[];
}

export interface ReasoningDecision {
  final_signal?: SignalDirection | string | null;
  setup_type?: string | null;
  confluence_score?: number | null;
  confidence?: number | null;
  adaptive_threshold?: number | null;
  position_size_multiplier?: number | null;
  evidence_for?: Evidence[] | null;
  evidence_against?: Evidence[] | null;
  warnings?: string[];
  wait_reason?: string | null;
  conflict_level?: ConflictLevel | string | null;
  conflict_details?: Record<string, unknown> | null;
  risk_notes?: string[];
  decision_trace?: DecisionTrace | Record<string, unknown> | null;
}

export interface MarketPreset {
  preset_id?: string;
  label?: string;
  symbol: string;
  asset_class: string;
  timeframe?: string;
  market_regime?: string;
  description?: string;
  tags?: string[];
  risk_profile?: "conservative" | "balanced" | "aggressive" | string;
  config_overrides?: Record<string, unknown>;
}

// Backward-compatible aliases for existing code paths.
export type ReasoningEvidencePayload = Evidence;
export type DecisionStepPayload = DecisionStep;
export type DecisionTracePayload = DecisionTrace;
export type ReasoningDecisionPayload = ReasoningDecision;
