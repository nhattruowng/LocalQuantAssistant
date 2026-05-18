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
    backtest_parser.add_argument("--model", help="Optional path to a saved .joblib model.")
    backtest_parser.add_argument(
        "--metadata",
        help="Optional path to model metadata JSON. Defaults to <model>.metadata.json.",
    )
    backtest_parser.add_argument(
        "--cost-model",
        choices=["fixed", "volatility_adjusted", "spread_aware", "stress"],
        help="Override the configured execution cost model.",
    )
    backtest_parser.add_argument(
        "--compare-cost-scenarios",
        action="store_true",
        help="Also export normal, high_slippage, stress, and zero_slippage comparison reports.",
    )

    stress_parser = subparsers.add_parser("backtest-stress", help="Backtest with stress execution costs.")
    stress_parser.add_argument("--symbol", required=True, help="Symbol, e.g. BTC/USDT.")
    stress_parser.add_argument("--timeframe", required=True, help="Timeframe, e.g. 15m.")
    stress_parser.add_argument("--model", help="Optional path to a saved .joblib model.")
    stress_parser.add_argument(
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
            model_path=Path(args.model) if args.model else None,
            metadata_path=Path(args.metadata) if args.metadata else None,
            cost_model=args.cost_model,
            compare_cost_scenarios=args.compare_cost_scenarios,
        )
        return
    if args.command == "backtest-stress":
        _run_backtest(
            symbol=args.symbol,
            timeframe=args.timeframe,
            model_path=Path(args.model) if args.model else None,
            metadata_path=Path(args.metadata) if args.metadata else None,
            cost_model="stress",
            compare_cost_scenarios=True,
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
    model_path: Path | None,
    metadata_path: Path | None,
    cost_model: str | None,
    compare_cost_scenarios: bool = False,
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
    backtester = Backtester(settings=settings, cost_model_name=cost_model, logger=logger)
    writer = BacktestReportWriter(settings.backtest.output_dir)

    rule_report = backtester.run(
        features=features,
        symbol=symbol,
        timeframe=timeframe,
        probability_provider=RuleOnlyProbabilityProvider(),
    )
    rule_trades_path, rule_summary_path, rule_report_path, rule_html_path = writer.write(rule_report)
    if compare_cost_scenarios:
        scenario_reports = backtester.run_cost_scenarios(
            features=features,
            symbol=symbol,
            timeframe=timeframe,
            probability_provider=RuleOnlyProbabilityProvider(),
        )
        scenario_json_path, scenario_html_path = writer.write_scenario_comparison(
            symbol=symbol,
            timeframe=timeframe,
            reports=scenario_reports,
        )
    else:
        scenario_json_path = scenario_html_path = None

    ml_report = None
    ml_trades_path = ml_summary_path = ml_report_path = ml_html_path = None
    ml_scenario_json_path = ml_scenario_html_path = None
    if model_path is not None:
        metadata = metadata_path or model_path.with_suffix(".metadata.json")
        provider = ModelProbabilityProvider.from_files(
            model_path,
            metadata,
            use_calibrated_probability=settings.signal.use_calibrated_probability,
        )
        ml_report = backtester.run(
            features=features,
            symbol=symbol,
            timeframe=timeframe,
            probability_provider=provider,
        )
        ml_trades_path, ml_summary_path, ml_report_path, ml_html_path = writer.write(ml_report)
        if compare_cost_scenarios:
            ml_scenario_reports = backtester.run_cost_scenarios(
                features=features,
                symbol=symbol,
                timeframe=timeframe,
                probability_provider=provider,
            )
            ml_scenario_json_path, ml_scenario_html_path = writer.write_scenario_comparison(
                symbol=symbol,
                timeframe=f"{timeframe}_ml",
                reports=ml_scenario_reports,
            )
    database.close()

    print(f"Rule-only backtest cost_model={cost_model or settings.backtest.execution_cost.model}")
    print(f"Trades: {rule_report.total_trades} Net profit: {rule_report.net_profit:.4f}")
    print(f"Trades CSV: {rule_trades_path}")
    print(f"Summary JSON: {rule_summary_path}")
    print(f"Full JSON: {rule_report_path}")
    print(f"HTML report: {rule_html_path}")
    if scenario_json_path is not None and scenario_html_path is not None:
        print(f"Scenario comparison JSON: {scenario_json_path}")
        print(f"Scenario comparison HTML: {scenario_html_path}")
    if ml_report is not None:
        print("ML-enhanced backtest")
        print(f"Trades: {ml_report.total_trades} Net profit: {ml_report.net_profit:.4f}")
        print(f"Trades CSV: {ml_trades_path}")
        print(f"Summary JSON: {ml_summary_path}")
        print(f"Full JSON: {ml_report_path}")
        print(f"HTML report: {ml_html_path}")
        if ml_scenario_json_path is not None and ml_scenario_html_path is not None:
            print(f"ML scenario comparison JSON: {ml_scenario_json_path}")
            print(f"ML scenario comparison HTML: {ml_scenario_html_path}")


if __name__ == "__main__":
    main()
