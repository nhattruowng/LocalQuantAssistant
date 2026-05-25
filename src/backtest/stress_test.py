"""Stress-test helpers for execution-cost scenario comparison."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import csv
import json
from typing import TYPE_CHECKING, Any

from backtest.execution_cost import STANDARD_COST_SCENARIO_ORDER
from backtest.models import BacktestReport

if TYPE_CHECKING:
    from backtest.backtester import Backtester, ProbabilityProvider
    import pandas as pd


@dataclass(frozen=True)
class ScenarioComparison:
    """One scenario summary row for stress-test reporting."""

    scenario: str
    mode: str
    total_trades: int
    winrate: float
    net_profit: float
    gross_profit: float
    gross_loss: float
    profit_factor: float
    expectancy: float
    max_drawdown: float
    degradation_pct: float = 0.0

    def to_dict(self) -> dict[str, object]:
        return {
            "scenario": self.scenario,
            "mode": self.mode,
            "total_trades": self.total_trades,
            "winrate": self.winrate,
            "net_profit": self.net_profit,
            "gross_profit": self.gross_profit,
            "gross_loss": self.gross_loss,
            "profit_factor": self.profit_factor,
            "expectancy": self.expectancy,
            "max_drawdown": self.max_drawdown,
            "degradation_pct": self.degradation_pct,
        }


@dataclass(frozen=True)
class StressTestReport:
    """Persistable stress-test report payload."""

    symbol: str
    timeframe: str
    scenarios: list[ScenarioComparison] = field(default_factory=list)
    baseline: str = "zero_slippage_baseline"

    def to_dict(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "baseline": self.baseline,
            "scenarios": [item.to_dict() for item in self.scenarios],
        }


class BacktestStressTester:
    """Run and export standard cost stress-test scenarios."""

    def __init__(self, output_dir: Path | None = None) -> None:
        self._output_dir = output_dir

    def run(
        self,
        backtester: "Backtester",
        features: "pd.DataFrame",
        symbol: str,
        timeframe: str,
        probability_provider: "ProbabilityProvider",
    ) -> StressTestReport:
        reports = backtester.run_cost_scenarios(
            features=features,
            symbol=symbol,
            timeframe=timeframe,
            probability_provider=probability_provider,
        )
        baseline_report = reports.get("zero_slippage_baseline")
        baseline_net_profit = baseline_report.net_profit if baseline_report else None
        scenarios = [
            _scenario_comparison(name, reports[name], baseline_net_profit)
            for name in STANDARD_COST_SCENARIO_ORDER
            if name in reports
        ]
        report = StressTestReport(
            symbol=symbol,
            timeframe=timeframe,
            scenarios=scenarios,
        )
        if self._output_dir is not None:
            self.write(report)
        return report

    def write(self, report: StressTestReport) -> dict[str, Path]:
        if self._output_dir is None:
            raise ValueError("output_dir is required to write stress-test artifacts.")
        self._output_dir.mkdir(parents=True, exist_ok=True)
        base_name = f"{report.symbol.replace('/', '_')}_{report.timeframe}_stress_test"
        json_path = self._output_dir / f"{base_name}.json"
        csv_path = self._output_dir / f"{base_name}.csv"
        html_path = self._output_dir / f"{base_name}.html"

        json_path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
        _write_csv(csv_path, report.scenarios)
        html_path.write_text(_render_html(report), encoding="utf-8")
        return {"json": json_path, "csv": csv_path, "html": html_path}


def _scenario_comparison(
    name: str,
    report: BacktestReport,
    baseline_net_profit: float | None,
) -> ScenarioComparison:
    return ScenarioComparison(
        scenario=name,
        mode=report.mode,
        total_trades=report.total_trades,
        winrate=report.winrate,
        net_profit=report.net_profit,
        gross_profit=report.gross_profit,
        gross_loss=report.gross_loss,
        profit_factor=report.profit_factor,
        expectancy=report.expectancy,
        max_drawdown=report.max_drawdown,
        degradation_pct=_degradation_pct(
            baseline_net_profit=baseline_net_profit,
            scenario_net_profit=report.net_profit,
        ),
    )


def _degradation_pct(
    baseline_net_profit: float | None,
    scenario_net_profit: float,
) -> float:
    """Return non-negative performance degradation versus the baseline."""
    if baseline_net_profit is None:
        return 0.0
    if baseline_net_profit == 0:
        return 100.0 if scenario_net_profit < 0 else 0.0
    degradation = (baseline_net_profit - scenario_net_profit) / abs(baseline_net_profit)
    return max(0.0, degradation * 100.0)


def _write_csv(path: Path, scenarios: list[ScenarioComparison]) -> None:
    if not scenarios:
        headers = ["scenario", "mode", "total_trades", "winrate", "net_profit"]
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=headers)
            writer.writeheader()
        return
    headers = list(scenarios[0].to_dict().keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        for row in scenarios:
            writer.writerow(row.to_dict())


def _render_html(report: StressTestReport) -> str:
    rows = "\n".join(
        (
            f"<tr><td>{item.scenario}</td><td>{item.total_trades}</td>"
            f"<td>{item.winrate:.2%}</td><td>{item.net_profit:.2f}</td>"
            f"<td>{item.profit_factor:.2f}</td><td>{item.max_drawdown:.2f}</td>"
            f"<td>{item.degradation_pct:.2f}%</td></tr>"
        )
        for item in report.scenarios
    )
    return (
        "<html><head><title>Stress Test Report</title></head><body>"
        f"<h1>Stress Test - {report.symbol} {report.timeframe}</h1>"
        "<table border='1' cellpadding='6' cellspacing='0'>"
        "<thead><tr><th>Scenario</th><th>Trades</th><th>Winrate</th>"
        "<th>Net Profit</th><th>Profit Factor</th><th>Max Drawdown</th>"
        "<th>Degradation</th></tr></thead>"
        f"<tbody>{rows}</tbody></table></body></html>"
    )
