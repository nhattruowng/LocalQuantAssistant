"""Safe research hypothesis generation from reviews and metrics."""

from __future__ import annotations

from typing import Any, Mapping

from research_assistant.trace_summarizer import ResearchAssistantResponse, _sanitize_text


class HypothesisGenerator:
    """Generate offline research ideas without producing actions or live changes."""

    def generate(
        self,
        review: Mapping[str, Any] | None = None,
        decision_trace: Mapping[str, Any] | None = None,
        backtest_metrics: Mapping[str, Any] | None = None,
    ) -> ResearchAssistantResponse:
        review_payload = dict(review or {})
        trace_payload = dict(decision_trace or {})
        metrics = dict(backtest_metrics or {})
        hypotheses = self._build_hypotheses(review_payload, trace_payload, metrics)
        recommended_backtests = [
            "Run offline walk-forward comparison for reviewed setup tags.",
            "Run ablation with price action, ICT, model probability, and safety filters toggled independently.",
            "Run stress scenarios for slippage, volatility, and liquidity before considering any research conclusion.",
        ]
        conflicts = self._build_conflicts(trace_payload)
        summary = (
            f"Generated {len(hypotheses)} research hypotheses from human feedback, "
            f"trace metadata, and backtest metrics."
        )
        return ResearchAssistantResponse(
            summary=summary,
            conflicts=conflicts,
            hypotheses=hypotheses,
            recommended_backtests=recommended_backtests,
        )

    def _build_hypotheses(
        self,
        review: Mapping[str, Any],
        trace: Mapping[str, Any],
        metrics: Mapping[str, Any],
    ) -> list[str]:
        hypotheses: list[str] = []
        score = _optional_float(review.get("confluence_score"))
        if score is not None and score < 0.60:
            hypotheses.append("Low confluence may correlate with weaker realized edge in this setup bucket.")
        if review.get("user_override"):
            hypotheses.append("Human overrides may cluster around ambiguous setup quality or unclear risk context.")
        if metrics:
            expectancy = _optional_float(metrics.get("expectancy"))
            if expectancy is not None and expectancy < 0.0:
                hypotheses.append("Negative expectancy may indicate this setup bucket needs stricter offline filters.")
        steps = trace.get("steps")
        if isinstance(steps, list) and len(steps) > 0:
            hypotheses.append("Trace step failures may explain variance in backtest outcomes.")
        if not hypotheses:
            hypotheses.append("Compare reviewed samples against matched historical controls before changing research assumptions.")
        return [_sanitize_text(item) for item in hypotheses]

    def _build_conflicts(self, trace: Mapping[str, Any]) -> list[str]:
        conflicts: list[str] = []
        for step in trace.get("steps", []) if isinstance(trace.get("steps"), list) else []:
            if isinstance(step, Mapping) and not bool(step.get("passed", True)):
                conflicts.append(f"Failed trace step: {step.get('step_name', 'unnamed_step')}.")
        return [_sanitize_text(item) for item in conflicts[:5]]


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
