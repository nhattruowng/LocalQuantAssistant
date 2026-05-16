"""Simple local benchmark for feature building and backtesting."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from time import perf_counter

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from backtest.backtester import Backtester, RuleOnlyProbabilityProvider  # noqa: E402
from config.loader import load_settings  # noqa: E402
from features.feature_builder import FeatureBuilder  # noqa: E402


def main() -> None:
    """Run a deterministic benchmark without external API calls."""
    parser = argparse.ArgumentParser(description="Benchmark LocalQuant core pipeline.")
    parser.add_argument("--rows", type=int, default=5_000, help="Synthetic candle rows.")
    args = parser.parse_args()

    settings = load_settings()
    candles = _synthetic_candles(args.rows)

    feature_started = perf_counter()
    builder = FeatureBuilder(settings.feature_toggles, settings.market_regime)
    features = builder.build(candles, drop_warmup_rows=True)
    feature_elapsed = perf_counter() - feature_started

    backtest_started = perf_counter()
    report = Backtester(settings).run(
        features=features,
        symbol="BTC/USDT",
        timeframe="15m",
        probability_provider=RuleOnlyProbabilityProvider(),
    )
    backtest_elapsed = perf_counter() - backtest_started

    print(f"Rows input: {len(candles):,}")
    print(f"Rows after warmup: {len(features):,}")
    print(f"Feature build: {feature_elapsed:.4f}s ({len(candles) / feature_elapsed:,.0f} rows/s)")
    print(f"Backtest: {backtest_elapsed:.4f}s ({len(features) / backtest_elapsed:,.0f} rows/s)")
    print(f"Trades: {report.total_trades:,} | Net profit: {report.net_profit:.2f}")


def _synthetic_candles(rows: int) -> pd.DataFrame:
    """Build deterministic OHLCV data for repeatable local benchmarking."""
    index = pd.Series(range(rows), dtype="float64")
    close = 100.0 + index * 0.02 + ((index % 17) * 0.05)
    open_price = close.shift(1).fillna(close.iloc[0])
    high = pd.concat([open_price, close], axis=1).max(axis=1) + 0.8
    low = pd.concat([open_price, close], axis=1).min(axis=1) - 0.8
    volume = 1_000.0 + (index % 50) * 10.0
    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-01-01", periods=rows, freq="15min", tz="UTC"),
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }
    )


if __name__ == "__main__":
    main()
