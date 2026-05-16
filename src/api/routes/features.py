"""Feature engineering API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from api.dependencies import get_service
from api.schemas.requests import SymbolTimeframeRequest
from api.schemas.responses import FeatureBuildResponse
from api.services.localquant_service import LocalQuantApiService


router = APIRouter(prefix="/api/features", tags=["features"])


@router.post("/build", response_model=FeatureBuildResponse)
def build_features(
    request: SymbolTimeframeRequest,
    service: LocalQuantApiService = Depends(get_service),
) -> dict[str, object]:
    """Build features for a symbol/timeframe."""
    return service.build_features(symbol=request.symbol, timeframe=request.timeframe)
