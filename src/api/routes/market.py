"""Market data API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from api.dependencies import get_service
from api.schemas.requests import DataUpdateRequest
from api.schemas.responses import CandleResponse, DataUpdateResponse, ListResponse
from api.services.localquant_service import LocalQuantApiService


router = APIRouter(prefix="/api", tags=["market"])


@router.get("/symbols", response_model=ListResponse)
def list_symbols(service: LocalQuantApiService = Depends(get_service)) -> ListResponse:
    """Return configured tradable symbols."""
    return ListResponse(items=service.symbols())


@router.get("/timeframes", response_model=ListResponse)
def list_timeframes(service: LocalQuantApiService = Depends(get_service)) -> ListResponse:
    """Return configured timeframes."""
    return ListResponse(items=service.timeframes())


@router.get("/candles", response_model=list[CandleResponse])
def list_candles(
    symbol: str = Query(...),
    timeframe: str = Query(...),
    limit: int = Query(500, ge=1, le=5000),
    service: LocalQuantApiService = Depends(get_service),
) -> list[dict[str, object]]:
    """Return latest OHLCV candles."""
    return service.candles(symbol=symbol, timeframe=timeframe, limit=limit)


@router.post("/data/update", response_model=DataUpdateResponse)
def update_data(
    request: DataUpdateRequest,
    service: LocalQuantApiService = Depends(get_service),
) -> DataUpdateResponse:
    """Collect and persist latest OHLCV data."""
    inserted = service.update_data(
        symbol=request.symbol,
        timeframe=request.timeframe,
        limit=request.limit,
    )
    return DataUpdateResponse(inserted=inserted)
