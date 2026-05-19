"""Strategy performance memory built from recent paper trades."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime, timedelta
import json
import math
from pathlib import Path
from typing import Iterable

from config.settings import AdaptiveStrategySettings
from paper.account import PaperTrade
from signals.models import SignalType, StrategyOpinion, StrategyType


@dataclass(frozen=True)
class RecentTradeSummary:
    """Compact closed trade summary used by memory snapshots."""

    trade_id: int | None
    result: str | None
    pnl: float
    r_multiple: float
    exit_reason: str | None
    opened_at: datetime | str
    closed_at: datetime | str | None

    def to_dict(self) -> dict[str, object]:
        """Serialize summary to JSON primitives."""
        data = asdict(self)
        data["opened_at"] = _iso_datetime(self.opened_at)
        data["closed_at"] = _iso_datetime(self.closed_at)
        return data


@dataclass(frozen=True)
class StrategyMemorySnapshot:
    """Recent performance snapshot for one strategy/regime/direction key."""

    symbol: str
    timeframe: str
    strategy_type: str
    regime: str
    direction: str
    recent_trades_count: int
    recent_winrate: float
    recent_profit_factor: float | None
    recent_expectancy: float
    recent_drawdown: float
    consecutive_losses: int
    average_r_multiple: float
    fakeout_count: int
    timeout_count: int
    last_updated_at: datetime | str
    recent_trades: list[RecentTradeSummary]

    @property
    def key(self) -> str:
        """Return stable snapshot key."""
        return memory_key(
            self.symbol,
            self.timeframe,
            self.strategy_type,
            self.regime,
            self.direction,
        )

    def to_dict(self) -> dict[str, object]:
        """Serialize snapshot to JSON primitives."""
        data = asdict(self)
        data["last_updated_at"] = _iso_datetime(self.last_updated_at)
        data["recent_trades"] = [trade.to_dict() for trade in self.recent_trades]
        return data


@dataclass(frozen=True)
class MemoryAdjustment:
    """Penalty, block, and size adjustments derived from recent performance."""

    strategy_type: str
    direction: str
    blocked: bool = False
    score_penalty: float = 0.0
    threshold_adjustment: float = 0.0
    size_multiplier: float = 1.0
    reasons: list[str] | None = None
    warnings: list[str] | None = None

    def to_dict(self) -> dict[str, object]:
        """Serialize adjustment for reports and API responses."""
        return {
            "strategy_type": self.strategy_type,
            "direction": self.direction,
            "blocked": self.blocked,
            "score_penalty": round(self.score_penalty, 4),
            "threshold_adjustment": round(self.threshold_adjustment, 4),
            "size_multiplier": round(self.size_multiplier, 4),
            "reasons": list(self.reasons or []),
            "warnings": list(self.warnings or []),
        }


@dataclass(frozen=True)
class StrategyPerformanceMemory:
    """Lookup table of strategy memory snapshots."""

    snapshots: dict[str, StrategyMemorySnapshot]

    def snapshot_for(
        self,
        symbol: str,
        timeframe: str,
        strategy_type: str | StrategyType,
        regime: str,
        direction: str | SignalType,
    ) -> StrategyMemorySnapshot | None:
        """Return the snapshot for a specific strategy memory key."""
        return self.snapshots.get(
            memory_key(symbol, timeframe, strategy_type, regime, direction)
        )

    def adjustment_for(
        self,
        symbol: str,
        timeframe: str,
        regime: str,
        opinion: StrategyOpinion,
        settings: AdaptiveStrategySettings,
    ) -> MemoryAdjustment | None:
        """Return a bounded adjustment for one strategy opinion."""
        if opinion.suggested_signal is SignalType.WAIT:
            return None
        snapshot = self.snapshot_for(
            symbol=symbol,
            timeframe=timeframe,
            strategy_type=opinion.strategy_type,
            regime=regime,
            direction=opinion.suggested_signal,
        )
        if snapshot is None:
            return None
        return memory_adjustment(snapshot, opinion.strategy_type, settings)

    def apply_to_opinion(
        self,
        symbol: str,
        timeframe: str,
        regime: str,
        opinion: StrategyOpinion,
        settings: AdaptiveStrategySettings,
    ) -> tuple[StrategyOpinion, MemoryAdjustment | None]:
        """Apply memory adjustment to an opinion without mutating the source."""
        adjustment = self.adjustment_for(symbol, timeframe, regime, opinion, settings)
        if adjustment is None:
            return opinion, None

        score = max(0.0, opinion.score - adjustment.score_penalty)
        size_multiplier = max(
            0.0,
            min(opinion.suggested_size_multiplier * adjustment.size_multiplier, 1.0),
        )
        warnings = [
            *opinion.warnings,
            *[f"Strategy memory: {warning}" for warning in adjustment.warnings or []],
        ]
        reasons = [
            *opinion.reasons,
            *[f"Strategy memory: {reason}" for reason in adjustment.reasons or []],
        ]
        if adjustment.blocked:
            score = 0.0
            size_multiplier = 0.0
            warnings.append("Strategy memory blocked this strategy after recent losses.")
        return (
            replace(
                opinion,
                score=round(score, 4),
                reasons=reasons,
                warnings=warnings,
                suggested_size_multiplier=round(size_multiplier, 4),
            ),
            adjustment,
        )

    def to_dict(self) -> dict[str, object]:
        """Serialize all snapshots to JSON primitives."""
        return {
            "snapshots": {
                key: snapshot.to_dict()
                for key, snapshot in sorted(self.snapshots.items())
            }
        }


class StrategyMemoryBuilder:
    """Builds strategy memory snapshots from recent closed trades."""

    def build(
        self,
        trades: Iterable[PaperTrade],
        lookback_trades: int = 30,
        lookback_bars: int | None = None,
        now: datetime | None = None,
    ) -> StrategyPerformanceMemory:
        """Aggregate closed paper trades into memory snapshots."""
        timestamp = now or datetime.now(UTC)
        grouped: dict[str, list[PaperTrade]] = {}
        for trade in trades:
            if trade.status != "CLOSED":
                continue
            key = memory_key(
                trade.symbol,
                trade.timeframe,
                trade.strategy,
                trade.market_regime,
                trade.direction,
            )
            grouped.setdefault(key, []).append(trade)

        snapshots: dict[str, StrategyMemorySnapshot] = {}
        for key, group in grouped.items():
            ordered = sorted(group, key=_trade_closed_at)
            if lookback_bars is not None and ordered:
                window_start = _bar_window_start(ordered[-1], lookback_bars)
                if window_start is not None:
                    ordered = [
                        trade
                        for trade in ordered
                        if _trade_closed_at(trade) >= window_start
                    ]
            recent = ordered[-lookback_trades:]
            if not recent:
                continue
            first = recent[-1]
            summaries = [_summary(trade) for trade in recent]
            snapshot = StrategyMemorySnapshot(
                symbol=first.symbol,
                timeframe=first.timeframe,
                strategy_type=first.strategy,
                regime=first.market_regime,
                direction=first.direction,
                recent_trades_count=len(recent),
                recent_winrate=_winrate(recent),
                recent_profit_factor=_profit_factor(recent),
                recent_expectancy=_expectancy(recent),
                recent_drawdown=_max_drawdown(recent),
                consecutive_losses=_consecutive_losses(recent),
                average_r_multiple=_average_r_multiple(recent),
                fakeout_count=_fakeout_count(recent),
                timeout_count=_timeout_count(recent),
                last_updated_at=timestamp,
                recent_trades=summaries,
            )
            snapshots[key] = snapshot
        return StrategyPerformanceMemory(snapshots=snapshots)


class StrategyMemoryStore:
    """JSON persistence for strategy performance memory."""

    def __init__(self, path: Path) -> None:
        self._path = path

    @property
    def path(self) -> Path:
        """Return memory file path."""
        return self._path

    def load(self) -> StrategyPerformanceMemory:
        """Load memory snapshots from disk."""
        if not self._path.exists():
            return StrategyPerformanceMemory(snapshots={})
        raw = json.loads(self._path.read_text(encoding="utf-8"))
        snapshots = {
            str(key): _snapshot_from_dict(value)
            for key, value in dict(raw.get("snapshots", {})).items()
            if isinstance(value, dict)
        }
        return StrategyPerformanceMemory(snapshots=snapshots)

    def save(self, memory: StrategyPerformanceMemory) -> None:
        """Persist memory snapshots to disk."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(memory.to_dict(), indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def refresh_from_trades(
        self,
        trades: Iterable[PaperTrade],
        settings: AdaptiveStrategySettings,
    ) -> StrategyPerformanceMemory:
        """Rebuild and save memory from closed trades."""
        memory = StrategyMemoryBuilder().build(
            trades=trades,
            lookback_trades=settings.memory_lookback_trades,
            lookback_bars=settings.memory_lookback_bars,
        )
        self.save(memory)
        return memory


def memory_key(
    symbol: str,
    timeframe: str,
    strategy_type: str | StrategyType,
    regime: str,
    direction: str | SignalType,
) -> str:
    """Build a stable strategy memory key."""
    strategy = strategy_type.value if isinstance(strategy_type, StrategyType) else str(strategy_type)
    signal = direction.value if isinstance(direction, SignalType) else str(direction)
    safe_symbol = symbol.replace("|", "_")
    return "|".join([safe_symbol, timeframe, strategy, str(regime), signal])


def memory_adjustment(
    snapshot: StrategyMemorySnapshot,
    strategy_type: StrategyType,
    settings: AdaptiveStrategySettings,
) -> MemoryAdjustment | None:
    """Convert one snapshot into bounded decision adjustments."""
    if snapshot.recent_trades_count < settings.memory_min_trades_required:
        return None

    reasons: list[str] = []
    warnings: list[str] = []
    score_penalty = 0.0
    threshold_adjustment = 0.0
    size_penalty = 0.0
    blocked = False

    if snapshot.consecutive_losses >= 2:
        penalty = min(
            settings.memory_max_score_penalty,
            0.08 * (snapshot.consecutive_losses - 1),
        )
        score_penalty += penalty
        reasons.append(
            f"{snapshot.strategy_type} has {snapshot.consecutive_losses} consecutive losses."
        )
    if (
        snapshot.consecutive_losses >= 3
        and settings.memory_block_after_consecutive_losses
    ):
        blocked = True
        warnings.append("Strategy temporarily blocked after 3 consecutive losses.")
    if snapshot.recent_profit_factor is not None and snapshot.recent_profit_factor < 1.0:
        adjustment = min(0.08, (1.0 - snapshot.recent_profit_factor) * 0.08)
        threshold_adjustment += adjustment
        reasons.append(
            f"Recent profit factor is weak ({snapshot.recent_profit_factor:.2f})."
        )
    if snapshot.recent_drawdown > 0 and (
        snapshot.recent_profit_factor is None
        or snapshot.recent_profit_factor < 1.0
        or snapshot.recent_expectancy < 0
    ):
        size_penalty += min(settings.memory_max_size_penalty, 0.25)
        warnings.append("Recent drawdown is elevated; position size reduced.")
    if (
        strategy_type is StrategyType.BREAKOUT_CONFIRMATION
        and snapshot.fakeout_count >= max(2, math.ceil(snapshot.recent_trades_count * 0.20))
    ):
        score_penalty += min(settings.memory_max_score_penalty, 0.06)
        threshold_adjustment += 0.03
        warnings.append("Breakout memory shows repeated fakeouts; require stronger confirmation.")
    if (
        strategy_type is StrategyType.MEAN_REVERSION
        and snapshot.regime == "SIDEWAY"
        and snapshot.consecutive_losses >= 2
        and (snapshot.recent_profit_factor is None or snapshot.recent_profit_factor < 1.0)
    ):
        score_penalty += min(settings.memory_max_score_penalty, 0.05)
        threshold_adjustment += 0.03
        warnings.append("Mean reversion in SIDEWAY is weak; range quality must be higher.")

    score_penalty = min(settings.memory_max_score_penalty, score_penalty)
    size_penalty = min(settings.memory_max_size_penalty, size_penalty)
    if not blocked and score_penalty <= 0 and threshold_adjustment <= 0 and size_penalty <= 0:
        return None
    return MemoryAdjustment(
        strategy_type=snapshot.strategy_type,
        direction=snapshot.direction,
        blocked=blocked,
        score_penalty=round(score_penalty, 4),
        threshold_adjustment=round(threshold_adjustment, 4),
        size_multiplier=round(max(0.0, 1.0 - size_penalty), 4),
        reasons=reasons,
        warnings=warnings,
    )


def _snapshot_from_dict(value: dict[str, object]) -> StrategyMemorySnapshot:
    """Deserialize a memory snapshot from JSON data."""
    return StrategyMemorySnapshot(
        symbol=str(value.get("symbol", "")),
        timeframe=str(value.get("timeframe", "")),
        strategy_type=str(value.get("strategy_type", "")),
        regime=str(value.get("regime", "UNKNOWN")),
        direction=str(value.get("direction", "")),
        recent_trades_count=int(value.get("recent_trades_count", 0)),
        recent_winrate=float(value.get("recent_winrate", 0.0)),
        recent_profit_factor=_optional_float(value.get("recent_profit_factor")),
        recent_expectancy=float(value.get("recent_expectancy", 0.0)),
        recent_drawdown=float(value.get("recent_drawdown", 0.0)),
        consecutive_losses=int(value.get("consecutive_losses", 0)),
        average_r_multiple=float(value.get("average_r_multiple", 0.0)),
        fakeout_count=int(value.get("fakeout_count", 0)),
        timeout_count=int(value.get("timeout_count", 0)),
        last_updated_at=str(value.get("last_updated_at", "")),
        recent_trades=[
            _recent_trade_from_dict(item)
            for item in list(value.get("recent_trades", []))
            if isinstance(item, dict)
        ],
    )


def _recent_trade_from_dict(value: dict[str, object]) -> RecentTradeSummary:
    """Deserialize a compact recent trade summary."""
    return RecentTradeSummary(
        trade_id=int(value["trade_id"]) if value.get("trade_id") is not None else None,
        result=str(value.get("result")) if value.get("result") is not None else None,
        pnl=float(value.get("pnl", 0.0)),
        r_multiple=float(value.get("r_multiple", 0.0)),
        exit_reason=str(value.get("exit_reason")) if value.get("exit_reason") is not None else None,
        opened_at=str(value.get("opened_at", "")),
        closed_at=str(value.get("closed_at")) if value.get("closed_at") is not None else None,
    )


def _summary(trade: PaperTrade) -> RecentTradeSummary:
    """Build one recent trade summary."""
    return RecentTradeSummary(
        trade_id=trade.id,
        result=trade.result,
        pnl=trade.pnl,
        r_multiple=_r_multiple(trade),
        exit_reason=_exit_reason(trade),
        opened_at=trade.opened_at,
        closed_at=trade.closed_at,
    )


def _winrate(trades: list[PaperTrade]) -> float:
    wins = sum(1 for trade in trades if trade.result == "WIN")
    return round(wins / len(trades), 4) if trades else 0.0


def _profit_factor(trades: list[PaperTrade]) -> float | None:
    gross_profit = sum(max(trade.pnl, 0.0) for trade in trades)
    gross_loss = abs(sum(min(trade.pnl, 0.0) for trade in trades))
    if gross_loss == 0:
        return None if gross_profit == 0 else None
    return round(gross_profit / gross_loss, 4)


def _expectancy(trades: list[PaperTrade]) -> float:
    return round(sum(trade.pnl for trade in trades) / len(trades), 4) if trades else 0.0


def _max_drawdown(trades: list[PaperTrade]) -> float:
    equity = 0.0
    peak = 0.0
    max_drawdown = 0.0
    for trade in trades:
        equity += trade.pnl
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, peak - equity)
    return round(max_drawdown, 4)


def _consecutive_losses(trades: list[PaperTrade]) -> int:
    count = 0
    for trade in reversed(trades):
        if trade.result != "LOSS":
            break
        count += 1
    return count


def _average_r_multiple(trades: list[PaperTrade]) -> float:
    if not trades:
        return 0.0
    return round(sum(_r_multiple(trade) for trade in trades) / len(trades), 4)


def _fakeout_count(trades: list[PaperTrade]) -> int:
    return sum(
        1
        for trade in trades
        if trade.strategy == StrategyType.BREAKOUT_CONFIRMATION.value
        and trade.result == "LOSS"
    )


def _timeout_count(trades: list[PaperTrade]) -> int:
    return sum(1 for trade in trades if _exit_reason(trade) == "TIMEOUT")


def _r_multiple(trade: PaperTrade) -> float:
    risk = abs(trade.entry - trade.stop_loss) * max(trade.position_size, 0.0)
    if risk <= 0:
        return 0.0
    return round(trade.pnl / risk, 4)


def _exit_reason(trade: PaperTrade) -> str | None:
    if trade.result == "LOSS":
        return "STOP_LOSS"
    if trade.result == "WIN":
        return "TAKE_PROFIT"
    if trade.result == "TIMEOUT":
        return "TIMEOUT"
    return trade.result


def _trade_closed_at(trade: PaperTrade) -> datetime:
    return _as_datetime(trade.closed_at or trade.opened_at)


def _bar_window_start(trade: PaperTrade, lookback_bars: int) -> datetime | None:
    """Estimate the earliest close timestamp included by a bar lookback."""
    minutes = _timeframe_minutes(trade.timeframe)
    if minutes is None:
        return None
    return _trade_closed_at(trade) - timedelta(minutes=minutes * lookback_bars)


def _timeframe_minutes(timeframe: str) -> int | None:
    """Parse compact timeframe strings like 15m, 1h, or 1d."""
    if len(timeframe) < 2:
        return None
    try:
        value = int(timeframe[:-1])
    except ValueError:
        return None
    unit = timeframe[-1].lower()
    if unit == "m":
        return value
    if unit == "h":
        return value * 60
    if unit == "d":
        return value * 60 * 24
    return None


def _as_datetime(value: datetime | str) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    parsed = datetime.fromisoformat(str(value))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _iso_datetime(value: datetime | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
