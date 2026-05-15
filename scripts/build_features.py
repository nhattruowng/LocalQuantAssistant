"""CLI script for building feature datasets from stored candles."""

from __future__ import annotations

from pathlib import Path
import argparse
import sys


ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


def main() -> None:
    """Build and export features for a symbol/timeframe pair."""
    parser = argparse.ArgumentParser(description="Build technical feature dataset.")
    parser.add_argument("--symbol", required=True, help="Symbol, e.g. BTC/USDT.")
    parser.add_argument("--timeframe", required=True, help="Timeframe, e.g. 1h.")
    parser.add_argument("--output", help="Optional CSV output path.")
    parser.add_argument(
        "--keep-warmup",
        action="store_true",
        help="Keep rows with warmup NaNs from rolling indicators.",
    )
    args = parser.parse_args()

    from config.loader import load_settings
    from database.candle_repository import CandleRepository
    from database.connection import create_database
    from features.feature_service import FeatureService
    from utils.logger import setup_logger

    settings = load_settings()
    logger = setup_logger(settings.logging)
    database = create_database(settings.database)
    database.initialize()

    service = FeatureService(
        repository=CandleRepository(database),
        settings=settings,
        logger=logger,
    )
    output_path = service.export_features_csv(
        symbol=args.symbol,
        timeframe=args.timeframe,
        output_path=Path(args.output) if args.output else None,
        drop_warmup_rows=not args.keep_warmup,
    )
    database.close()
    print(f"Features exported to {output_path}")


if __name__ == "__main__":
    main()
