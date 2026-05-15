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

    backtest_parser = subparsers.add_parser("backtest", help="Backtest setup signals.")
    backtest_parser.add_argument("--symbol", required=True, help="Symbol, e.g. BTC/USDT.")
    backtest_parser.add_argument("--timeframe", required=True, help="Timeframe, e.g. 15m.")
    backtest_parser.add_argument("--model", required=True, help="Path to a saved .joblib model.")
    backtest_parser.add_argument(
        "--metadata",
        help="Optional path to model metadata JSON. Defaults to <model>.metadata.json.",
    )

    args = parser.parse_args()
    if args.command == "train":
        _run_train(symbol=args.symbol, timeframe=args.timeframe)
        return
    if args.command == "backtest":
        _run_backtest(
            symbol=args.symbol,
            timeframe=args.timeframe,
            model_path=Path(args.model),
            metadata_path=Path(args.metadata) if args.metadata else None,
        )
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


def _run_backtest(
    symbol: str,
    timeframe: str,
    model_path: Path,
    metadata_path: Path | None,
) -> None:
    """Run rule-only and ML-enhanced backtests from stored candles."""
    from backtest.backtester import (
        Backtester,
        ModelProbabilityProvider,
        RuleOnlyProbabilityProvider,
    )
    from backtest.report_writer import BacktestReportWriter
    from config.loader import load_settings
    from database.candle_repository import CandleRepository
    from database.connection import create_database
    from features.feature_service import FeatureService
    from utils.logger import setup_logger

    settings = load_settings()
    logger = setup_logger(settings.logging)
    database = create_database(settings.database)
    database.initialize()

    features = FeatureService(
        repository=CandleRepository(database),
        settings=settings,
        logger=logger,
    ).build_features(symbol=symbol, timeframe=timeframe, drop_warmup_rows=True)
    backtester = Backtester(settings=settings, logger=logger)
    writer = BacktestReportWriter(settings.backtest.output_dir)

    rule_report = backtester.run(
        features=features,
        symbol=symbol,
        timeframe=timeframe,
        probability_provider=RuleOnlyProbabilityProvider(),
    )
    rule_trades_path, rule_summary_path = writer.write(rule_report)

    metadata = metadata_path or model_path.with_suffix(".metadata.json")
    ml_report = backtester.run(
        features=features,
        symbol=symbol,
        timeframe=timeframe,
        probability_provider=ModelProbabilityProvider.from_files(model_path, metadata),
    )
    ml_trades_path, ml_summary_path = writer.write(ml_report)
    database.close()

    print("Rule-only backtest")
    print(f"Trades: {rule_report.total_trades} Net profit: {rule_report.net_profit:.4f}")
    print(f"Trades CSV: {rule_trades_path}")
    print(f"Summary JSON: {rule_summary_path}")
    print("ML-enhanced backtest")
    print(f"Trades: {ml_report.total_trades} Net profit: {ml_report.net_profit:.4f}")
    print(f"Trades CSV: {ml_trades_path}")
    print(f"Summary JSON: {ml_summary_path}")


if __name__ == "__main__":
    main()
