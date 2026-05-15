"""Feature builder contracts."""

from __future__ import annotations

from typing import Mapping

from domain.entities import MarketSnapshot


def build_basic_features(snapshot: MarketSnapshot) -> Mapping[str, float]:
    """Build a small baseline feature set from a market snapshot."""
    return {"close_price": snapshot.close_price}
