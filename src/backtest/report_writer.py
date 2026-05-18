"""Backtest report persistence."""

from __future__ import annotations

from pathlib import Path
import csv
from dataclasses import asdict
from html import escape
import json
import math
from typing import Any

from backtest.models import BacktestReport, BacktestSegmentReport


class BacktestReportWriter:
    """Writes backtest trades and summary reports."""

    def __init__(self, output_dir: Path) -> None:
        self._output_dir = output_dir

    def write(self, report: BacktestReport) -> tuple[Path, Path, Path, Path]:
        """Write trades CSV plus JSON and HTML reports."""
        self._output_dir.mkdir(parents=True, exist_ok=True)
        safe_symbol = report.symbol.replace("/", "_").replace(":", "_")
        stem = f"{safe_symbol}_{report.timeframe}_{report.mode}"
        trades_path = self._output_dir / f"{stem}_trades.csv"
        summary_path = self._output_dir / f"{stem}_summary.json"
        report_path = self._output_dir / f"{stem}_report.json"
        html_path = self._output_dir / f"{stem}_report.html"

        trade_rows = [trade.to_dict() for trade in report.trades]
        with trades_path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=trade_rows[0].keys() if trade_rows else [])
            if trade_rows:
                writer.writeheader()
                writer.writerows(trade_rows)

        summary = _json_ready(report.to_summary_dict())
        full_report = {
            **summary,
            "trades": [_json_ready(trade.to_dict()) for trade in report.trades],
        }
        summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
        report_path.write_text(json.dumps(full_report, indent=2, sort_keys=True), encoding="utf-8")
        html_path.write_text(_render_html_report(report), encoding="utf-8")
        return trades_path, summary_path, report_path, html_path

    def write_scenario_comparison(
        self,
        symbol: str,
        timeframe: str,
        reports: dict[str, BacktestReport],
    ) -> tuple[Path, Path]:
        """Write JSON and HTML comparison for execution cost scenarios."""
        self._output_dir.mkdir(parents=True, exist_ok=True)
        safe_symbol = symbol.replace("/", "_").replace(":", "_")
        stem = f"{safe_symbol}_{timeframe}_execution_cost_scenarios"
        json_path = self._output_dir / f"{stem}.json"
        html_path = self._output_dir / f"{stem}.html"
        payload = {
            scenario: _json_ready(report.to_summary_dict())
            for scenario, report in reports.items()
        }
        json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        html_path.write_text(
            _render_scenario_html(symbol=symbol, timeframe=timeframe, reports=reports),
            encoding="utf-8",
        )
        return json_path, html_path


def _render_html_report(report: BacktestReport) -> str:
    """Render a lightweight standalone HTML report."""
    summary_rows = _segment_rows({"overall": _overall_segment(report)})
    regime_rows = _segment_rows(report.grouped.get("by_market_regime", {}))
    strategy_rows = _segment_rows(report.grouped.get("by_strategy", {}))
    signal_rows = _segment_rows(report.grouped.get("by_signal_type", {}))
    confidence_rows = _segment_rows(report.grouped.get("by_confidence_bucket", {}))
    volatility_rows = _segment_rows(report.grouped.get("by_volatility_bucket", {}))
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Backtest Report - {escape(report.symbol)} {escape(report.timeframe)}</title>
  <style>
    body {{ font-family: Inter, Arial, sans-serif; margin: 32px; color: #172033; background: #f8fafc; }}
    h1, h2 {{ letter-spacing: 0; }}
    table {{ width: 100%; border-collapse: collapse; margin: 12px 0 28px; background: #fff; }}
    th, td {{ border: 1px solid #dce3ee; padding: 8px 10px; text-align: left; }}
    th {{ background: #eef4ff; }}
    .meta {{ color: #617084; }}
  </style>
</head>
<body>
  <h1>Backtest Report</h1>
  <p class="meta">{escape(report.symbol)} / {escape(report.timeframe)} / {escape(report.mode)}</p>
  <h2>Overall</h2>
  <table>{summary_rows}</table>
  <h2>By Market Regime</h2>
  <table>{regime_rows}</table>
  <h2>By Strategy</h2>
  <table>{strategy_rows}</table>
  <h2>By Signal Type</h2>
  <table>{signal_rows}</table>
  <h2>By Confidence Bucket</h2>
  <table>{confidence_rows}</table>
  <h2>By Volatility Bucket</h2>
  <table>{volatility_rows}</table>
</body>
</html>
"""


def _render_scenario_html(
    symbol: str,
    timeframe: str,
    reports: dict[str, BacktestReport],
) -> str:
    """Render a compact scenario comparison report."""
    rows = []
    for scenario, report in reports.items():
        rows.append(
            "<tr>"
            f"<td>{escape(scenario)}</td>"
            f"<td>{report.total_trades}</td>"
            f"<td>{report.winrate:.4f}</td>"
            f"<td>{report.net_profit:.4f}</td>"
            f"<td>{_format_value(report.profit_factor)}</td>"
            f"<td>{report.max_drawdown:.4f}</td>"
            f"<td>{report.expectancy:.4f}</td>"
            "</tr>"
        )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Execution Cost Scenario Comparison</title>
  <style>
    body {{ font-family: Inter, Arial, sans-serif; margin: 32px; color: #172033; background: #f8fafc; }}
    table {{ width: 100%; border-collapse: collapse; background: #fff; }}
    th, td {{ border: 1px solid #dce3ee; padding: 8px 10px; text-align: left; }}
    th {{ background: #eef4ff; }}
  </style>
</head>
<body>
  <h1>Execution Cost Scenario Comparison</h1>
  <p>{escape(symbol)} / {escape(timeframe)}</p>
  <table>
    <thead>
      <tr>
        <th>scenario</th><th>total_trades</th><th>winrate</th><th>net_profit</th>
        <th>profit_factor</th><th>max_drawdown</th><th>expectancy</th>
      </tr>
    </thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
</body>
</html>
"""


def _overall_segment(report: BacktestReport) -> BacktestSegmentReport:
    """Convert report-level metrics into a segment row."""
    return BacktestSegmentReport(
        total_trades=report.total_trades,
        winrate=report.winrate,
        gross_profit=report.gross_profit,
        gross_loss=report.gross_loss,
        net_profit=report.net_profit,
        profit_factor=report.profit_factor,
        max_drawdown=report.max_drawdown,
        expectancy=report.expectancy,
        avg_holding_bars=_average([float(trade.holding_bars) for trade in report.trades]),
        avg_confidence=_average([trade.confidence for trade in report.trades]),
        best_trade=max((trade.pnl for trade in report.trades), default=0.0),
        worst_trade=min((trade.pnl for trade in report.trades), default=0.0),
    )


def _segment_rows(segments: dict[str, BacktestSegmentReport]) -> str:
    """Render segment metrics as HTML table rows."""
    headers = [
        "segment",
        "total_trades",
        "winrate",
        "gross_profit",
        "gross_loss",
        "net_profit",
        "profit_factor",
        "max_drawdown",
        "expectancy",
        "avg_holding_bars",
        "avg_confidence",
        "best_trade",
        "worst_trade",
    ]
    head = "".join(f"<th>{escape(header)}</th>" for header in headers)
    body = []
    for name, segment in segments.items():
        values = {"segment": name, **segment.to_dict()}
        body.append(
            "<tr>"
            + "".join(f"<td>{escape(_format_value(values.get(header)))}</td>" for header in headers)
            + "</tr>"
        )
    return f"<thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody>"


def _json_ready(value: Any) -> Any:
    """Convert dataclasses and non-finite floats into strict JSON values."""
    if hasattr(value, "__dataclass_fields__"):
        return _json_ready(asdict(value))
    if isinstance(value, float):
        if math.isinf(value):
            return "Infinity"
        if math.isnan(value):
            return None
        return value
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    return value


def _format_value(value: object) -> str:
    """Format report values for HTML output."""
    if isinstance(value, float):
        if math.isinf(value):
            return "Infinity"
        return f"{value:.4f}"
    return str(value)


def _average(values: list[float]) -> float:
    """Return mean value or zero for an empty list."""
    return sum(values) / len(values) if values else 0.0
