"""Risk manager for setup recommendations."""

from __future__ import annotations

import math
from typing import Mapping

from config.settings import RiskSettings
from signals.models import RiskPlan, SignalType


class RiskManager:
    """Builds entry, exits, risk/reward, and position sizing."""

    def __init__(self, settings: RiskSettings) -> None:
        self._settings = settings

    def build_plan(
        self,
        signal: SignalType,
        features: Mapping[str, float],
    ) -> RiskPlan | None:
        """Return a risk plan for BUY/SELL, or None for WAIT."""
        if signal is SignalType.WAIT:
            return None

        entry = float(features["close"])
        atr = float(features["atr_14"])
        if not math.isfinite(entry) or entry <= 0:
            raise ValueError("Risk plan requires positive close price.")
        if not math.isfinite(atr) or atr <= 0:
            raise ValueError("Risk plan requires positive atr_14.")

        stop_distance = atr * self._settings.stop_loss_atr_multiplier
        take_profit_1_distance = atr * self._settings.take_profit_1_atr_multiplier
        take_profit_2_distance = atr * self._settings.take_profit_2_atr_multiplier
        if signal is SignalType.BUY:
            stop_loss = entry - stop_distance
            take_profit_1 = entry + take_profit_1_distance
            take_profit_2 = entry + take_profit_2_distance
        else:
            stop_loss = entry + stop_distance
            take_profit_1 = entry - take_profit_1_distance
            take_profit_2 = entry - take_profit_2_distance

        per_unit_risk = abs(entry - stop_loss)
        risk_pct = min(
            self._settings.risk_per_trade_pct,
            _pct_limit(self._settings.max_risk_per_trade_pct),
        )
        risk_amount = self._settings.account_balance * risk_pct
        position_size = risk_amount / per_unit_risk
        risk_reward = abs(take_profit_2 - entry) / per_unit_risk

        notes: list[str] = []
        if stop_loss <= 0 or take_profit_1 <= 0 or take_profit_2 <= 0:
            notes.append("One or more exit levels are non-positive; verify symbol pricing.")
        return RiskPlan(
            entry=entry,
            stop_loss=stop_loss,
            take_profit_1=take_profit_1,
            take_profit_2=take_profit_2,
            risk_reward=risk_reward,
            position_size=position_size,
            risk_notes=notes,
            base_position_size=position_size,
            final_position_size=position_size,
            size_multiplier=1.0,
        )


def _pct_limit(value: float) -> float:
    """Normalize percent config values that may be expressed as 1 or 0.01."""
    return value / 100.0 if value > 0.25 else value
