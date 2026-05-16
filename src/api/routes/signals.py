"""Signal API routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from api.dependencies import get_service
from api.schemas.requests import GenerateSignalRequest
from api.services.localquant_service import LocalQuantApiService


router = APIRouter(prefix="/api/signals", tags=["signals"])


@router.post("/generate")
def generate_signal(
    request: GenerateSignalRequest,
    service: LocalQuantApiService = Depends(get_service),
) -> dict[str, object]:
    """Generate a BUY/SELL/WAIT setup."""
    return service.generate_signal(
        symbol=request.symbol,
        timeframe=request.timeframe,
        account_balance=request.account_balance,
        risk_percent=request.risk_percent,
    )


@router.get("/history")
def signal_history(
    symbol: str | None = Query(default=None),
    timeframe: str | None = Query(default=None),
    service: LocalQuantApiService = Depends(get_service),
) -> list[dict[str, Any]]:
    """Return local signal history."""
    return service.signal_history(symbol=symbol, timeframe=timeframe)
