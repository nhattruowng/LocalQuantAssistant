"""CLI entrypoint for LocalQuant Assistant."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from app.cli import run_cli


def main() -> None:
    """Route CLI commands."""
    parser = argparse.ArgumentParser(description="LocalQuant Assistant")
    subparsers = parser.add_subparsers(dest="command")

    train_parser = subparsers.add_parser("train", help="Train a local setup model.")
    train_parser.add_argument("--symbol", required=True, help="Symbol, e.g. BTC/USDT.")
    train_parser.add_argument("--timeframe", required=True, help="Timeframe, e.g. 15m.")

    args = parser.parse_args()
    if args.command == "train":
        _run_train(symbol=args.symbol, timeframe=args.timeframe)
        return

    run_cli()


def _run_train(symbol: str, timeframe: str) -> None:
    """Train a setup classifier from stored candles."""
    from config.loader import load_settings
    from database.candle_repository import CandleRepository
    from database.connection import create_database
    from features.feature_service import FeatureService
    from ml.model_trainer import ModelTrainer
    from utils.logger import setup_logger

    settings = load_settings()
    logger = setup_logger(settings.logging)
    database = create_database(settings.database)
    database.initialize()

    feature_service = FeatureService(
        repository=CandleRepository(database),
        settings=settings,
        logger=logger,
    )
    features = feature_service.build_features(
        symbol=symbol,
        timeframe=timeframe,
        drop_warmup_rows=True,
    )
    result = ModelTrainer(settings=settings, logger=logger).train(
        features=features,
        symbol=symbol,
        timeframe=timeframe,
    )
    database.close()

    print(f"Trained {result.model_type}")
    print(f"Model: {result.model_path}")
    print(f"Metadata: {result.metadata_path}")
    print(f"Validation accuracy: {result.metrics['validation']['accuracy']:.4f}")
    print(f"Test accuracy: {result.metrics['test']['accuracy']:.4f}")


if __name__ == "__main__":
    main()
