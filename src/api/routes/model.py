"""Model API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from api.dependencies import get_service
from api.schemas.requests import SymbolTimeframeRequest
from api.services.localquant_service import LocalQuantApiService


router = APIRouter(prefix="/api/model", tags=["model"])


@router.get("/info")
def model_info(
    symbol: str | None = Query(default=None),
    timeframe: str | None = Query(default=None),
    service: LocalQuantApiService = Depends(get_service),
) -> dict[str, object]:
    """Return latest model metadata."""
    metadata = service.model_info(symbol=symbol, timeframe=timeframe)
    if metadata is None:
        raise HTTPException(status_code=404, detail="No model found.")
    return metadata


@router.post("/train")
def train_model(
    request: SymbolTimeframeRequest,
    service: LocalQuantApiService = Depends(get_service),
) -> dict[str, object]:
    """Train a model for a symbol/timeframe."""
    return service.train_model(symbol=request.symbol, timeframe=request.timeframe)
