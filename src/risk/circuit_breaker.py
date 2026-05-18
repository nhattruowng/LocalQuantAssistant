"""Circuit breaker state transitions for risk guard decisions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum


class CircuitBreakerState(str, Enum):
    """Risk circuit breaker states."""

    ACTIVE = "ACTIVE"
    WARNING = "WARNING"
    BLOCKED = "BLOCKED"
    COOLDOWN = "COOLDOWN"


@dataclass(frozen=True)
class CircuitBreakerDecision:
    """Circuit breaker state plus human-readable reasons."""

    state: CircuitBreakerState
    reasons: list[str]


class CircuitBreaker:
    """Derives a circuit breaker state from blocking and warning conditions."""

    def __init__(self, cooldown_minutes_after_block: int) -> None:
        self._cooldown = timedelta(minutes=cooldown_minutes_after_block)

    def evaluate(
        self,
        blocking_reasons: list[str],
        warning_reasons: list[str],
        last_blocked_at: datetime | None,
        now: datetime,
    ) -> CircuitBreakerDecision:
        """Return the current circuit breaker state."""
        if blocking_reasons:
            return CircuitBreakerDecision(
                state=CircuitBreakerState.BLOCKED,
                reasons=blocking_reasons,
            )
        if last_blocked_at is not None and now < last_blocked_at + self._cooldown:
            return CircuitBreakerDecision(
                state=CircuitBreakerState.COOLDOWN,
                reasons=["Blocked by circuit breaker: cooldown after previous block is active"],
            )
        if warning_reasons:
            return CircuitBreakerDecision(
                state=CircuitBreakerState.WARNING,
                reasons=warning_reasons,
            )
        return CircuitBreakerDecision(state=CircuitBreakerState.ACTIVE, reasons=[])
