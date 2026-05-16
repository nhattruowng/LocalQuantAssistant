"""Service layer used by FastAPI routes."""

from __future__ import annotations

from dataclasses import replace
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
from ml.model_trainer import ModelTrainer


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
    ) -> dict[str, object]:
        """Generate one trade setup."""
        setup = self._dashboard.generate_signal(
            symbol=symbol,
            timeframe=timeframe,
            account_balance=account_balance,
            risk_percent=_percent_to_decimal(risk_percent),
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

    def model_info(self, symbol: str | None = None, timeframe: str | None = None) -> dict[str, object] | None:
        """Return latest model metadata."""
        if symbol and timeframe:
            return _json_safe(self._dashboard.latest_model_metadata(symbol, timeframe))
        candidates = sorted(
            self._settings.training.model_dir.glob("*.metadata.json"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        if not candidates:
            return None
        path = candidates[0]
        metadata = json.loads(path.read_text(encoding="utf-8"))
        metadata["metadata_path"] = str(path)
        return _json_safe(metadata)

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
        })

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
