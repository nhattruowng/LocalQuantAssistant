"""Backtest report persistence."""

from __future__ import annotations

from pathlib import Path
import csv
import json

from backtest.models import BacktestReport


class BacktestReportWriter:
    """Writes backtest trades and summary reports."""

    def __init__(self, output_dir: Path) -> None:
        self._output_dir = output_dir

    def write(self, report: BacktestReport) -> tuple[Path, Path]:
        """Write trades CSV and summary JSON."""
        self._output_dir.mkdir(parents=True, exist_ok=True)
        safe_symbol = report.symbol.replace("/", "_").replace(":", "_")
        stem = f"{safe_symbol}_{report.timeframe}_{report.mode}"
        trades_path = self._output_dir / f"{stem}_trades.csv"
        summary_path = self._output_dir / f"{stem}_summary.json"

        trade_rows = [trade.to_dict() for trade in report.trades]
        with trades_path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=trade_rows[0].keys() if trade_rows else [])
            if trade_rows:
                writer.writeheader()
                writer.writerows(trade_rows)

        summary_path.write_text(
            json.dumps(report.to_summary_dict(), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return trades_path, summary_path
