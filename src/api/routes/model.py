"""Model API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from api.dependencies import get_service
from api.schemas.requests import ModelLifecycleRequest, SymbolTimeframeRequest
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


@router.get("/calibration")
def model_calibration(
    symbol: str | None = Query(default=None),
    timeframe: str | None = Query(default=None),
    service: LocalQuantApiService = Depends(get_service),
) -> dict[str, object]:
    """Return latest model calibration diagnostics."""
    metadata = service.model_calibration(symbol=symbol, timeframe=timeframe)
    if metadata is None:
        raise HTTPException(status_code=404, detail="No model found.")
    return metadata


@router.get("/registry")
def model_registry(
    service: LocalQuantApiService = Depends(get_service),
) -> dict[str, object]:
    """Return all registered model versions."""
    return service.model_registry()


@router.get("/registry/{symbol}/{timeframe}")
def model_registry_for_market(
    symbol: str,
    timeframe: str,
    service: LocalQuantApiService = Depends(get_service),
) -> dict[str, object]:
    """Return registered model versions for one symbol/timeframe."""
    normalized_symbol = symbol.replace("_", "/") if "/" not in symbol else symbol
    return service.model_registry(symbol=normalized_symbol, timeframe=timeframe)


@router.post("/promote")
def promote_model(
    request: ModelLifecycleRequest,
    service: LocalQuantApiService = Depends(get_service),
) -> dict[str, object]:
    """Promote a model version to champion."""
    try:
        return service.promote_model(request.model_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/archive")
def archive_model(
    request: ModelLifecycleRequest,
    service: LocalQuantApiService = Depends(get_service),
) -> dict[str, object]:
    """Archive a model version."""
    try:
        return service.archive_model(request.model_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/train")
def train_model(
    request: SymbolTimeframeRequest,
    service: LocalQuantApiService = Depends(get_service),
) -> dict[str, object]:
    """Train a model for a symbol/timeframe."""
    return service.train_model(symbol=request.symbol, timeframe=request.timeframe)
