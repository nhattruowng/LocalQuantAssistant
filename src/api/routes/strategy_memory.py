"""Strategy memory API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from api.dependencies import get_service
from api.services.localquant_service import LocalQuantApiService


router = APIRouter(prefix="/api/strategy-memory", tags=["strategy-memory"])


@router.get("")
def strategy_memory(
    service: LocalQuantApiService = Depends(get_service),
) -> dict[str, object]:
    """Return all strategy memory snapshots."""
    return service.strategy_memory()


@router.get("/{symbol_path:path}")
def strategy_memory_for_timeframe(
    symbol_path: str,
    service: LocalQuantApiService = Depends(get_service),
) -> dict[str, object]:
    """Return memory snapshots for a symbol/timeframe."""
    if "/" not in symbol_path:
        return service.strategy_memory(symbol=symbol_path, timeframe=None)
    symbol, timeframe = symbol_path.rsplit("/", maxsplit=1)
    return service.strategy_memory(symbol=symbol, timeframe=timeframe)
