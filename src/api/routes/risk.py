"""Risk status API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from api.dependencies import get_service
from api.services.localquant_service import LocalQuantApiService


router = APIRouter(prefix="/api/risk", tags=["risk"])


@router.get("/status")
def risk_status(
    symbol: str | None = Query(default=None),
    timeframe: str | None = Query(default=None),
    service: LocalQuantApiService = Depends(get_service),
) -> dict[str, object]:
    """Return risk guard and circuit breaker status."""
    return service.risk_status(symbol=symbol, timeframe=timeframe)
