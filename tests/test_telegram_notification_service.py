"""Tests for Telegram notification filters."""

from __future__ import annotations

from datetime import UTC, datetime

from config.settings import NotificationSettings
from notification.telegram_service import TelegramNotificationService
from signal.models import SignalType, StrategyType, TradeSetup


def test_telegram_service_sends_strong_buy_once_then_cooldown():
    sent_payloads: list[bytes] = []
    service = TelegramNotificationService(
        settings=_settings(enabled=True),
        http_post=lambda url, payload, timeout: sent_payloads.append(payload),
    )

    first_sent = service.send_trade_setup(_setup(signal=SignalType.BUY))
    second_sent = service.send_trade_setup(_setup(signal=SignalType.BUY))

    assert first_sent is True
    assert second_sent is False
    assert len(sent_payloads) == 1
    assert b"BTC/USDT" in sent_payloads[0]
    assert b"Risk/Reward" in sent_payloads[0]


def test_telegram_service_does_not_send_wait():
    sent_payloads: list[bytes] = []
    service = TelegramNotificationService(
        settings=_settings(enabled=True),
        http_post=lambda url, payload, timeout: sent_payloads.append(payload),
    )

    sent = service.send_trade_setup(_setup(signal=SignalType.WAIT))

    assert sent is False
    assert sent_payloads == []


def test_telegram_service_does_not_send_low_confidence():
    sent_payloads: list[bytes] = []
    service = TelegramNotificationService(
        settings=_settings(enabled=True),
        http_post=lambda url, payload, timeout: sent_payloads.append(payload),
    )

    sent = service.send_trade_setup(_setup(signal=SignalType.SELL, confidence=0.50))

    assert sent is False
    assert sent_payloads == []


def test_telegram_service_does_not_send_low_risk_reward():
    sent_payloads: list[bytes] = []
    service = TelegramNotificationService(
        settings=_settings(enabled=True),
        http_post=lambda url, payload, timeout: sent_payloads.append(payload),
    )

    sent = service.send_trade_setup(_setup(signal=SignalType.BUY, risk_reward=1.5))

    assert sent is False
    assert sent_payloads == []


def _settings(enabled: bool) -> NotificationSettings:
    """Return notification settings with fake Telegram credentials."""
    return NotificationSettings(
        enabled=enabled,
        telegram_bot_token="token",
        telegram_chat_id="chat",
        min_confidence=0.70,
        min_risk_reward=2.0,
        cooldown_seconds=900,
        request_timeout_seconds=1.0,
    )


def _setup(
    signal: SignalType,
    confidence: float = 0.75,
    risk_reward: float = 2.0,
) -> TradeSetup:
    """Build a setup for notification tests."""
    return TradeSetup(
        symbol="BTC/USDT",
        timeframe="15m",
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        market_regime="UPTREND",
        signal=signal,
        strategy=StrategyType.TREND_FOLLOWING,
        confidence=confidence,
        entry=100.0,
        stop_loss=95.0,
        take_profit_1=110.0,
        take_profit_2=115.0,
        risk_reward=risk_reward,
        position_size=1.0,
        reasons=["Test reason"],
        risk_notes=[],
    )
