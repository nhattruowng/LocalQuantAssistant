"""Service layer for the Streamlit dashboard."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
import json
import logging

import pandas as pd

from backtest.backtester import Backtester, ModelProbabilityProvider, RuleOnlyProbabilityProvider
from backtest.models import BacktestReport
from backtest.report_writer import BacktestReportWriter
from collector.binance_collector import BinanceCollector
from collector.update_service import MarketDataUpdateService
from config.settings import Settings
from database.candle_repository import CandleRepository
from database.connection import create_database
from features.feature_service import FeatureService
from risk.risk_manager import RiskManager
from signal.models import TradeSetup
from signal.signal_engine import SignalEngine


class DashboardService:
    """Coordinates dashboard data access and workflow operations."""

    def __init__(self, settings: Settings, logger: logging.Logger | None = None) -> None:
        self._settings = settings
        self._logger = logger or logging.getLogger("localquant.dashboard")

    @property
    def settings(self) -> Settings:
        """Return immutable app settings."""
        return self._settings

    @property
    def symbols(self) -> tuple[str, ...]:
        """Return configured symbols."""
        return self._settings.collector.symbols

    @property
    def timeframes(self) -> tuple[str, ...]:
        """Return configured timeframes."""
        return self._settings.collector.timeframes

    def load_features(self, symbol: str, timeframe: str) -> pd.DataFrame:
        """Load candles from SQLite and build dashboard features."""
        database = create_database(self._settings.database)
        database.initialize()
        try:
            service = FeatureService(
                repository=CandleRepository(database),
                settings=self._settings,
                logger=self._logger,
            )
            return service.build_features(
                symbol=symbol,
                timeframe=timeframe,
                drop_warmup_rows=False,
            )
        finally:
            database.close()

    def update_data(self, symbol: str, timeframe: str) -> int:
        """Download and persist latest candles."""
        database = create_database(self._settings.database)
        database.initialize()
        try:
            update_service = MarketDataUpdateService(
                collector=BinanceCollector(
                    retry_attempts=self._settings.collector.retry_attempts,
                    retry_delay_seconds=self._settings.collector.retry_delay_seconds,
                    logger=self._logger,
                ),
                repository=CandleRepository(database),
                settings=self._settings.collector,
                logger=self._logger,
            )
            return update_service.update_latest(symbols=(symbol,), timeframes=(timeframe,))
        finally:
            database.close()

    def generate_signal(
        self,
        symbol: str,
        timeframe: str,
        account_balance: float,
        risk_percent: float,
    ) -> TradeSetup:
        """Generate the latest signal setup."""
        features = self.load_features(symbol, timeframe)
        if features.empty:
            raise ValueError("No data found. Please update market data first.")
        latest = features.dropna(subset=["market_regime", "atr_14"]).tail(1)
        if latest.empty:
            raise ValueError("Not enough indicator data yet. Please collect more candles.")
        row = latest.iloc[0]
        provider = self._probability_provider(symbol, timeframe)
        probabilities = provider.predict_proba(row)
        settings = self._with_risk_inputs(account_balance, risk_percent)
        setup = SignalEngine(
            settings=settings,
            risk_manager=RiskManager(settings.risk),
            logger=self._logger,
        ).generate(
            symbol=symbol,
            timeframe=timeframe,
            timestamp=row["timestamp"],
            market_regime=str(row["market_regime"]),
            features=row.to_dict(),
            probabilities=probabilities,
        )
        self.append_signal_history(setup)
        return setup

    def run_backtest(
        self,
        symbol: str,
        timeframe: str,
        account_balance: float,
        risk_percent: float,
    ) -> dict[str, BacktestReport]:
        """Run rule-only and ML-enhanced backtests when possible."""
        features = self.load_features(symbol, timeframe).dropna()
        if features.empty:
            raise ValueError("No data found. Please update market data first.")

        settings = self._with_risk_inputs(account_balance, risk_percent)
        backtester = Backtester(settings=settings, logger=self._logger)
        reports = {
            "rule_only": backtester.run(
                features=features,
                symbol=symbol,
                timeframe=timeframe,
                probability_provider=RuleOnlyProbabilityProvider(),
            )
        }
        model = self.latest_model_metadata(symbol, timeframe)
        if model is not None:
            reports["ml_enhanced"] = backtester.run(
                features=features,
                symbol=symbol,
                timeframe=timeframe,
                probability_provider=ModelProbabilityProvider.from_files(
                    Path(model["model_path"]),
                    Path(model["metadata_path"]),
                ),
            )
        writer = BacktestReportWriter(settings.backtest.output_dir)
        for report in reports.values():
            writer.write(report)
        return reports

    def latest_model_metadata(self, symbol: str, timeframe: str) -> dict[str, object] | None:
        """Return latest metadata JSON for a symbol/timeframe."""
        safe_symbol = symbol.replace("/", "_").replace(":", "_")
        pattern = f"{safe_symbol}_{timeframe}_*.metadata.json"
        candidates = sorted(self._settings.training.model_dir.glob(pattern), reverse=True)
        if not candidates:
            return None
        path = candidates[0]
        metadata = json.loads(path.read_text(encoding="utf-8"))
        metadata["metadata_path"] = str(path)
        return metadata

    def load_signal_history(self) -> pd.DataFrame:
        """Load persisted signal history."""
        path = self._history_path()
        if not path.exists():
            return pd.DataFrame()
        return pd.read_csv(path)

    def append_signal_history(self, setup: TradeSetup) -> None:
        """Append one generated setup to local history CSV."""
        path = self._history_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        row = setup.to_dict()
        row["recorded_at"] = datetime.now(UTC).isoformat()
        data = pd.DataFrame([row])
        if path.exists():
            data.to_csv(path, mode="a", header=False, index=False)
        else:
            data.to_csv(path, index=False)

    def _probability_provider(self, symbol: str, timeframe: str):
        """Return latest model provider or rule-only provider."""
        metadata = self.latest_model_metadata(symbol, timeframe)
        if metadata is None:
            return RuleOnlyProbabilityProvider()
        try:
            return ModelProbabilityProvider.from_files(
                Path(metadata["model_path"]),
                Path(metadata["metadata_path"]),
            )
        except (OSError, ValueError, KeyError) as error:
            self._logger.warning("Falling back to rule-only probabilities: %s", error)
            return RuleOnlyProbabilityProvider()

    def _with_risk_inputs(self, account_balance: float, risk_percent: float) -> Settings:
        """Return settings with dashboard risk inputs applied."""
        return replace(
            self._settings,
            risk=replace(
                self._settings.risk,
                account_balance=account_balance,
                risk_per_trade_pct=risk_percent,
            ),
        )

    def _history_path(self) -> Path:
        """Return local signal history CSV path."""
        return self._settings.features.output_dir / "signal_history.csv"
