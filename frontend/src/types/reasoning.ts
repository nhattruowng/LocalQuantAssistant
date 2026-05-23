export type SignalDirection = "BUY" | "SELL" | "WAIT" | "NEUTRAL";

export type EvidenceType = "SUPPORT" | "AGAINST" | "WARNING";

export interface Evidence {
  name: string;
  source: string;
  direction: SignalDirection;
  score: number;
  confidence: number;
  weight: number;
  evidence_type: EvidenceType;
  reason: string;
  impact_on_score?: number;
  is_critical?: boolean;
}

export interface DecisionStep {
  step_name: string;
  input_score?: number;
  output_score?: number;
  delta?: number;
  passed?: boolean;
  details?: Record<string, unknown>;
  warnings?: string[];
  timestamp?: string;
}

export interface DecisionTrace {
  trace_id?: string;
  symbol?: string;
  timeframe?: string;
  model_version?: string;
  config_hash?: string;
  steps: DecisionStep[];
  final_signal?: string;
  final_confidence?: number;
  created_at?: string;
}

export interface ReasoningDecision {
  final_signal: "BUY" | "SELL" | "WAIT";
  setup_type?: string;
  confluence_score?: number;
  confidence?: number;
  adaptive_threshold?: number;
  position_size_multiplier?: number;
  evidence_for?: Evidence[];
  evidence_against?: Evidence[];
  warnings?: string[];
  wait_reason?: string | null;
  conflict_level?: "NONE" | "LOW" | "MEDIUM" | "HIGH";
  conflict_details?: string[];
  risk_notes?: string[];
  decision_trace?: DecisionTrace;
}

// Backward-compatible aliases for existing code paths.
export type ReasoningEvidencePayload = Evidence;
export type DecisionStepPayload = DecisionStep;
export type DecisionTracePayload = DecisionTrace;
export type ReasoningDecisionPayload = ReasoningDecision;
