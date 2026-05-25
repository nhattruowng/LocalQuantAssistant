"""Meta-labeling for strategy signal candidates."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

import pandas as pd

from ml.labeling.triple_barrier import (
    BarrierLabel,
    TripleBarrierConfig,
    TripleBarrierLabel,
    TripleBarrierLabeler,
)


@dataclass(frozen=True)
class MetaLabel:
    """Meta-label for whether a candidate trade is worth taking."""

    candidate_id: str | int | None
    trade_worth_taking: bool
    label: BarrierLabel
    r_multiple: float
    expected_r_multiple: float | None
    lookahead_bars: int
    label_start_index: int
    label_end_index: int
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "trade_worth_taking": self.trade_worth_taking,
            "label": self.label.value,
            "r_multiple": self.r_multiple,
            "expected_r_multiple": self.expected_r_multiple,
            "lookahead_bars": self.lookahead_bars,
            "label_start_index": self.label_start_index,
            "label_end_index": self.label_end_index,
            "metadata": dict(self.metadata),
        }


class MetaLabeler:
    """Create binary meta-labels from strategy candidate signals."""

    def __init__(
        self,
        triple_barrier_labeler: TripleBarrierLabeler | None = None,
        min_r_multiple: float = 0.0,
    ) -> None:
        self._labeler = triple_barrier_labeler or TripleBarrierLabeler(
            TripleBarrierConfig(lookahead_bars=10)
        )
        self._min_r_multiple = float(min_r_multiple)

    def label_candidates(
        self,
        candles: pd.DataFrame,
        candidates: pd.DataFrame | Iterable[Mapping[str, Any]],
    ) -> list[MetaLabel]:
        """Return true/false labels for strategy signals without mutating inputs."""
        rows = _candidate_rows(candidates)
        labels: list[MetaLabel] = []
        for row in rows:
            triple_label = self._labeler.label_one(
                candles=candles,
                entry_index=int(_row_get(row, "entry_index", _row_get(row, "index", 0))),
                direction=str(_row_get(row, "direction", _row_get(row, "signal", "BUY"))),
                entry_price=_optional_float(_row_get(row, "entry_price")),
                take_profit=_optional_float(_row_get(row, "take_profit")),
                stop_loss=_optional_float(_row_get(row, "stop_loss")),
            )
            expected_r_multiple = _optional_float(_row_get(row, "expected_r_multiple"))
            labels.append(
                self._build_meta_label(
                    candidate_id=_row_get(row, "candidate_id", _row_get(row, "id")),
                    triple_label=triple_label,
                    expected_r_multiple=expected_r_multiple,
                )
            )
        return labels

    def _build_meta_label(
        self,
        candidate_id: str | int | None,
        triple_label: TripleBarrierLabel,
        expected_r_multiple: float | None,
    ) -> MetaLabel:
        worth_taking = (
            triple_label.label is BarrierLabel.WIN
            and triple_label.r_multiple >= self._min_r_multiple
        )
        return MetaLabel(
            candidate_id=candidate_id,
            trade_worth_taking=worth_taking,
            label=triple_label.label,
            r_multiple=triple_label.r_multiple,
            expected_r_multiple=(
                expected_r_multiple
                if expected_r_multiple is not None
                else triple_label.r_multiple
            ),
            lookahead_bars=triple_label.lookahead_bars,
            label_start_index=triple_label.label_start_index,
            label_end_index=triple_label.label_end_index,
            metadata={
                **triple_label.metadata,
                "lookahead_bars": triple_label.lookahead_bars,
                "primary_label": triple_label.label.value,
                "barrier_touched": triple_label.barrier_touched,
            },
        )


def _candidate_rows(candidates: pd.DataFrame | Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    if isinstance(candidates, pd.DataFrame):
        return [dict(row) for row in candidates.to_dict(orient="records")]
    return [dict(item) for item in candidates]


def _row_get(row: Mapping[str, Any], key: str, default: Any = None) -> Any:
    return row.get(key, default)


def _optional_float(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)
