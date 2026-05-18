"""Risk guard checks for signal throttling and circuit breaking."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from config.settings import RiskGuardSettings
from paper.account import PaperAccountSnapshot, PaperTrade
from risk.circuit_breaker import CircuitBreaker, CircuitBreakerState
from signals.models import SignalType, TradeSetup


@dataclass(frozen=True)
class RiskGuardContext:
    """Current paper-trading risk context for one signal decision."""

    now: datetime
    initial_balance: float
    equity: float
    open_positions: list[PaperTrade] = field(default_factory=list)
    closed_trades: list[PaperTrade] = field(default_factory=list)
    snapshots: list[PaperAccountSnapshot] = field(default_factory=list)
    last_blocked_at: datetime | None = None
    regime_confidence_threshold: float = 0.55


@dataclass(frozen=True)
class RiskGuardEvent:
    """Logged risk guard event."""

    timestamp: datetime
    state: CircuitBreakerState
    reason: str
    symbol: str
    timeframe: str


@dataclass(frozen=True)
class RiskGuardDecision:
    """Result of applying risk guard checks."""

    allowed: bool
    state: CircuitBreakerState
    reasons: list[str]
    events: list[RiskGuardEvent]


class RiskGuard:
    """Blocks or warns on signals that breach research risk limits."""

    def __init__(
        self,
        settings: RiskGuardSettings,
        event_logger: Callable[[RiskGuardEvent], None] | None = None,
    ) -> None:
        self._settings = settings
        self._event_logger = event_logger
        self._breaker = CircuitBreaker(settings.cooldown_minutes_after_block)

    def evaluate(self, setup: TradeSetup, context: RiskGuardContext) -> RiskGuardDecision:
        """Evaluate a candidate BUY/SELL setup against configured guardrails."""
        if not self._settings.enabled or setup.signal not in {SignalType.BUY, SignalType.SELL}:
            return RiskGuardDecision(
                allowed=True,
                state=CircuitBreakerState.ACTIVE,
                reasons=[],
                events=[],
            )

        blocking = self._blocking_reasons(setup, context)
        warnings = self._warning_reasons(context)
        breaker = self._breaker.evaluate(
            blocking_reasons=blocking,
            warning_reasons=warnings,
            last_blocked_at=context.last_blocked_at,
            now=context.now,
        )
        allowed = breaker.state in {CircuitBreakerState.ACTIVE, CircuitBreakerState.WARNING}
        events = [
            RiskGuardEvent(
                timestamp=context.now,
                state=breaker.state,
                reason=reason,
                symbol=setup.symbol,
                timeframe=setup.timeframe,
            )
            for reason in breaker.reasons
        ]
        for event in events:
            if self._event_logger is not None:
                self._event_logger(event)
        return RiskGuardDecision(
            allowed=allowed,
            state=breaker.state,
            reasons=breaker.reasons,
            events=events,
        )

    def status(self, context: RiskGuardContext) -> dict[str, object]:
        """Return current guard status without a candidate trade."""
        warnings = self._warning_reasons(context)
        breaker = self._breaker.evaluate([], warnings, context.last_blocked_at, context.now)
        return {
            "enabled": self._settings.enabled,
            "state": breaker.state.value,
            "reasons": breaker.reasons,
            "daily_trade_count": _daily_trade_count(
                [*context.closed_trades, *context.open_positions],
                context.now,
            ),
            "open_positions": len(context.open_positions),
            "consecutive_losses": _consecutive_losses(context.closed_trades),
            "daily_drawdown_pct": _period_drawdown_pct(context, days=1),
            "weekly_drawdown_pct": _period_drawdown_pct(context, days=7),
            "last_blocked_at": context.last_blocked_at.isoformat()
            if context.last_blocked_at
            else None,
        }

    def _blocking_reasons(self, setup: TradeSetup, context: RiskGuardContext) -> list[str]:
        """Return blocking reasons for hard guard breaches."""
        reasons: list[str] = []
        if _daily_trade_count(
            [*context.closed_trades, *context.open_positions],
            context.now,
        ) >= self._settings.max_trades_per_day:
            reasons.append("Blocked by risk guard: max trades per day exceeded")
        if _consecutive_losses(context.closed_trades) >= self._settings.max_consecutive_losses:
            reasons.append("Blocked by risk guard: too many consecutive losses")
        if _period_drawdown_pct(context, days=1) >= _pct_limit(self._settings.max_daily_drawdown_pct):
            reasons.append("Blocked by circuit breaker: daily drawdown exceeded")
        if _period_drawdown_pct(context, days=7) >= _pct_limit(self._settings.max_weekly_drawdown_pct):
            reasons.append("Blocked by circuit breaker: weekly drawdown exceeded")
        if len(context.open_positions) >= self._settings.max_open_positions:
            reasons.append("Blocked by risk guard: max open positions reached")
        if _minutes_since_last_trade(context.closed_trades, context.now) < self._settings.min_time_between_trades_minutes:
            reasons.append("Blocked by risk guard: minimum time between trades not met")
        if self._settings.block_low_regime_confidence and (
            setup.strategy_diagnostics or {}
        ).get("transition_warning"):
            reasons.append("Blocked by risk guard: regime is unstable")
        if self._settings.block_low_regime_confidence and _setup_regime_confidence(setup) < context.regime_confidence_threshold:
            reasons.append("Blocked by risk guard: regime confidence is too low")
        if self._settings.require_calibrated_model and setup.probability_source != "calibrated":
            reasons.append("Blocked by risk guard: model probabilities are not calibrated")
        return reasons

    def _warning_reasons(self, context: RiskGuardContext) -> list[str]:
        """Return non-blocking warning reasons."""
        reasons: list[str] = []
        if _period_drawdown_pct(context, days=1) >= _pct_limit(self._settings.max_daily_drawdown_pct) * 0.8:
            reasons.append("Risk warning: daily drawdown is near limit")
        if _consecutive_losses(context.closed_trades) == self._settings.max_consecutive_losses - 1:
            reasons.append("Risk warning: one loss away from max consecutive losses")
        return reasons


def _daily_trade_count(trades: list[PaperTrade], now: datetime) -> int:
    """Count trades opened today."""
    return sum(1 for trade in trades if _as_datetime(trade.opened_at).date() == now.date())


def _consecutive_losses(trades: list[PaperTrade]) -> int:
    """Count trailing consecutive losses among closed trades."""
    ordered = sorted(
        [trade for trade in trades if trade.result is not None],
        key=lambda trade: _as_datetime(trade.closed_at or trade.opened_at),
    )
    losses = 0
    for trade in reversed(ordered):
        if str(trade.result).upper() == "LOSS":
            losses += 1
            continue
        break
    return losses


def _minutes_since_last_trade(trades: list[PaperTrade], now: datetime) -> float:
    """Return minutes since the latest opened trade, or infinity."""
    if not trades:
        return float("inf")
    latest = max(_as_datetime(trade.opened_at) for trade in trades)
    return (now - latest).total_seconds() / 60.0


def _period_drawdown_pct(context: RiskGuardContext, days: int) -> float:
    """Return drawdown over the current trailing period as a fraction."""
    since = context.now - timedelta(days=days)
    period_snapshots = [
        snapshot for snapshot in context.snapshots if _as_datetime(snapshot.timestamp) >= since
    ]
    start_equity = (
        period_snapshots[0].equity
        if period_snapshots
        else context.initial_balance
    )
    if start_equity <= 0:
        return 0.0
    return max(0.0, (start_equity - context.equity) / start_equity)


def _setup_regime_confidence(setup: TradeSetup) -> float:
    """Read regime confidence from strategy diagnostics when present."""
    diagnostics = setup.strategy_diagnostics or {}
    try:
        return float(diagnostics.get("regime_confidence", 1.0))
    except (TypeError, ValueError):
        return 1.0


def _pct_limit(value: float) -> float:
    """Normalize percent config that may be expressed as 5 or 0.05."""
    return value / 100.0 if value > 1.0 else value


def _as_datetime(value: object) -> datetime:
    """Parse a timezone-aware datetime."""
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    parsed = datetime.fromisoformat(str(value))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
