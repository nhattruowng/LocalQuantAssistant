"""Ablation study runner for component-level edge attribution."""

from __future__ import annotations

from dataclasses import dataclass, replace
import csv
from pathlib import Path
import json
from typing import Any, Callable

from backtest.analyzer import BacktestAnalyzer
from backtest.models import BacktestReport
from config.settings import Settings


ABLATION_COMPONENTS = (
    "price_action",
    "ict",
    "memory",
    "safety_filter",
    "adaptive_threshold",
    "mtf",
    "model_probability",
)


@dataclass(frozen=True)
class AblationScenarioResult:
    """One ablation scenario with backtest summary and grouped analytics."""

    scenario: str
    component_overrides: dict[str, bool]
    report_summary: dict[str, Any]
    analysis: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario": self.scenario,
            "component_overrides": dict(self.component_overrides),
            "report_summary": dict(self.report_summary),
            "analysis": dict(self.analysis),
        }


@dataclass(frozen=True)
class AblationResult:
    """Full ablation result payload."""

    baseline_components: dict[str, bool]
    scenarios: list[AblationScenarioResult]
    json_path: Path | None = None
    csv_path: Path | None = None
    html_path: Path | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "baseline_components": dict(self.baseline_components),
            "scenarios": [item.to_dict() for item in self.scenarios],
            "artifacts": {
                "json_path": str(self.json_path) if self.json_path else None,
                "csv_path": str(self.csv_path) if self.csv_path else None,
                "html_path": str(self.html_path) if self.html_path else None,
            },
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)


class AblationStudy:
    """Runs baseline + one-component-off ablation scenarios."""

    def __init__(
        self,
        analyzer: BacktestAnalyzer | None = None,
        output_dir: Path | None = None,
    ) -> None:
        self._analyzer = analyzer or BacktestAnalyzer()
        self._output_dir = output_dir

    def run(
        self,
        settings: Settings,
        evaluate_fn: Callable[[Settings, str], BacktestReport],
    ) -> AblationResult:
        baseline = resolve_component_config(settings)
        scenarios: list[AblationScenarioResult] = []

        baseline_report = evaluate_fn(settings, "baseline")
        scenarios.append(
            AblationScenarioResult(
                scenario="baseline",
                component_overrides=baseline,
                report_summary=_summary_dict(baseline_report),
                analysis=self._analyzer.analyze(baseline_report.trades).to_dict(),
            )
        )

        for component in ABLATION_COMPONENTS:
            overrides = dict(baseline)
            overrides[component] = False
            scenario_name = f"disable_{component}"
            scenario_settings = apply_component_config(settings, overrides)
            report = evaluate_fn(scenario_settings, scenario_name)
            scenarios.append(
                AblationScenarioResult(
                    scenario=scenario_name,
                    component_overrides=overrides,
                    report_summary=_summary_dict(report),
                    analysis=self._analyzer.analyze(report.trades).to_dict(),
                )
            )

        json_path, csv_path, html_path = self._write_artifacts(scenarios, baseline)
        return AblationResult(
            baseline_components=baseline,
            scenarios=scenarios,
            json_path=json_path,
            csv_path=csv_path,
            html_path=html_path,
        )

    def _write_artifacts(
        self,
        scenarios: list[AblationScenarioResult],
        baseline: dict[str, bool],
    ) -> tuple[Path | None, Path | None, Path | None]:
        if self._output_dir is None:
            return None, None, None
        self._output_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "baseline_components": baseline,
            "scenarios": [item.to_dict() for item in scenarios],
        }
        json_path = self._output_dir / "ablation_report.json"
        json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

        csv_path = self._output_dir / "ablation_summary.csv"
        headers = [
            "scenario",
            "component_disabled",
            "total_trades",
            "winrate",
            "net_profit",
            "profit_factor",
            "max_drawdown",
            "expectancy",
        ]
        with csv_path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=headers)
            writer.writeheader()
            for item in scenarios:
                summary = item.report_summary
                disabled = [
                    key
                    for key, value in item.component_overrides.items()
                    if key in baseline and baseline[key] and not value
                ]
                writer.writerow(
                    {
                        "scenario": item.scenario,
                        "component_disabled": "|".join(disabled) if disabled else "NONE",
                        "total_trades": summary.get("total_trades", 0),
                        "winrate": summary.get("winrate", 0.0),
                        "net_profit": summary.get("net_profit", 0.0),
                        "profit_factor": summary.get("profit_factor", 0.0),
                        "max_drawdown": summary.get("max_drawdown", 0.0),
                        "expectancy": summary.get("expectancy", 0.0),
                    }
                )

        html_path = self._output_dir / "ablation_report.html"
        rows = []
        for item in scenarios:
            summary = item.report_summary
            rows.append(
                "<tr>"
                f"<td>{item.scenario}</td>"
                f"<td>{summary.get('total_trades', 0)}</td>"
                f"<td>{summary.get('winrate', 0.0):.4f}</td>"
                f"<td>{summary.get('net_profit', 0.0):.4f}</td>"
                f"<td>{summary.get('profit_factor', 0.0)}</td>"
                f"<td>{summary.get('max_drawdown', 0.0):.4f}</td>"
                f"<td>{summary.get('expectancy', 0.0):.4f}</td>"
                "</tr>"
            )
        html_path.write_text(
            (
                "<!doctype html><html><head><meta charset='utf-8'><title>Ablation Report</title>"
                "<style>body{font-family:Arial,sans-serif;margin:24px;}table{border-collapse:collapse;width:100%;}"
                "th,td{border:1px solid #ddd;padding:8px;}th{background:#f3f6fb;}</style></head><body>"
                "<h1>Ablation Study</h1><table><thead><tr>"
                "<th>Scenario</th><th>Total Trades</th><th>Winrate</th><th>Net Profit</th>"
                "<th>Profit Factor</th><th>Max Drawdown</th><th>Expectancy</th>"
                "</tr></thead><tbody>"
                + "".join(rows)
                + "</tbody></table></body></html>"
            ),
            encoding="utf-8",
        )
        return json_path, csv_path, html_path


def resolve_component_config(settings: Settings) -> dict[str, bool]:
    """Extract current component toggles from Settings."""
    return {
        "price_action": bool(settings.feature_toggles.price_action),
        "ict": bool(settings.feature_toggles.momentum),
        "memory": bool(settings.adaptive_strategy.memory_block_after_consecutive_losses),
        "safety_filter": bool(
            settings.safety_filters.mean_reversion_danger_enabled
            or settings.safety_filters.breakout_fakeout_defense_enabled
            or settings.safety_filters.extreme_volatility_block
            or settings.safety_filters.higher_timeframe_conflict_block
        ),
        "adaptive_threshold": bool(settings.adaptive_strategy.enabled),
        "mtf": bool(settings.signal.multi_timeframe.enabled if settings.signal.multi_timeframe else False),
        "model_probability": bool(settings.signal.model_score_weight > 0.0),
    }


def apply_component_config(settings: Settings, components: dict[str, bool]) -> Settings:
    """Return a Settings copy with ablation component toggles applied."""
    adaptive = settings.adaptive_strategy
    safety = settings.safety_filters
    signal = settings.signal
    feature_toggles = settings.feature_toggles
    memory_override = components.get("memory")
    memory_enabled = (
        adaptive.memory_block_after_consecutive_losses
        if memory_override is None
        else bool(memory_override)
    )
    safety_override = components.get("safety_filter")
    safety_enabled = bool(safety_override) if safety_override is not None else None
    model_override = components.get("model_probability")
    return replace(
        settings,
        feature_toggles=replace(
            feature_toggles,
            price_action=bool(components.get("price_action", feature_toggles.price_action)),
            momentum=bool(components.get("ict", feature_toggles.momentum)),
        ),
        adaptive_strategy=replace(
            adaptive,
            enabled=bool(components.get("adaptive_threshold", adaptive.enabled)),
            memory_block_after_consecutive_losses=memory_enabled,
            memory_max_score_penalty=(
                adaptive.memory_max_score_penalty
                if memory_override is None or memory_enabled
                else 0.0
            ),
            memory_max_size_penalty=(
                adaptive.memory_max_size_penalty
                if memory_override is None or memory_enabled
                else 0.0
            ),
        ),
        safety_filters=replace(
            safety,
            mean_reversion_danger_enabled=(
                safety.mean_reversion_danger_enabled if safety_enabled is None else safety_enabled
            ),
            breakout_fakeout_defense_enabled=(
                safety.breakout_fakeout_defense_enabled if safety_enabled is None else safety_enabled
            ),
            extreme_volatility_block=(
                safety.extreme_volatility_block if safety_enabled is None else safety_enabled
            ),
            higher_timeframe_conflict_block=(
                safety.higher_timeframe_conflict_block if safety_enabled is None else safety_enabled
            ),
        ),
        signal=replace(
            signal,
            model_score_weight=(
                signal.model_score_weight
                if model_override is None or bool(model_override)
                else 0.0
            ),
            multi_timeframe=replace(
                signal.multi_timeframe,
                enabled=bool(components.get("mtf", signal.multi_timeframe.enabled)),
            )
            if signal.multi_timeframe
            else None,
        ),
    )


def _summary_dict(report: BacktestReport) -> dict[str, Any]:
    return {
        "symbol": report.symbol,
        "timeframe": report.timeframe,
        "mode": report.mode,
        "total_trades": report.total_trades,
        "winrate": report.winrate,
        "net_profit": report.net_profit,
        "gross_profit": report.gross_profit,
        "gross_loss": report.gross_loss,
        "profit_factor": report.profit_factor,
        "expectancy": report.expectancy,
        "max_drawdown": report.max_drawdown,
    }
