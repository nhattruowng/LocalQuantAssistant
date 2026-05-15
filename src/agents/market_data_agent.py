"""Market data validation agent."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import math

from agents.base import AgentError, BaseAgent
from agents.context import AgentContext
from domain.entities import OHLCVBar


class MarketDataAgent(BaseAgent):
    """Ensures OHLCV data is present and usable."""

    name = "MarketDataAgent"

    def run(self, context: AgentContext) -> AgentContext:
        """Validate OHLCV data and collect local fallback data if needed."""
        self.log_start(context)
        min_bars = self.settings.data.min_bars

        if context.ohlcv:
            self._validate_ohlcv(context.ohlcv, len(context.ohlcv))

        if len(context.ohlcv) < min_bars:
            context.ohlcv = self._collect_missing_data(context.symbol, min_bars)
            context.add_reason("Market data was collected from the local fallback collector.")

        self._validate_ohlcv(context.ohlcv, min_bars)
        context.add_reason(f"Validated {len(context.ohlcv)} OHLCV bars.")
        self.log_finish(context)
        return context

    def _collect_missing_data(self, symbol: str, bars: int) -> list[OHLCVBar]:
        """Collect deterministic local sample data until real collectors are added."""
        now = datetime.now(UTC).replace(second=0, microsecond=0)
        base_price = 100.0 + (sum(ord(char) for char in symbol) % 50)
        collected: list[OHLCVBar] = []

        for index in range(bars):
            close = base_price + index * 0.4
            open_price = close - 0.2
            collected.append(
                OHLCVBar(
                    timestamp=now - timedelta(minutes=bars - index),
                    open=open_price,
                    high=close + 0.6,
                    low=open_price - 0.6,
                    close=close,
                    volume=1_000.0 + index * 5.0,
                )
            )
        return collected

    def _validate_ohlcv(self, bars: list[OHLCVBar], min_bars: int) -> None:
        """Validate basic OHLCV integrity."""
        if len(bars) < min_bars:
            raise AgentError(f"Not enough OHLCV bars: expected at least {min_bars}.")

        previous_timestamp: datetime | None = None
        for bar in bars:
            values = [bar.open, bar.high, bar.low, bar.close, bar.volume]
            if any(not math.isfinite(value) for value in values):
                raise AgentError("OHLCV data contains non-finite values.")
            if min(bar.open, bar.close) < bar.low or max(bar.open, bar.close) > bar.high:
                raise AgentError("OHLCV high/low values are inconsistent.")
            if bar.low <= 0 or bar.volume < 0:
                raise AgentError("OHLCV data contains invalid price or volume.")
            if previous_timestamp and bar.timestamp <= previous_timestamp:
                raise AgentError("OHLCV timestamps must be strictly increasing.")
            previous_timestamp = bar.timestamp
