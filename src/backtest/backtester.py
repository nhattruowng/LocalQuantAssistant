"""Candle-by-candle backtesting engine."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Any, Protocol

import pandas as pd

from backtest.metrics import build_report
from backtest.models import BacktestReport, Trade, TradeResult
from config.settings import Settings
from regime.market_regime import MarketRegime
from signal.models import SignalType, TradeSetup
from signal.signal_engine import SignalEngine


class ProbabilityProvider(Protocol):
    """Provides BUY/SELL/WAIT probabilities for the current feature row."""

    mode: str

    def predict_proba(self, row: pd.Series) -> dict[str, float]:
        """Return probabilities keyed by BUY, SELL, and WAIT."""


@dataclass
class RuleOnlyProbabilityProvider:
    """Simple rule-only probabilities from regime and indicators."""

    mode: str = "rule_only"

    def predict_proba(self, row: pd.Series) -> dict[str, float]:
        """Return deterministic probabilities without an ML model."""
        regime = str(row.get("market_regime", MarketRegime.UNKNOWN.value))
        rsi = float(row.get("rsi_14", 50.0))
        if regime in {MarketRegime.UPTREND.value, MarketRegime.BREAKOUT_UP.value}:
            return {"BUY": 0.70, "SELL": 0.10, "WAIT": 0.20}
        if regime in {MarketRegime.DOWNTREND.value, MarketRegime.BREAKOUT_DOWN.value}:
            return {"BUY": 0.10, "SELL": 0.70, "WAIT": 0.20}
        if regime == MarketRegime.SIDEWAY.value and rsi < 35:
            return {"BUY": 0.62, "SELL": 0.10, "WAIT": 0.28}
        if regime == MarketRegime.SIDEWAY.value and rsi > 65:
            return {"BUY": 0.10, "SELL": 0.62, "WAIT": 0.28}
        return {"BUY": 0.15, "SELL": 0.15, "WAIT": 0.70}


class ModelProbabilityProvider:
    """Probability provider backed by a saved sklearn-like model."""

    mode = "ml_enhanced"

    def __init__(self, model: Any, feature_columns: list[str]) -> None:
        self._model = model
        self._feature_columns = feature_columns

    @classmethod
    def from_files(
        cls,
        model_path: Path,
        metadata_path: Path | None = None,
    ) -> "ModelProbabilityProvider":
        """Load a model and feature columns from disk."""
        import json
        import joblib

        model = joblib.load(model_path)
        feature_columns: list[str] | None = None
        if metadata_path is not None and metadata_path.exists():
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            feature_columns = list(metadata.get("feature_columns", []))
        if feature_columns is None or not feature_columns:
            raise ValueError("Model metadata must provide feature_columns for backtesting.")
        return cls(model=model, feature_columns=feature_columns)

    def predict_proba(self, row: pd.Series) -> dict[str, float]:
        """Return model probabilities for one feature row."""
        x = pd.DataFrame([{column: row[column] for column in self._feature_columns}])
        probabilities = self._model.predict_proba(x)[0]
        classes = getattr(self._model, "classes_", ["BUY", "SELL", "WAIT"])
        return {str(label): float(probability) for label, probability in zip(classes, probabilities)}


class Backtester:
    """Runs candle-by-candle signal simulation without overlapping positions."""

    def __init__(
        self,
        settings: Settings,
        signal_engine: SignalEngine | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._settings = settings
        self._signal_engine = signal_engine or SignalEngine(settings)
        self._logger = logger or logging.getLogger("localquant.backtest")

    def run(
        self,
        features: pd.DataFrame,
        symbol: str,
        timeframe: str,
        probability_provider: ProbabilityProvider,
    ) -> BacktestReport:
        """Run a backtest over feature rows."""
        self._validate_features(features)
        data = features.sort_values("timestamp").reset_index(drop=True)
        trades: list[Trade] = []
        index = 0
        while index < len(data) - 1:
            row = data.iloc[index]
            probabilities = probability_provider.predict_proba(row)
            setup = self._signal_engine.generate(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=row["timestamp"],
                market_regime=row.get("market_regime", MarketRegime.UNKNOWN.value),
                features=row.to_dict(),
                probabilities=probabilities,
            )
            if setup.signal is SignalType.WAIT:
                index += 1
                continue

            trade, close_index = self._simulate_trade(data, index, setup)
            trades.append(trade)
            cooldown = (
                self._settings.backtest.cooldown_bars_after_loss
                if trade.result is TradeResult.LOSS
                else 0
            )
            index = close_index + 1 + cooldown

        report = build_report(symbol, timeframe, probability_provider.mode, trades)
        self._logger.info(
            "Backtest completed: mode=%s trades=%s net_profit=%.4f",
            probability_provider.mode,
            report.total_trades,
            report.net_profit,
        )
        return report

    def _validate_features(self, features: pd.DataFrame) -> None:
        """Validate required backtest columns."""
        required = [
            "timestamp",
            "high",
            "low",
            "close",
            "market_regime",
            "atr_14",
        ]
        missing = [column for column in required if column not in features]
        if missing:
            raise ValueError(f"Backtest features are missing columns: {missing}.")
        if features.empty:
            raise ValueError("Backtest features must not be empty.")

    def _simulate_trade(
        self,
        data: pd.DataFrame,
        signal_index: int,
        setup: TradeSetup,
    ) -> tuple[Trade, int]:
        """Simulate one trade from the next candle after signal generation."""
        if setup.entry is None or setup.stop_loss is None or setup.take_profit_2 is None:
            raise ValueError("Actionable setup requires entry, stop loss, and take profit.")

        entry_raw = setup.entry
        entry_fill = _apply_entry_slippage(
            entry_raw,
            setup.signal,
            self._settings.backtest.slippage_rate,
        )
        position_size = float(setup.position_size or 0.0)
        max_close_index = min(
            signal_index + self._settings.backtest.max_holding_bars,
            len(data) - 1,
        )
        exit_raw = float(data.iloc[max_close_index]["close"])
        close_index = max_close_index
        result = TradeResult.TIMEOUT

        for index in range(signal_index + 1, max_close_index + 1):
            row = data.iloc[index]
            high = float(row["high"])
            low = float(row["low"])
            if setup.signal is SignalType.BUY:
                if low <= setup.stop_loss:
                    exit_raw = setup.stop_loss
                    close_index = index
                    result = TradeResult.LOSS
                    break
                if high >= setup.take_profit_2:
                    exit_raw = setup.take_profit_2
                    close_index = index
                    result = TradeResult.WIN
                    break
            else:
                if high >= setup.stop_loss:
                    exit_raw = setup.stop_loss
                    close_index = index
                    result = TradeResult.LOSS
                    break
                if low <= setup.take_profit_2:
                    exit_raw = setup.take_profit_2
                    close_index = index
                    result = TradeResult.WIN
                    break

        exit_fill = _apply_exit_slippage(
            exit_raw,
            setup.signal,
            self._settings.backtest.slippage_rate,
        )
        gross_pnl = _gross_pnl(setup.signal, entry_fill, exit_fill, position_size)
        entry_fee = abs(entry_fill * position_size) * self._settings.backtest.fee_rate
        exit_fee = abs(exit_fill * position_size) * self._settings.backtest.fee_rate
        fees = entry_fee + exit_fee
        slippage_cost = (
            abs(entry_fill - entry_raw) * position_size
            + abs(exit_fill - exit_raw) * position_size
        )
        pnl = gross_pnl - fees
        if result is TradeResult.TIMEOUT:
            result = _timeout_result(pnl)

        return (
            Trade(
                symbol=setup.symbol,
                timeframe=setup.timeframe,
                direction=setup.signal,
                strategy=setup.strategy,
                opened_at=setup.timestamp,
                closed_at=data.iloc[close_index]["timestamp"],
                entry=entry_fill,
                stop_loss=setup.stop_loss,
                take_profit_1=float(setup.take_profit_1 or setup.take_profit_2),
                take_profit_2=setup.take_profit_2,
                exit_price=exit_fill,
                position_size=position_size,
                gross_pnl=gross_pnl,
                fees=fees,
                slippage=slippage_cost,
                pnl=pnl,
                risk_reward=float(setup.risk_reward or 0.0),
                result=result,
                confidence=setup.confidence,
                reasons=setup.reasons,
            ),
            close_index,
        )


def _apply_entry_slippage(price: float, signal: SignalType, slippage_rate: float) -> float:
    """Apply adverse entry slippage."""
    if signal is SignalType.BUY:
        return price * (1.0 + slippage_rate)
    return price * (1.0 - slippage_rate)


def _apply_exit_slippage(price: float, signal: SignalType, slippage_rate: float) -> float:
    """Apply adverse exit slippage."""
    if signal is SignalType.BUY:
        return price * (1.0 - slippage_rate)
    return price * (1.0 + slippage_rate)


def _gross_pnl(
    signal: SignalType,
    entry: float,
    exit_price: float,
    position_size: float,
) -> float:
    """Calculate gross PnL before fees."""
    if signal is SignalType.BUY:
        return (exit_price - entry) * position_size
    return (entry - exit_price) * position_size


def _timeout_result(pnl: float) -> TradeResult:
    """Classify timeout trade by net PnL."""
    if pnl > 0:
        return TradeResult.WIN
    if pnl < 0:
        return TradeResult.LOSS
    return TradeResult.BREAKEVEN
