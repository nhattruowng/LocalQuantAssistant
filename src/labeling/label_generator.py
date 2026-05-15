"""TP/SL first-touch label generation."""

from __future__ import annotations

import pandas as pd

from config.settings import LabelingSettings
from domain.enums import TradingAction


class LabelGenerator:
    """Generates BUY/SELL/WAIT labels using first-touch TP/SL logic."""

    def __init__(self, settings: LabelingSettings) -> None:
        self._settings = settings

    def generate(self, features: pd.DataFrame) -> pd.DataFrame:
        """Return a copy of features with a label column added."""
        self._validate_input(features)
        labeled = features.copy(deep=True)
        labels = [self._label_row(labeled, index) for index in range(len(labeled))]
        labeled["label"] = labels
        labeled["label_lookahead_complete"] = [
            index + self._settings.lookahead_bars < len(labeled)
            for index in range(len(labeled))
        ]
        return labeled

    def _validate_input(self, features: pd.DataFrame) -> None:
        """Validate required label inputs."""
        required = ["close", "high", "low", "atr_14"]
        missing = [column for column in required if column not in features]
        if missing:
            raise ValueError(f"Feature DataFrame is missing label columns: {missing}.")
        if features.empty:
            raise ValueError("Feature DataFrame must not be empty.")

    def _label_row(self, features: pd.DataFrame, index: int) -> str:
        """Create a first-touch label for one candle."""
        entry = features["close"].iat[index]
        atr = features["atr_14"].iat[index]
        if pd.isna(entry) or pd.isna(atr) or atr <= 0:
            return TradingAction.WAIT.value

        sl_buy = entry - atr * self._settings.stop_loss_atr_multiplier
        tp_buy = entry + atr * self._settings.take_profit_atr_multiplier
        sl_sell = entry + atr * self._settings.stop_loss_atr_multiplier
        tp_sell = entry - atr * self._settings.take_profit_atr_multiplier
        start = index + 1
        stop = min(index + self._settings.lookahead_bars + 1, len(features))
        buy_active = True
        sell_active = True

        for future_index in range(start, stop):
            future_high = features["high"].iat[future_index]
            future_low = features["low"].iat[future_index]
            buy_tp_hit = future_high >= tp_buy
            buy_sl_hit = future_low <= sl_buy
            sell_tp_hit = future_low <= tp_sell
            sell_sl_hit = future_high >= sl_sell
            buy_signal = buy_active and buy_tp_hit and not buy_sl_hit
            sell_signal = sell_active and sell_tp_hit and not sell_sl_hit

            if buy_signal and sell_signal:
                return TradingAction.WAIT.value
            if buy_signal:
                return TradingAction.BUY.value
            if sell_signal:
                return TradingAction.SELL.value

            if buy_active and (buy_sl_hit or buy_tp_hit):
                buy_active = False
            if sell_active and (sell_sl_hit or sell_tp_hit):
                sell_active = False

        return TradingAction.WAIT.value
