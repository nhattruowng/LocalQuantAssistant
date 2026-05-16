"""Service layer for the Streamlit dashboard."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
import json
import logging
from time import perf_counter
from typing import Any

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
from ml.explainability import ExplainabilityService
from notification.telegram_service import TelegramNotificationService
from paper.paper_trading_engine import PaperTradingEngine
from risk.risk_manager import RiskManager
from signal.models import TradeSetup
from signal.signal_engine import SignalEngine


class DashboardService:
    """Coordinates dashboard data access and workflow operations."""

    def __init__(self, settings: Settings, logger: logging.Logger | None = None) -> None:
        self._settings = settings
        self._logger = logger or logging.getLogger("localquant.dashboard")
        self._feature_cache: dict[tuple[str, str, int, str | None], pd.DataFrame] = {}
        self._provider_cache: dict[tuple[str, str, str], Any] = {}
        self._explainability = ExplainabilityService(logger=self._logger)
        self._notification_service = TelegramNotificationService(
            settings=settings.notification,
            logger=self._logger,
        )

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
        started_at = perf_counter()
        database = create_database(self._settings.database)
        database.initialize()
        try:
            repository = CandleRepository(database)
            fingerprint = repository.get_fingerprint(symbol, timeframe)
            cache_key = (
                symbol,
                timeframe,
                fingerprint.row_count,
                fingerprint.latest_timestamp.isoformat() if fingerprint.latest_timestamp else None,
            )
            cached = self._feature_cache.get(cache_key)
            if cached is not None:
                self._logger.debug(
                    "Dashboard feature cache hit: symbol=%s timeframe=%s rows=%s",
                    symbol,
                    timeframe,
                    len(cached),
                )
                return cached.copy(deep=True)

            service = FeatureService(
                repository=repository,
                settings=self._settings,
                logger=self._logger,
            )
            features = service.build_features(
                symbol=symbol,
                timeframe=timeframe,
                drop_warmup_rows=False,
            )
            self._feature_cache[cache_key] = features.copy(deep=True)
            if len(self._feature_cache) > 12:
                self._feature_cache.pop(next(iter(self._feature_cache)), None)
            self._logger.info(
                "Dashboard features ready: symbol=%s timeframe=%s rows=%s elapsed_ms=%.2f",
                symbol,
                timeframe,
                len(features),
                (perf_counter() - started_at) * 1000,
            )
            return features
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
        explanation = self._explain_signal(provider, row, setup)
        if explanation is not None:
            setup = replace(setup, explainability=explanation)
        self.append_signal_history(setup)
        self._process_paper_trading(setup, row)
        self._notification_service.send_trade_setup(setup)
        return setup

    def load_paper_account(self, symbol: str, timeframe: str) -> dict[str, object]:
        """Load paper trading account state for the dashboard."""
        mark_price: float | None = None
        try:
            features = self.load_features(symbol, timeframe)
            if not features.empty:
                mark_price = float(features.sort_values("timestamp").iloc[-1]["close"])
        except Exception:
            mark_price = None

        database = create_database(self._settings.database)
        database.initialize()
        try:
            account = PaperTradingEngine(
                database=database,
                settings=self._settings.paper_trading,
                logger=self._logger,
            ).load_account(mark_price=mark_price)
            return account.to_dict()
        finally:
            database.close()

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
            key = (symbol, timeframe, "rule_only")
            if key not in self._provider_cache:
                self._provider_cache[key] = RuleOnlyProbabilityProvider()
            return self._provider_cache[key]
        key = (symbol, timeframe, str(metadata.get("metadata_path", "")))
        cached = self._provider_cache.get(key)
        if cached is not None:
            return cached
        try:
            provider = ModelProbabilityProvider.from_files(
                Path(metadata["model_path"]),
                Path(metadata["metadata_path"]),
            )
            self._provider_cache[key] = provider
            return provider
        except (OSError, ValueError, KeyError) as error:
            self._logger.warning("Falling back to rule-only probabilities: %s", error)
            return RuleOnlyProbabilityProvider()

    def _explain_signal(
        self,
        provider: object,
        row: pd.Series,
        setup: TradeSetup,
    ) -> dict[str, object] | None:
        """Explain a generated signal when a local ML model is available."""
        if not isinstance(provider, ModelProbabilityProvider):
            return None
        try:
            return self._explainability.explain(
                model=provider.model,
                feature_row=row,
                feature_columns=provider.feature_columns,
                target_label=setup.signal.value,
            ).to_dict()
        except Exception as error:
            self._logger.warning("Model explainability failed: %s", error)
            return None

    def _process_paper_trading(self, setup: TradeSetup, row: pd.Series) -> None:
        """Update paper trading state without affecting real orders."""
        database = create_database(self._settings.database)
        database.initialize()
        try:
            PaperTradingEngine(
                database=database,
                settings=self._settings.paper_trading,
                logger=self._logger,
            ).process_setup(setup, row.to_dict())
        except Exception as error:
            self._logger.warning("Paper trading update failed: %s", error)
        finally:
            database.close()

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
