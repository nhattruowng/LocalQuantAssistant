"""Telegram notification delivery."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
import json
import logging
from typing import Callable
from urllib import request
from urllib.error import URLError

from config.settings import NotificationSettings
from signals.models import SignalType, TradeSetup


HttpPoster = Callable[[str, bytes, float], None]


@dataclass
class TelegramNotificationService:
    """Sends Telegram alerts for strong BUY/SELL recommendations."""

    settings: NotificationSettings
    logger: logging.Logger | None = None
    http_post: HttpPoster | None = None
    _last_sent_at: dict[str, datetime] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self._logger = self.logger or logging.getLogger("localquant.notification")
        self._http_post = self.http_post or _post_json

    def send_trade_setup(self, setup: TradeSetup) -> bool:
        """Send a Telegram alert when setup passes filters and cooldown."""
        if not self._is_eligible(setup):
            return False

        key = _cooldown_key(setup)
        if self._is_in_cooldown(key):
            self._logger.info("Telegram alert skipped by cooldown: key=%s", key)
            return False

        if not self.settings.telegram_bot_token or not self.settings.telegram_chat_id:
            self._logger.warning("Telegram alert skipped because token/chat_id is not configured.")
            return False

        url = f"https://api.telegram.org/bot{self.settings.telegram_bot_token}/sendMessage"
        payload = {
            "chat_id": self.settings.telegram_chat_id,
            "text": _format_message(setup),
            "disable_web_page_preview": True,
        }
        try:
            self._http_post(
                url,
                json.dumps(payload).encode("utf-8"),
                self.settings.request_timeout_seconds,
            )
        except Exception as error:
            self._logger.warning("Telegram alert failed: %s", error)
            return False

        self._last_sent_at[key] = datetime.now(UTC)
        self._logger.info(
            "Telegram alert sent: symbol=%s timeframe=%s signal=%s confidence=%.4f",
            setup.symbol,
            setup.timeframe,
            setup.signal.value,
            setup.confidence,
        )
        return True

    def _is_eligible(self, setup: TradeSetup) -> bool:
        """Return True when a setup should be sent to Telegram."""
        if not self.settings.enabled:
            return False
        if setup.signal not in {SignalType.BUY, SignalType.SELL}:
            return False
        if setup.confidence < self.settings.min_confidence:
            return False
        if setup.risk_reward is None or setup.risk_reward < self.settings.min_risk_reward:
            return False
        return True

    def _is_in_cooldown(self, key: str) -> bool:
        """Return True when the symbol/timeframe alert is cooling down."""
        if self.settings.cooldown_seconds <= 0:
            return False
        last_sent_at = self._last_sent_at.get(key)
        if last_sent_at is None:
            return False
        elapsed = (datetime.now(UTC) - last_sent_at).total_seconds()
        return elapsed < self.settings.cooldown_seconds


def _post_json(url: str, payload: bytes, timeout_seconds: float) -> None:
    """POST JSON to Telegram using the Python standard library."""
    http_request = request.Request(
        url=url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(http_request, timeout=timeout_seconds) as response:
            if response.status >= 400:
                raise RuntimeError(f"Telegram API returned HTTP {response.status}.")
    except URLError as error:
        raise RuntimeError(str(error)) from error


def _format_message(setup: TradeSetup) -> str:
    """Create a compact plain-text Telegram message."""
    reasons = "\n".join(f"- {reason}" for reason in setup.reasons[:6]) or "- No reasons provided."
    return (
        "LocalQuant Assistant Alert\n"
        f"Symbol: {setup.symbol}\n"
        f"Timeframe: {setup.timeframe}\n"
        f"Signal: {setup.signal.value}\n"
        f"Confidence: {setup.confidence:.2f}\n"
        f"Strategy: {setup.strategy.value}\n"
        f"Entry: {_fmt(setup.entry)}\n"
        f"Stop Loss: {_fmt(setup.stop_loss)}\n"
        f"Take Profit 1: {_fmt(setup.take_profit_1)}\n"
        f"Take Profit 2: {_fmt(setup.take_profit_2)}\n"
        f"Risk/Reward: {_fmt(setup.risk_reward)}\n"
        "Reasons:\n"
        f"{reasons}\n\n"
        "Research only. This is not financial advice and no real trade was executed."
    )


def _cooldown_key(setup: TradeSetup) -> str:
    """Return cooldown key for a setup."""
    return f"{setup.symbol}:{setup.timeframe}"


def _fmt(value: object) -> str:
    """Format optional numeric values for alerts."""
    if value is None:
        return "-"
    try:
        return f"{float(value):.4f}"
    except (TypeError, ValueError):
        return str(value)
