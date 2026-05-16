"""Pydantic request schemas for the REST API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SymbolTimeframeRequest(BaseModel):
    """Common symbol/timeframe request."""

    symbol: str = Field(..., examples=["BTC/USDT"])
    timeframe: str = Field(..., examples=["15m"])


class DataUpdateRequest(SymbolTimeframeRequest):
    """Request to update market data."""

    limit: int | None = Field(default=None, ge=1, le=5000)


class GenerateSignalRequest(SymbolTimeframeRequest):
    """Request to generate a signal setup."""

    account_balance: float = Field(..., gt=0)
    risk_percent: float = Field(..., ge=0, description="Risk percent as UI percent, e.g. 1 for 1%.")


class RunBacktestRequest(SymbolTimeframeRequest):
    """Request to run a backtest."""

    initial_balance: float = Field(..., gt=0)
    risk_percent: float = Field(..., ge=0, description="Risk percent as UI percent, e.g. 1 for 1%.")
