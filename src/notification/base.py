"""Notification service contracts."""

from __future__ import annotations

from typing import Protocol

from signals.models import TradeSetup


class NotificationService(Protocol):
    """Sends external alerts for eligible trade setups."""

    def send_trade_setup(self, setup: TradeSetup) -> bool:
        """Send a setup alert and return True when it was delivered."""
