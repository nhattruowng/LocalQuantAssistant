"""Paper trading analytics API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from api.dependencies import get_service
from api.services.localquant_service import LocalQuantApiService


router = APIRouter(prefix="/api/paper", tags=["paper"])


@router.get("/analytics")
def paper_analytics(
    symbol: str = Query(...),
    timeframe: str = Query(...),
    service: LocalQuantApiService = Depends(get_service),
) -> dict[str, object]:
    """Return paper trading risk analytics."""
    return service.paper_analytics(symbol=symbol, timeframe=timeframe)


@router.get("/drawdown")
def paper_drawdown(
    symbol: str = Query(...),
    timeframe: str = Query(...),
    service: LocalQuantApiService = Depends(get_service),
) -> dict[str, object]:
    """Return paper drawdown curve."""
    return service.paper_drawdown(symbol=symbol, timeframe=timeframe)


@router.get("/regime-performance")
def paper_regime_performance(
    symbol: str = Query(...),
    timeframe: str = Query(...),
    service: LocalQuantApiService = Depends(get_service),
) -> dict[str, object]:
    """Return realized paper PnL by regime and strategy."""
    return service.paper_regime_performance(symbol=symbol, timeframe=timeframe)
