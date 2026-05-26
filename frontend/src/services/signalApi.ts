import {
  generateSignal as generateSignalRequest,
  getSignalHistory as getSignalHistoryRequest,
} from "@/lib/api";
import type { SignalHistory, TradeSetup } from "@/types";
import type {
  DecisionStep,
  DecisionTrace,
  Evidence,
  ReasoningDecision,
  SignalDirection,
} from "@/types/reasoning";
import {
  asRecord,
  numberOrNull,
  stringArray,
  toApiResource,
  type ApiResource,
} from "@/services/apiState";

export { generateSignal, getSignalHistory } from "@/lib/api";

export interface GenerateSignalParams {
  symbol: string;
  timeframe: string;
  account_balance: number;
  risk_percent: number;
  multi_timeframe?: boolean;
}

export function normalizeTradeSetup(payload: unknown): TradeSetup {
  const record = asRecord(payload) ?? {};
  return {
    ...(record as unknown as TradeSetup),
    symbol: String(record.symbol ?? ""),
    timeframe: String(record.timeframe ?? ""),
    signal: normalizeSignal(record.signal),
    confidence: numberOrNull(record.confidence) ?? 0,
    entry: numberOrNull(record.entry),
    stop_loss: numberOrNull(record.stop_loss),
    take_profit_1: numberOrNull(record.take_profit_1),
    take_profit_2: numberOrNull(record.take_profit_2),
    risk_reward: numberOrNull(record.risk_reward),
    position_size: numberOrNull(record.position_size),
    position_size_multiplier: numberOrNull(record.position_size_multiplier),
    reasons: stringArray(record.reasons),
    risk_notes: stringArray(record.risk_notes),
    reasoning_decision: normalizeReasoningDecision(record.reasoning_decision),
  };
}

export function normalizeReasoningDecision(payload: unknown): ReasoningDecision | null {
  const record = asRecord(payload);
  if (!record) return null;
  return {
    final_signal: normalizeNullableSignal(record.final_signal),
    setup_type: nullableString(record.setup_type),
    confluence_score: numberOrNull(record.confluence_score),
    confidence: numberOrNull(record.confidence),
    adaptive_threshold: numberOrNull(record.adaptive_threshold),
    position_size_multiplier: numberOrNull(record.position_size_multiplier),
    evidence_for: normalizeEvidenceList(record.evidence_for),
    evidence_against: normalizeEvidenceList(record.evidence_against),
    warnings: stringArray(record.warnings),
    wait_reason: nullableString(record.wait_reason),
    conflict_level: nullableString(record.conflict_level),
    conflict_details: asRecord(record.conflict_details),
    risk_notes: stringArray(record.risk_notes),
    decision_trace: normalizeDecisionTrace(record.decision_trace),
  };
}

export function normalizeDecisionTrace(payload: unknown): DecisionTrace | null {
  const record = asRecord(payload);
  if (!record) return null;
  return {
    trace_id: nullableString(record.trace_id) ?? undefined,
    symbol: nullableString(record.symbol) ?? undefined,
    timeframe: nullableString(record.timeframe) ?? undefined,
    model_version: nullableString(record.model_version),
    config_hash: nullableString(record.config_hash),
    steps: normalizeDecisionSteps(record.steps),
    final_signal: normalizeNullableSignal(record.final_signal),
    final_confidence: numberOrNull(record.final_confidence),
    wait_reason: nullableString(record.wait_reason),
    created_at: nullableString(record.created_at) ?? undefined,
    warnings: stringArray(record.warnings),
  };
}

export function normalizeEvidenceList(payload: unknown): Evidence[] {
  if (!Array.isArray(payload)) return [];
  return payload.map(normalizeEvidence).filter((item): item is Evidence => item !== null);
}

export async function generateSignalResource(params: GenerateSignalParams): Promise<ApiResource<TradeSetup>> {
  return toApiResource(() => generateSignalRequest(params), normalizeTradeSetup);
}

export async function getSignalHistoryResource(
  symbol?: string,
  timeframe?: string,
): Promise<ApiResource<SignalHistory[]>> {
  return toApiResource(
    () => getSignalHistoryRequest(symbol, timeframe),
    (payload) => (Array.isArray(payload) ? (payload as SignalHistory[]) : []),
    [],
  );
}

function normalizeEvidence(payload: unknown): Evidence | null {
  const record = asRecord(payload);
  if (!record) return null;
  return {
    name: nullableString(record.name) ?? undefined,
    source: nullableString(record.source) ?? undefined,
    direction: normalizeNullableSignal(record.direction) ?? undefined,
    score: numberOrNull(record.score),
    confidence: numberOrNull(record.confidence),
    weight: numberOrNull(record.weight),
    evidence_type: nullableString(record.evidence_type) ?? undefined,
    reason: nullableString(record.reason) ?? undefined,
    impact_on_score: numberOrNull(record.impact_on_score),
    is_critical: typeof record.is_critical === "boolean" ? record.is_critical : false,
  };
}

function normalizeDecisionSteps(payload: unknown): DecisionStep[] {
  if (!Array.isArray(payload)) return [];
  const steps: DecisionStep[] = [];
  for (const item of payload) {
    const record = asRecord(item);
    if (!record) continue;
    steps.push({
      step_name: nullableString(record.step_name) ?? "step",
      input_score: numberOrNull(record.input_score),
      output_score: numberOrNull(record.output_score),
      delta: numberOrNull(record.delta),
      passed: typeof record.passed === "boolean" ? record.passed : undefined,
      details: asRecord(record.details) ?? undefined,
      warnings: stringArray(record.warnings),
      timestamp: nullableString(record.timestamp) ?? undefined,
    });
  }
  return steps;
}

function normalizeSignal(value: unknown): TradeSetup["signal"] {
  const signal = String(value ?? "WAIT").toUpperCase();
  if (signal === "BUY" || signal === "SELL" || signal === "WAIT") return signal;
  return "WAIT";
}

function normalizeNullableSignal(value: unknown): SignalDirection | null {
  if (value === null || value === undefined) return null;
  return String(value).toUpperCase() as SignalDirection;
}

function nullableString(value: unknown): string | null {
  if (value === null || value === undefined) return null;
  return String(value);
}
