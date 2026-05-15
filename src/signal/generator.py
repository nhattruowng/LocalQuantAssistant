"""Signal generation primitives."""

from __future__ import annotations

from domain.enums import TradingAction


def no_signal() -> TradingAction:
    """Return WAIT when no signal generator is configured."""
    return TradingAction.WAIT
