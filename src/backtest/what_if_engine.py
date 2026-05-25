"""What-if configuration runner for backtest research."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
import json
from typing import Any, Callable, Iterable, Mapping

from backtest.ablation import apply_component_config
from backtest.models import BacktestReport
from backtest.scenario_engine import delta_vs_baseline, summarize_report
from config.settings import ExecutionCostSettings, Settings


WhatIfEvaluator = Callable[[Settings, Mapping[str, Any], str], BacktestReport]


@dataclass(frozen=True)
class WhatIfChange:
    """One immutable what-if config override."""

    name: str
    confluence_weights: Mapping[str, float] | None = None
    min_confluence_score: float | None = None
    conflict_penalty: float | None = None
    fakeout_penalty: float | None = None
    slippage_mode: str | None = None
    risk_per_trade: float | None = None
    enable_price_action: bool | None = None
    enable_ict: bool | None = None
    enable_mtf: bool | None = None
    enable_memory: bool | None = None
    enable_model: bool | None = None


@dataclass(frozen=True)
class AppliedWhatIfConfig:
    """Settings copy and explicit research-only override metadata."""

    settings: Settings
    changed_config: dict[str, Any]


@dataclass(frozen=True)
class WhatIfRunResult:
    """Comparison result for one what-if run versus baseline."""

    scenario: str
    baseline_result: dict[str, Any]
    scenario_result: dict[str, Any]
    delta_vs_baseline: dict[str, float]
    changed_config: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario": self.scenario,
            "baseline_result": dict(self.baseline_result),
            "scenario_result": dict(self.scenario_result),
            "delta_vs_baseline": dict(self.delta_vs_baseline),
            "changed_config": dict(self.changed_config),
        }


@dataclass(frozen=True)
class WhatIfAnalysisResult:
    """Full what-if analysis output."""

    baseline_result: dict[str, Any]
    scenarios: list[WhatIfRunResult] = field(default_factory=list)
    best_scenario: WhatIfRunResult | None = None
    worst_scenario: WhatIfRunResult | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "baseline_result": dict(self.baseline_result),
            "scenarios": [item.to_dict() for item in self.scenarios],
            "best_scenario": self.best_scenario.to_dict() if self.best_scenario else None,
            "worst_scenario": self.worst_scenario.to_dict() if self.worst_scenario else None,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)


class WhatIfEngine:
    """Run baseline plus immutable what-if config variants."""

    def run(
        self,
        settings: Settings,
        evaluate_fn: WhatIfEvaluator,
        changes: Iterable[WhatIfChange],
    ) -> WhatIfAnalysisResult:
        """Run what-if changes while preserving the original Settings object."""
        baseline_report = evaluate_fn(settings, {}, "baseline")
        baseline_summary = summarize_report(baseline_report)
        scenario_results: list[WhatIfRunResult] = []

        for change in changes:
            applied = apply_what_if_config(settings, change)
            report = evaluate_fn(applied.settings, applied.changed_config, change.name)
            scenario_summary = summarize_report(report)
            scenario_results.append(
                WhatIfRunResult(
                    scenario=change.name,
                    baseline_result=baseline_summary,
                    scenario_result=scenario_summary,
                    delta_vs_baseline=delta_vs_baseline(
                        baseline_summary,
                        scenario_summary,
                    ),
                    changed_config=applied.changed_config,
                )
            )

        return WhatIfAnalysisResult(
            baseline_result=baseline_summary,
            scenarios=scenario_results,
            best_scenario=_best_scenario(scenario_results),
            worst_scenario=_worst_scenario(scenario_results),
        )


def apply_what_if_config(settings: Settings, change: WhatIfChange) -> AppliedWhatIfConfig:
    """Return a Settings copy plus metadata for non-Settings research knobs."""
    changed_config: dict[str, Any] = {}
    updated = settings

    if change.min_confluence_score is not None:
        value = _clip(change.min_confluence_score)
        updated = replace(
            updated,
            reasoning_brain=replace(
                updated.reasoning_brain,
                min_confluence_score=value,
            ),
        )
        changed_config["min_confluence_score"] = value

    if change.conflict_penalty is not None:
        value = _clip(change.conflict_penalty)
        updated = replace(
            updated,
            reasoning_brain=replace(
                updated.reasoning_brain,
                max_conflict_penalty=value,
            ),
        )
        changed_config["conflict_penalty"] = value

    if change.fakeout_penalty is not None:
        value = _clip(change.fakeout_penalty)
        updated = replace(
            updated,
            safety_filters=replace(
                updated.safety_filters,
                breakout_fakeout_threshold=_clip(1.0 - value),
            ),
        )
        changed_config["fakeout_penalty"] = value
        changed_config["breakout_fakeout_threshold"] = updated.safety_filters.breakout_fakeout_threshold

    if change.slippage_mode is not None:
        cost_settings = updated.backtest.execution_cost or ExecutionCostSettings(
            fee_rate=updated.backtest.fee_rate,
            base_slippage_rate=updated.backtest.slippage_rate,
        )
        updated = replace(
            updated,
            backtest=replace(
                updated.backtest,
                execution_cost=replace(cost_settings, model=str(change.slippage_mode)),
            ),
        )
        changed_config["slippage_mode"] = str(change.slippage_mode)

    if change.risk_per_trade is not None:
        value = max(0.0, float(change.risk_per_trade))
        updated = replace(
            updated,
            risk=replace(updated.risk, risk_per_trade_pct=value),
        )
        changed_config["risk_per_trade"] = value

    component_overrides = _component_overrides(change)
    if component_overrides:
        updated = apply_component_config(updated, component_overrides)
        changed_config.update(component_overrides)

    if change.confluence_weights is not None:
        changed_config["confluence_weights"] = {
            str(key): max(0.0, float(value))
            for key, value in change.confluence_weights.items()
        }

    return AppliedWhatIfConfig(settings=updated, changed_config=changed_config)


def _component_overrides(change: WhatIfChange) -> dict[str, bool]:
    overrides: dict[str, bool] = {}
    if change.enable_price_action is not None:
        overrides["price_action"] = bool(change.enable_price_action)
    if change.enable_ict is not None:
        overrides["ict"] = bool(change.enable_ict)
    if change.enable_mtf is not None:
        overrides["mtf"] = bool(change.enable_mtf)
    if change.enable_memory is not None:
        overrides["memory"] = bool(change.enable_memory)
    if change.enable_model is not None:
        overrides["model_probability"] = bool(change.enable_model)
    return overrides


def _best_scenario(results: list[WhatIfRunResult]) -> WhatIfRunResult | None:
    return max(
        results,
        key=lambda item: _safe_float(item.scenario_result.get("net_profit")),
        default=None,
    )


def _worst_scenario(results: list[WhatIfRunResult]) -> WhatIfRunResult | None:
    return min(
        results,
        key=lambda item: _safe_float(item.scenario_result.get("net_profit")),
        default=None,
    )


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _clip(value: float) -> float:
    return max(0.0, min(float(value), 1.0))
