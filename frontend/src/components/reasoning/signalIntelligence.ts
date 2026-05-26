import type {
  DecisionTracePayload,
  ReasoningDecisionPayload,
  StructuredExplanation,
  TradeSetup,
} from "@/types";

export interface SignalIntelligenceSnapshot {
  reasoning: ReasoningDecisionPayload | null;
  trace: DecisionTracePayload | null;
  explanation: StructuredExplanation | null;
  finalSignal: string;
  setupType: string;
  confluenceScore: number | null;
  confidence: number | null;
  adaptiveThreshold: number | null;
  positionSizeMultiplier: number | null;
  waitReason: string | null;
  conflictLevel: string;
  symbol: string;
  timeframe: string;
  currentRegime: string;
  volatilityLevel: string;
  transitionWarning: boolean;
  mtfAlignment: string;
  hasReasoning: boolean;
}

export function resolveSignalIntelligence(setup?: TradeSetup | null): SignalIntelligenceSnapshot {
  const reasoning = resolveReasoning(setup);
  const explanation = setup?.explanation_v2 ?? null;
  const finalSignal = String(reasoning?.final_signal ?? setup?.signal ?? "WAIT").toUpperCase();
  const waitReason = finalSignal === "WAIT"
    ? reasoning?.wait_reason ?? setup?.wait_reason ?? explanation?.strategy?.why_wait ?? "WAIT_NO_CLEAR_SETUP"
    : null;

  return {
    reasoning,
    trace: resolveDecisionTrace(setup, reasoning),
    explanation,
    finalSignal,
    setupType: String(reasoning?.setup_type ?? setup?.setup_type ?? explanation?.strategy?.setup_type ?? "NO_CLEAR_SETUP"),
    confluenceScore: reasoning?.confluence_score ?? setup?.confluence_score ?? explanation?.strategy?.confluence_score ?? null,
    confidence: reasoning?.confidence ?? setup?.confidence ?? explanation?.regime?.confidence ?? null,
    adaptiveThreshold: reasoning?.adaptive_threshold ?? explanation?.strategy?.adaptive_threshold ?? null,
    positionSizeMultiplier:
      reasoning?.position_size_multiplier
      ?? setup?.position_size_multiplier
      ?? setup?.size_multiplier
      ?? explanation?.multi_timeframe?.confidence_multiplier
      ?? null,
    waitReason,
    conflictLevel: String(reasoning?.conflict_level ?? setup?.conflict_level ?? explanation?.strategy?.conflict_level ?? "NONE"),
    symbol: setup?.symbol ?? "-",
    timeframe: setup?.timeframe ?? "-",
    currentRegime: setup?.market_regime ?? explanation?.regime?.primary ?? "-",
    volatilityLevel: explanation?.regime?.volatility_level ?? "-",
    transitionWarning: Boolean(explanation?.regime?.transition_warning),
    mtfAlignment: resolveMtfAlignment(explanation),
    hasReasoning: Boolean(reasoning && Object.keys(reasoning).length > 0),
  };
}

export function resolveReasoning(setup?: TradeSetup | null): ReasoningDecisionPayload | null {
  const candidate = setup?.reasoning_decision;
  return candidate && typeof candidate === "object" ? candidate : null;
}

export function resolveDecisionTrace(
  setup?: TradeSetup | null,
  reasoning: ReasoningDecisionPayload | null = resolveReasoning(setup),
): DecisionTracePayload | null {
  const trace = reasoning?.decision_trace;
  if (trace && typeof trace === "object" && "steps" in trace) {
    return trace as DecisionTracePayload;
  }
  const diagnostics = setup?.strategy_diagnostics;
  if (diagnostics && typeof diagnostics === "object") {
    const candidate = (diagnostics as Record<string, unknown>).decision_trace;
    if (candidate && typeof candidate === "object" && "steps" in candidate) {
      return candidate as DecisionTracePayload;
    }
  }
  return null;
}

export function riskGuardIsBlocked(state?: string | null): boolean {
  const normalized = String(state ?? "").toUpperCase();
  return normalized === "BLOCKED" || normalized === "COOLDOWN";
}

function resolveMtfAlignment(explanation?: StructuredExplanation | null): string {
  const mtf = explanation?.multi_timeframe;
  if (!mtf) return "-";
  if (mtf.blocked) return "Blocked";
  if (mtf.conflict) return "Conflict";
  if (Array.isArray(mtf.aligned_timeframes) && mtf.aligned_timeframes.length) {
    return mtf.aligned_timeframes.join(", ");
  }
  if (Array.isArray(mtf.reasons) && mtf.reasons.length) {
    return mtf.reasons.join("; ");
  }
  return mtf.enabled === false ? "Disabled" : "Partial";
}
