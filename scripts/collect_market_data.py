"""CLI script for updating local OHLCV candle data."""

from __future__ import annotations

from pathlib import Path
import argparse
import sys


ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from collector.binance_collector import BinanceCollector
from collector.update_service import MarketDataUpdateService
from config.loader import load_settings
from database.candle_repository import CandleRepository
from database.connection import create_database
from utils.logger import setup_logger


def main() -> None:
    """Run the Binance collector from the command line."""
    parser = argparse.ArgumentParser(description="Update local OHLCV candles.")
    parser.add_argument("--symbol", action="append", help="Symbol to update, e.g. BTC/USDT.")
    parser.add_argument("--timeframe", action="append", help="Timeframe to update, e.g. 1h.")
    args = parser.parse_args()

    settings = load_settings()
    logger = setup_logger(settings.logging)
    database = create_database(settings.database)
    database.initialize()

    collector = BinanceCollector(
        retry_attempts=settings.collector.retry_attempts,
        retry_delay_seconds=settings.collector.retry_delay_seconds,
        logger=logger,
    )
    repository = CandleRepository(database)
    service = MarketDataUpdateService(
        collector=collector,
        repository=repository,
        settings=settings.collector,
        logger=logger,
    )

    inserted = service.update_latest(
        symbols=tuple(args.symbol) if args.symbol else None,
        timeframes=tuple(args.timeframe) if args.timeframe else None,
    )
    database.close()
    print(f"Inserted {inserted} new candles.")


if __name__ == "__main__":
    main()
