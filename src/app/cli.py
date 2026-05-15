"""Command-line UI for LocalQuant Assistant."""

from __future__ import annotations

from agents.trading_orchestrator_agent import TradingOrchestratorAgent
from config.loader import load_settings
from database.connection import create_database
from utils.logger import setup_logger


def run_cli() -> None:
    """Run a minimal local recommendation workflow."""
    settings = load_settings()
    logger = setup_logger(settings.logging)
    logger.info("Starting %s", settings.app.name)

    database = create_database(settings.database)
    database.initialize()
    database.close()

    orchestrator = TradingOrchestratorAgent(settings=settings, logger=logger)
    trade_setup = orchestrator.analyze(symbol="BTCUSDT")

    logger.info(
        "Trade setup generated: symbol=%s action=%s confidence=%.2f",
        trade_setup.symbol,
        trade_setup.action.value,
        trade_setup.confidence,
    )
    print(trade_setup.to_display_text())
    print(trade_setup.explanation)
