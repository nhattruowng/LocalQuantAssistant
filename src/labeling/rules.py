"""Label generation primitives."""

from __future__ import annotations

from domain.enums import TradingAction


def neutral_label() -> TradingAction:
    """Return the default label before strategy-specific rules exist."""
    return TradingAction.WAIT
