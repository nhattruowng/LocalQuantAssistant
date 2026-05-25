"""Tests for ML triple-barrier and meta-labeling pipeline."""

from __future__ import annotations

import pandas as pd

from ml.labeling.meta_labeling import MetaLabeler
from ml.labeling.triple_barrier import (
    BarrierLabel,
    TripleBarrierConfig,
    TripleBarrierLabeler,
)


def test_triple_barrier_tp_first_touch_marks_win() -> None:
    labeler = _labeler()
    candles = _candles()
    candles.loc[1, "high"] = 111.0

    label = labeler.label_one(
        candles,
        entry_index=0,
        direction="BUY",
        entry_price=100.0,
        take_profit=110.0,
        stop_loss=95.0,
    )

    assert label.label is BarrierLabel.WIN
    assert label.barrier_touched == "take_profit"
    assert label.r_multiple == 2.0
    assert label.metadata["lookahead_bars"] == 3
    assert label.metadata["purge_until_index"] == 3


def test_triple_barrier_sl_first_touch_marks_loss() -> None:
    labeler = _labeler()
    candles = _candles()
    candles.loc[1, "low"] = 94.0

    label = labeler.label_one(
        candles,
        entry_index=0,
        direction="BUY",
        entry_price=100.0,
        take_profit=110.0,
        stop_loss=95.0,
    )

    assert label.label is BarrierLabel.LOSS
    assert label.barrier_touched == "stop_loss"
    assert label.r_multiple == -1.0


def test_triple_barrier_time_expiry_marks_timeout_without_using_future_beyond_window() -> None:
    labeler = _labeler()
    candles = _candles()
    candles.loc[3, "close"] = 102.0
    candles.loc[4, "high"] = 120.0

    label = labeler.label_one(
        candles,
        entry_index=0,
        direction="BUY",
        entry_price=100.0,
        take_profit=110.0,
        stop_loss=95.0,
    )

    assert label.label is BarrierLabel.TIMEOUT
    assert label.barrier_touched == "time_expiry"
    assert label.exit_index == 3
    assert label.r_multiple == 0.4


def test_triple_barrier_sell_r_multiple_is_directional() -> None:
    labeler = _labeler()
    candles = _candles()
    candles.loc[1, "low"] = 90.0

    label = labeler.label_one(
        candles,
        entry_index=0,
        direction="SELL",
        entry_price=100.0,
        take_profit=90.0,
        stop_loss=105.0,
    )

    assert label.label is BarrierLabel.WIN
    assert label.r_multiple == 2.0


def test_meta_labeler_creates_trade_worth_taking_labels() -> None:
    candles = _candles()
    candles.loc[1, "high"] = 111.0
    candles.loc[2, "low"] = 94.0
    labeler = MetaLabeler(_labeler(), min_r_multiple=1.0)
    candidates = [
        {
            "candidate_id": "win",
            "entry_index": 0,
            "direction": "BUY",
            "entry_price": 100.0,
            "take_profit": 110.0,
            "stop_loss": 95.0,
            "expected_r_multiple": 1.8,
        },
        {
            "candidate_id": "loss",
            "entry_index": 1,
            "direction": "BUY",
            "entry_price": 100.0,
            "take_profit": 110.0,
            "stop_loss": 95.0,
        },
    ]

    labels = labeler.label_candidates(candles, candidates)

    assert labels[0].candidate_id == "win"
    assert labels[0].trade_worth_taking is True
    assert labels[0].expected_r_multiple == 1.8
    assert labels[0].metadata["lookahead_bars"] == 3
    assert labels[1].candidate_id == "loss"
    assert labels[1].trade_worth_taking is False
    assert labels[1].label is BarrierLabel.LOSS


def test_meta_labeler_accepts_dataframe_candidates() -> None:
    candles = _candles()
    candles.loc[1, "high"] = 111.0
    candidates = pd.DataFrame(
        [
            {
                "id": 1,
                "entry_index": 0,
                "signal": "BUY",
                "entry_price": 100.0,
                "take_profit": 110.0,
                "stop_loss": 95.0,
            }
        ]
    )

    labels = MetaLabeler(_labeler()).label_candidates(candles, candidates)

    assert labels[0].candidate_id == 1
    assert labels[0].trade_worth_taking is True


def _labeler() -> TripleBarrierLabeler:
    return TripleBarrierLabeler(
        TripleBarrierConfig(
            lookahead_bars=3,
            take_profit_pct=0.10,
            stop_loss_pct=0.05,
        )
    )


def _candles() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-01-01", periods=5, freq="h", tz="UTC"),
            "open": [100.0] * 5,
            "high": [101.0] * 5,
            "low": [99.0] * 5,
            "close": [100.0] * 5,
            "volume": [1_000.0] * 5,
            "atr_14": [2.0] * 5,
        }
    )
