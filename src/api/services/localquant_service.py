"""Service layer used by FastAPI routes."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
import json
import logging
import math

import pandas as pd

from app.services.dashboard_service import DashboardService
from backtest.models import BacktestReport
from collector.binance_collector import BinanceCollector
from collector.update_service import MarketDataUpdateService
from config.settings import Settings
from database.candle_repository import CandleRepository
from database.connection import create_database
from features.feature_service import FeatureService
from ml.model_registry import ModelRegistry
from ml.model_trainer import ModelTrainer
from ml.monitoring.model_monitor import ModelMonitor
from paper.paper_trading_engine import PaperTradingEngine
from risk.risk_guard import RiskGuard, RiskGuardContext
from strategy.memory import StrategyMemoryStore


class LocalQuantApiService:
    """Facade for API workflows without exposing infrastructure to route handlers."""

    def __init__(self, settings: Settings, logger: logging.Logger | None = None) -> None:
        self._settings = settings
        self._logger = logger or logging.getLogger("localquant.api")
        self._dashboard = DashboardService(settings=settings, logger=self._logger)

    def symbols(self) -> list[str]:
        """Return configured symbols."""
        return list(self._settings.collector.symbols)

    def timeframes(self) -> list[str]:
        """Return configured timeframes."""
        return list(self._settings.collector.timeframes)

    def candles(self, symbol: str, timeframe: str, limit: int) -> list[dict[str, object]]:
        """Return latest candles as API dictionaries."""
        database = create_database(self._settings.database)
        database.initialize()
        try:
            repository = CandleRepository(database)
            candles = repository.list_latest_candles(symbol=symbol, timeframe=timeframe, limit=limit)
            return [
                {
                    "symbol": candle.symbol,
                    "timeframe": candle.timeframe,
                    "timestamp": candle.timestamp.isoformat(),
                    "open": candle.open,
                    "high": candle.high,
                    "low": candle.low,
                    "close": candle.close,
                    "volume": candle.volume,
                }
                for candle in candles
            ]
        finally:
            database.close()

    def update_data(self, symbol: str, timeframe: str, limit: int | None = None) -> int:
        """Update market data from the configured collector."""
        collector_settings = self._settings.collector
        if limit is not None:
            collector_settings = replace(collector_settings, candles_limit=limit)
        database = create_database(self._settings.database)
        database.initialize()
        try:
            service = MarketDataUpdateService(
                collector=BinanceCollector(
                    retry_attempts=collector_settings.retry_attempts,
                    retry_delay_seconds=collector_settings.retry_delay_seconds,
                    logger=self._logger,
                ),
                repository=CandleRepository(database),
                settings=collector_settings,
                logger=self._logger,
            )
            return service.update_latest(symbols=(symbol,), timeframes=(timeframe,))
        finally:
            database.close()

    def build_features(self, symbol: str, timeframe: str) -> dict[str, object]:
        """Build features for a symbol/timeframe."""
        features = self._feature_service().build_features(
            symbol=symbol,
            timeframe=timeframe,
            drop_warmup_rows=False,
        )
        return {"rows": len(features), "columns": list(features.columns)}

    def generate_signal(
        self,
        symbol: str,
        timeframe: str,
        account_balance: float,
        risk_percent: float,
        multi_timeframe: bool | None = None,
    ) -> dict[str, object]:
        """Generate one trade setup."""
        setup = self._dashboard.generate_signal(
            symbol=symbol,
            timeframe=timeframe,
            account_balance=account_balance,
            risk_percent=_percent_to_decimal(risk_percent),
            multi_timeframe=multi_timeframe,
        )
        return setup.to_dict()

    def run_backtest(
        self,
        symbol: str,
        timeframe: str,
        initial_balance: float,
        risk_percent: float,
    ) -> dict[str, object]:
        """Run backtest and return serialized reports."""
        reports = self._dashboard.run_backtest(
            symbol=symbol,
            timeframe=timeframe,
            account_balance=initial_balance,
            risk_percent=_percent_to_decimal(risk_percent),
        )
        return {mode: _report_to_dict(report) for mode, report in reports.items()}

    def latest_backtest(self, symbol: str, timeframe: str) -> dict[str, object] | None:
        """Return latest persisted backtest summary for a symbol/timeframe."""
        safe_symbol = symbol.replace("/", "_").replace(":", "_")
        pattern = f"{safe_symbol}_{timeframe}_*_summary.json"
        candidates = sorted(
            self._settings.backtest.output_dir.glob(pattern),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        if not candidates:
            return None
        return _json_safe(json.loads(candidates[0].read_text(encoding="utf-8")))

    def risk_status(self, symbol: str | None = None, timeframe: str | None = None) -> dict[str, object]:
        """Return current risk guard and circuit breaker status."""
        selected_symbol = symbol or self._settings.collector.symbols[0]
        selected_timeframe = timeframe or self._settings.collector.timeframes[0]
        database = create_database(self._settings.database)
        database.initialize()
        try:
            account = PaperTradingEngine(
                database=database,
                settings=self._settings.paper_trading,
                logger=self._logger,
            ).load_account()
            last_blocked = _latest_risk_event_at(database, selected_symbol, selected_timeframe)
            context = RiskGuardContext(
                now=_now_utc(),
                initial_balance=account.initial_balance,
                equity=account.equity,
                open_positions=[
                    trade
                    for trade in account.open_positions
                    if trade.symbol == selected_symbol and trade.timeframe == selected_timeframe
                ],
                closed_trades=[
                    trade
                    for trade in account.closed_trades
                    if trade.symbol == selected_symbol and trade.timeframe == selected_timeframe
                ],
                snapshots=account.snapshots,
                last_blocked_at=last_blocked,
                regime_confidence_threshold=(
                    self._settings.signal.strategy_ensemble.low_regime_confidence_threshold
                    if self._settings.signal.strategy_ensemble is not None
                    else 0.55
                ),
            )
            status = RiskGuard(self._settings.risk_guard).status(context)
            events = _latest_risk_events(database, selected_symbol, selected_timeframe)
            return _json_safe({**status, "symbol": selected_symbol, "timeframe": selected_timeframe, "events": events})
        finally:
            database.close()

    def paper_analytics(self, symbol: str, timeframe: str) -> dict[str, object]:
        """Return paper trading analytics."""
        return _json_safe(self._dashboard.load_paper_analytics(symbol, timeframe))

    def paper_drawdown(self, symbol: str, timeframe: str) -> dict[str, object]:
        """Return paper drawdown curve."""
        analytics = self.paper_analytics(symbol, timeframe)
        return {"drawdown_curve": analytics.get("drawdown_curve", [])}

    def paper_regime_performance(self, symbol: str, timeframe: str) -> dict[str, object]:
        """Return paper realized PnL by regime and strategy."""
        analytics = self.paper_analytics(symbol, timeframe)
        return {
            "realized_pnl_by_regime": analytics.get("realized_pnl_by_regime", {}),
            "realized_pnl_by_strategy": analytics.get("realized_pnl_by_strategy", {}),
        }

    def strategy_memory(
        self,
        symbol: str | None = None,
        timeframe: str | None = None,
    ) -> dict[str, object]:
        """Return strategy memory snapshots, optionally filtered by symbol/timeframe."""
        memory = StrategyMemoryStore(
            self._settings.features.output_dir / "strategy_memory.json"
        ).load()
        snapshots = [
            snapshot.to_dict()
            for snapshot in memory.snapshots.values()
            if (symbol is None or snapshot.symbol == symbol)
            and (timeframe is None or snapshot.timeframe == timeframe)
        ]
        return _json_safe(
            {
                "symbol": symbol,
                "timeframe": timeframe,
                "total": len(snapshots),
                "snapshots": snapshots,
            }
        )

    def model_info(self, symbol: str | None = None, timeframe: str | None = None) -> dict[str, object] | None:
        """Return latest model metadata."""
        registry = ModelRegistry(self._settings.training.model_dir)
        if symbol and timeframe:
            return _json_safe(registry.latest_metadata(symbol, timeframe))
        records = registry.list_models()
        if not records:
            return None
        return _json_safe(max(records, key=lambda item: str(item.get("trained_at", ""))))

    def model_calibration(
        self,
        symbol: str | None = None,
        timeframe: str | None = None,
    ) -> dict[str, object] | None:
        """Return latest model calibration diagnostics."""
        metadata = self.model_info(symbol=symbol, timeframe=timeframe)
        if metadata is None:
            return None
        metrics = metadata.get("metrics", {})
        calibration = metrics.get("calibration", {}) if isinstance(metrics, dict) else {}
        before = calibration.get("before", {}) if isinstance(calibration, dict) else {}
        after = calibration.get("after", {}) if isinstance(calibration, dict) else {}
        return _json_safe(
            {
                "symbol": metadata.get("symbol"),
                "timeframe": metadata.get("timeframe"),
                "trained_at": metadata.get("trained_at"),
                "calibration_enabled": metadata.get("calibration_enabled", False),
                "calibration_method": metadata.get("calibration_method", "none"),
                "brier_score_before": metadata.get("brier_score_before"),
                "brier_score_after": metadata.get("brier_score_after"),
                "log_loss_before": metadata.get("log_loss_before"),
                "log_loss_after": metadata.get("log_loss_after"),
                "expected_calibration_error_before": before.get("expected_calibration_error"),
                "expected_calibration_error_after": after.get("expected_calibration_error"),
                "per_class_brier_score_before": before.get("per_class_brier_score"),
                "per_class_brier_score_after": after.get("per_class_brier_score"),
                "reliability_curve_before": before.get("reliability_curve"),
                "reliability_curve_after": after.get("reliability_curve"),
                "probability_histogram_before": before.get("probability_histogram"),
                "probability_histogram_after": after.get("probability_histogram"),
                "report": calibration,
            }
        )

    def model_drift(
        self,
        symbol: str,
        timeframe: str,
        recent_window: int = 200,
    ) -> dict[str, object] | None:
        """Build a drift report from feature history and current model metadata."""
        metadata = self.latest_model_metadata(symbol, timeframe)
        if metadata is None:
            return None
        feature_service = self._feature_service()
        features = feature_service.build_features(
            symbol=symbol,
            timeframe=timeframe,
            drop_warmup_rows=False,
        )
        if features.empty:
            recent_rows: list[dict[str, object]] = []
            baseline_rows: list[dict[str, object]] = []
        else:
            data = features.sort_values("timestamp").reset_index(drop=True)
            recent_count = max(20, int(recent_window))
            recent = data.tail(recent_count)
            baseline = data.iloc[:-len(recent)] if len(data) > len(recent) else data.head(max(20, len(data) // 2))
            baseline_rows = baseline.to_dict("records")
            recent_rows = recent.to_dict("records")

        feature_columns = metadata.get("feature_columns", [])
        selected_baseline = _pick_features(baseline_rows, feature_columns)
        selected_recent = _pick_features(recent_rows, feature_columns)
        monitor = ModelMonitor()
        report = monitor.build_report(
            train_feature_rows=selected_baseline,
            recent_feature_rows=selected_recent,
            baseline_predictions=[],
            recent_predictions=[],
            baseline_calibration=[],
            recent_calibration=[],
            baseline_regime_counts=_regime_counts(baseline_rows),
            recent_regime_counts=_regime_counts(recent_rows),
        )
        return _json_safe(
            {
                "symbol": symbol,
                "timeframe": timeframe,
                "model_id": metadata.get("model_id"),
                "model_version": metadata.get("model_version"),
                "report": report.to_dict(),
            }
        )

    def train_model(self, symbol: str, timeframe: str) -> dict[str, object]:
        """Train a local model and return result metadata."""
        feature_service = self._feature_service()
        features = feature_service.build_features(
            symbol=symbol,
            timeframe=timeframe,
            drop_warmup_rows=True,
        )
        result = ModelTrainer(settings=self._settings, logger=self._logger).train(
            features=features,
            symbol=symbol,
            timeframe=timeframe,
        )
        return _json_safe({
            "model_path": result.model_path,
            "metadata_path": result.metadata_path,
            "model_type": result.model_type,
            "metrics": result.metrics,
            "feature_columns": result.feature_columns,
            "registry_report": result.registry_report,
        })

    def model_registry(
        self,
        symbol: str | None = None,
        timeframe: str | None = None,
    ) -> dict[str, object]:
        """Return model registry records."""
        registry = ModelRegistry(self._settings.training.model_dir)
        records = registry.list_models(symbol=symbol, timeframe=timeframe)
        return _json_safe({"models": records, "total": len(records)})

    def promote_model(self, model_id: str) -> dict[str, object]:
        """Promote a model to champion."""
        return _json_safe(ModelRegistry(self._settings.training.model_dir).promote(model_id))

    def archive_model(self, model_id: str) -> dict[str, object]:
        """Archive a model."""
        return _json_safe(ModelRegistry(self._settings.training.model_dir).archive(model_id))

    def signal_history(self, symbol: str | None = None, timeframe: str | None = None) -> list[dict[str, object]]:
        """Return saved signal history filtered by symbol/timeframe."""
        history = self._dashboard.load_signal_history()
        if history.empty:
            return []
        filtered = history
        if symbol is not None and "symbol" in filtered:
            filtered = filtered[filtered["symbol"] == symbol]
        if timeframe is not None and "timeframe" in filtered:
            filtered = filtered[filtered["timeframe"] == timeframe]
        return _dataframe_records(filtered)

    def _feature_service(self) -> FeatureService:
        """Create a feature service with a short-lived database connection."""
        database = create_database(self._settings.database)
        database.initialize()
        return _ClosingFeatureService(
            repository=CandleRepository(database),
            settings=self._settings,
            database=database,
            logger=self._logger,
        )


class _ClosingFeatureService(FeatureService):
    """FeatureService wrapper that closes its database after feature building."""

    def __init__(self, database, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._database_to_close = database

    def build_features(self, *args, **kwargs) -> pd.DataFrame:
        """Build features and close the database connection."""
        try:
            return super().build_features(*args, **kwargs)
        finally:
            self._database_to_close.close()


def _report_to_dict(report: BacktestReport) -> dict[str, object]:
    """Serialize a backtest report with trades."""
    summary = report.to_summary_dict()
    summary["trades"] = [trade.to_dict() for trade in report.trades]
    return _json_safe(summary)


def _dataframe_records(data: pd.DataFrame) -> list[dict[str, object]]:
    """Convert dataframe records into JSON-safe dictionaries."""
    return [
        {
            key: value.isoformat() if hasattr(value, "isoformat") else value
            for key, value in row.items()
        }
        for row in data.where(pd.notna(data), None).to_dict("records")
    ]


def _percent_to_decimal(value: float) -> float:
    """Convert UI-style percent input to decimal risk fraction."""
    return value / 100.0


def _json_safe(value: Any) -> Any:
    """Convert non-finite floats recursively so API JSON encoding stays valid."""
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def _pick_features(
    rows: list[dict[str, object]],
    feature_columns: object,
) -> list[dict[str, object]]:
    columns = [str(item) for item in feature_columns] if isinstance(feature_columns, list) else []
    if not columns:
        return rows
    selected: list[dict[str, object]] = []
    for row in rows:
        selected.append({column: row.get(column) for column in columns if column in row})
    return selected


def _regime_counts(rows: list[dict[str, object]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        regime = str(row.get("market_regime", "UNKNOWN")).upper()
        counts[regime] = counts.get(regime, 0) + 1
    return counts


def _now_utc() -> datetime:
    """Return current UTC timestamp."""
    return datetime.now(UTC)


def _latest_risk_event_at(database: object, symbol: str, timeframe: str) -> datetime | None:
    """Return latest blocking risk event timestamp."""
    row = database.execute(  # type: ignore[attr-defined]
        """
        SELECT timestamp
        FROM risk_events
        WHERE symbol = ? AND timeframe = ? AND state IN ('BLOCKED', 'COOLDOWN')
        ORDER BY timestamp DESC
        LIMIT 1
        """,
        (symbol, timeframe),
    ).fetchone()
    if row is None:
        return None
    return _parse_datetime(str(row["timestamp"]))


def _latest_risk_events(database: object, symbol: str, timeframe: str) -> list[dict[str, object]]:
    """Return latest persisted risk guard events."""
    rows = database.execute(  # type: ignore[attr-defined]
        """
        SELECT timestamp, state, reason, symbol, timeframe
        FROM risk_events
        WHERE symbol = ? AND timeframe = ?
        ORDER BY timestamp DESC
        LIMIT 20
        """,
        (symbol, timeframe),
    ).fetchall()
    return [
        {
            "timestamp": row["timestamp"],
            "state": row["state"],
            "reason": row["reason"],
            "symbol": row["symbol"],
            "timeframe": row["timeframe"],
        }
        for row in rows
    ]


def _parse_datetime(value: str) -> datetime:
    """Parse an ISO timestamp as timezone-aware UTC when needed."""
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
