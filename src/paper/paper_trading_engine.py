"""Paper trading engine for simulated realtime execution."""

from __future__ import annotations

from datetime import UTC, datetime
import logging
import sqlite3
from typing import Mapping

from config.settings import PaperTradingSettings
from database.connection import Database
from paper.account import PaperAccountSnapshot, PaperTrade, PaperTradingAccount
from signal.models import SignalType, TradeSetup


class PaperTradingEngine:
    """Simulates trade lifecycle locally without sending real orders."""

    def __init__(
        self,
        database: Database,
        settings: PaperTradingSettings,
        logger: logging.Logger | None = None,
    ) -> None:
        self._database = database
        self._settings = settings
        self._logger = logger or logging.getLogger("localquant.paper")

    def process_setup(
        self,
        setup: TradeSetup,
        candle: Mapping[str, object],
    ) -> PaperTradingAccount:
        """Update open trades with a candle, then open a new simulated trade if eligible."""
        timestamp = _as_datetime(candle.get("timestamp", setup.timestamp))
        mark_price = _as_float(candle.get("close"), default=float(setup.entry or 0.0))
        if not self._settings.enabled:
            return self.load_account(mark_price=mark_price, timestamp=timestamp)

        self.update_positions(candle)
        if self._settings.enabled and self._can_open(setup):
            self._open_trade(setup)
        account = self.load_account(
            mark_price=mark_price,
            timestamp=timestamp,
        )
        self._save_snapshot(account, timestamp)
        return self.load_account(mark_price=mark_price)

    def update_positions(self, candle: Mapping[str, object]) -> list[PaperTrade]:
        """Close open paper trades when the latest candle touches TP or SL."""
        closed: list[PaperTrade] = []
        timestamp = _as_datetime(candle.get("timestamp", datetime.now(UTC)))
        high = _as_float(candle.get("high"))
        low = _as_float(candle.get("low"))
        for trade in self._open_positions():
            exit_price, result = _exit_for_candle(trade, high=high, low=low)
            if exit_price is None or result is None:
                continue
            pnl = _pnl(trade, exit_price)
            self._database.execute(
                """
                UPDATE paper_trades
                SET status = 'CLOSED',
                    closed_at = ?,
                    exit_price = ?,
                    pnl = ?,
                    result = ?
                WHERE id = ?
                """,
                (timestamp.isoformat(), exit_price, pnl, result, trade.id),
            )
            closed.append(
                PaperTrade(
                    **{
                        **trade.to_dict(),
                        "status": "CLOSED",
                        "closed_at": timestamp,
                        "exit_price": exit_price,
                        "pnl": pnl,
                        "result": result,
                    }
                )
            )
            self._logger.info(
                "Paper trade closed: id=%s symbol=%s result=%s pnl=%.4f",
                trade.id,
                trade.symbol,
                result,
                pnl,
            )
        return closed

    def load_account(
        self,
        mark_price: float | None = None,
        timestamp: datetime | None = None,
    ) -> PaperTradingAccount:
        """Return current paper account state."""
        open_positions = self._open_positions()
        closed_trades = self._closed_trades()
        realized_pnl = sum(trade.pnl for trade in closed_trades)
        current_balance = self._settings.initial_balance + realized_pnl
        mark = mark_price if mark_price is not None else _latest_mark(open_positions)
        unrealized_pnl = sum(_pnl(trade, mark) for trade in open_positions) if mark else 0.0
        equity = current_balance + unrealized_pnl
        drawdown = self._drawdown(equity)
        snapshots = self._snapshots()
        return PaperTradingAccount(
            initial_balance=self._settings.initial_balance,
            current_balance=current_balance,
            realized_pnl=realized_pnl,
            unrealized_pnl=unrealized_pnl,
            equity=equity,
            drawdown=drawdown,
            open_positions=open_positions,
            closed_trades=closed_trades,
            snapshots=snapshots,
        )

    def _can_open(self, setup: TradeSetup) -> bool:
        """Return True when setup is actionable and no position is open."""
        if setup.signal not in {SignalType.BUY, SignalType.SELL}:
            return False
        if self._open_positions():
            return False
        required = [
            setup.entry,
            setup.stop_loss,
            setup.take_profit_1,
            setup.take_profit_2,
            setup.position_size,
            setup.risk_reward,
        ]
        if any(value is None for value in required):
            return False
        return float(setup.risk_reward or 0.0) > 0.0

    def _open_trade(self, setup: TradeSetup) -> None:
        """Persist one simulated open trade."""
        self._database.execute(
            """
            INSERT INTO paper_trades (
                symbol,
                timeframe,
                direction,
                strategy,
                status,
                opened_at,
                entry,
                stop_loss,
                take_profit_1,
                take_profit_2,
                position_size,
                confidence
            )
            VALUES (?, ?, ?, ?, 'OPEN', ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                setup.symbol,
                setup.timeframe,
                setup.signal.value,
                setup.strategy.value,
                _as_datetime(setup.timestamp).isoformat(),
                float(setup.entry or 0.0),
                float(setup.stop_loss or 0.0),
                float(setup.take_profit_1 or 0.0),
                float(setup.take_profit_2 or 0.0),
                float(setup.position_size or 0.0),
                setup.confidence,
            ),
        )
        self._logger.info(
            "Paper trade opened: symbol=%s timeframe=%s direction=%s",
            setup.symbol,
            setup.timeframe,
            setup.signal.value,
        )

    def _save_snapshot(self, account: PaperTradingAccount, timestamp: datetime) -> None:
        """Persist one account snapshot."""
        self._database.execute(
            """
            INSERT INTO paper_account_snapshots (
                timestamp,
                initial_balance,
                current_balance,
                realized_pnl,
                unrealized_pnl,
                equity,
                drawdown
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                timestamp.isoformat(),
                account.initial_balance,
                account.current_balance,
                account.realized_pnl,
                account.unrealized_pnl,
                account.equity,
                account.drawdown,
            ),
        )

    def _open_positions(self) -> list[PaperTrade]:
        """Load open paper trades."""
        rows = self._database.execute(
            """
            SELECT *
            FROM paper_trades
            WHERE status = 'OPEN'
            ORDER BY opened_at ASC
            """
        ).fetchall()
        return [_row_to_trade(row) for row in rows]

    def _closed_trades(self) -> list[PaperTrade]:
        """Load closed paper trades."""
        rows = self._database.execute(
            """
            SELECT *
            FROM paper_trades
            WHERE status = 'CLOSED'
            ORDER BY closed_at DESC
            LIMIT 200
            """
        ).fetchall()
        return [_row_to_trade(row) for row in rows]

    def _snapshots(self) -> list[PaperAccountSnapshot]:
        """Load account snapshots for the equity curve."""
        rows = self._database.execute(
            """
            SELECT timestamp, initial_balance, current_balance, realized_pnl,
                   unrealized_pnl, equity, drawdown
            FROM paper_account_snapshots
            ORDER BY timestamp ASC
            LIMIT 1000
            """
        ).fetchall()
        return [
            PaperAccountSnapshot(
                timestamp=_parse_datetime(row["timestamp"]),
                initial_balance=float(row["initial_balance"]),
                current_balance=float(row["current_balance"]),
                realized_pnl=float(row["realized_pnl"]),
                unrealized_pnl=float(row["unrealized_pnl"]),
                equity=float(row["equity"]),
                drawdown=float(row["drawdown"]),
            )
            for row in rows
        ]

    def _drawdown(self, equity: float) -> float:
        """Calculate absolute drawdown from historical snapshot peak."""
        row = self._database.execute(
            "SELECT MAX(equity) AS peak_equity FROM paper_account_snapshots"
        ).fetchone()
        peak = float(row["peak_equity"]) if row and row["peak_equity"] is not None else equity
        return max(0.0, peak - equity)


def _row_to_trade(row: sqlite3.Row) -> PaperTrade:
    """Convert a SQLite row into a paper trade."""
    return PaperTrade(
        id=int(row["id"]),
        symbol=str(row["symbol"]),
        timeframe=str(row["timeframe"]),
        direction=str(row["direction"]),
        strategy=str(row["strategy"]),
        status=str(row["status"]),
        opened_at=_parse_datetime(row["opened_at"]),
        closed_at=_parse_datetime(row["closed_at"]) if row["closed_at"] else None,
        entry=float(row["entry"]),
        stop_loss=float(row["stop_loss"]),
        take_profit_1=float(row["take_profit_1"]),
        take_profit_2=float(row["take_profit_2"]),
        position_size=float(row["position_size"]),
        confidence=float(row["confidence"]),
        exit_price=float(row["exit_price"]) if row["exit_price"] is not None else None,
        pnl=float(row["pnl"] or 0.0),
        result=str(row["result"]) if row["result"] else None,
    )


def _exit_for_candle(trade: PaperTrade, high: float, low: float) -> tuple[float | None, str | None]:
    """Return conservative TP/SL exit for a candle."""
    if trade.direction == SignalType.BUY.value:
        if low <= trade.stop_loss:
            return trade.stop_loss, "LOSS"
        if high >= trade.take_profit_2:
            return trade.take_profit_2, "WIN"
        return None, None

    if high >= trade.stop_loss:
        return trade.stop_loss, "LOSS"
    if low <= trade.take_profit_2:
        return trade.take_profit_2, "WIN"
    return None, None


def _pnl(trade: PaperTrade, mark_price: float) -> float:
    """Calculate paper PnL at a mark or exit price."""
    if trade.direction == SignalType.BUY.value:
        return (mark_price - trade.entry) * trade.position_size
    return (trade.entry - mark_price) * trade.position_size


def _latest_mark(open_positions: list[PaperTrade]) -> float | None:
    """Return a fallback mark price from the latest open trade entry."""
    if not open_positions:
        return None
    return open_positions[-1].entry


def _as_datetime(value: object) -> datetime:
    """Parse datetime-like values into timezone-aware datetimes."""
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    parsed = datetime.fromisoformat(str(value))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _parse_datetime(value: str) -> datetime:
    """Parse ISO datetime from SQLite."""
    return _as_datetime(value)


def _as_float(value: object, default: float = 0.0) -> float:
    """Parse a float value with a fallback."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
