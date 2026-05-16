"""Feature engineering service over stored OHLCV candles."""

from __future__ import annotations

from pathlib import Path
import logging
from time import perf_counter

import pandas as pd

from config.settings import Settings
from database.candle_repository import CandleRepository
from domain.entities import Candle
from features.feature_builder import FeatureBuilder


class FeatureService:
    """Loads candles, builds features, and exports processed datasets."""

    def __init__(
        self,
        repository: CandleRepository,
        settings: Settings,
        logger: logging.Logger | None = None,
    ) -> None:
        self._repository = repository
        self._settings = settings
        self._builder = FeatureBuilder(settings.feature_toggles, settings.market_regime)
        self._logger = logger or logging.getLogger("localquant.features")
        self._cache: dict[tuple[str, str, bool, int, str | None], pd.DataFrame] = {}

    def build_features(
        self,
        symbol: str,
        timeframe: str,
        drop_warmup_rows: bool | None = None,
    ) -> pd.DataFrame:
        """Build features for stored candles."""
        started_at = perf_counter()
        fingerprint = self._repository.get_fingerprint(symbol, timeframe)
        if fingerprint.row_count == 0:
            raise ValueError(f"No candles found for symbol={symbol} timeframe={timeframe}.")

        should_drop = (
            self._settings.features.drop_warmup_rows
            if drop_warmup_rows is None
            else drop_warmup_rows
        )
        cache_key = (
            symbol,
            timeframe,
            should_drop,
            fingerprint.row_count,
            fingerprint.latest_timestamp.isoformat() if fingerprint.latest_timestamp else None,
        )
        cached = self._cache.get(cache_key)
        if cached is not None:
            self._logger.debug(
                "Feature cache hit: symbol=%s timeframe=%s rows=%s",
                symbol,
                timeframe,
                len(cached),
            )
            return cached.copy(deep=True)

        candles = self._repository.list_candles(symbol=symbol, timeframe=timeframe)
        raw = candles_to_dataframe(candles)
        features = self._builder.build(raw, drop_warmup_rows=should_drop)
        self._cache[cache_key] = features.copy(deep=True)
        if len(self._cache) > 16:
            oldest_key = next(iter(self._cache))
            self._cache.pop(oldest_key, None)
        self._logger.info(
            "Built feature dataset: symbol=%s timeframe=%s rows=%s columns=%s elapsed_ms=%.2f",
            symbol,
            timeframe,
            len(features),
            len(features.columns),
            (perf_counter() - started_at) * 1000,
        )
        return features

    def export_features_csv(
        self,
        symbol: str,
        timeframe: str,
        output_path: Path | None = None,
        drop_warmup_rows: bool | None = None,
    ) -> Path:
        """Build and export features to CSV."""
        features = self.build_features(symbol, timeframe, drop_warmup_rows)
        target_path = output_path or self._default_output_path(symbol, timeframe)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        features.to_csv(target_path, index=False)
        self._logger.info("Exported feature dataset to %s", target_path)
        return target_path

    def _default_output_path(self, symbol: str, timeframe: str) -> Path:
        """Return a stable CSV path for a feature dataset."""
        safe_symbol = symbol.replace("/", "_").replace(":", "_")
        return self._settings.features.output_dir / f"{safe_symbol}_{timeframe}_features.csv"


def candles_to_dataframe(candles: list[Candle]) -> pd.DataFrame:
    """Convert Candle objects to the canonical input DataFrame."""
    return pd.DataFrame(
        [
            {
                "timestamp": candle.timestamp,
                "open": candle.open,
                "high": candle.high,
                "low": candle.low,
                "close": candle.close,
                "volume": candle.volume,
            }
            for candle in candles
        ],
    )
