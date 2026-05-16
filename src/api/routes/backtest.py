"""Backtest API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from api.dependencies import get_service
from api.schemas.requests import RunBacktestRequest
from api.services.localquant_service import LocalQuantApiService


router = APIRouter(prefix="/api/backtest", tags=["backtest"])


@router.post("/run")
def run_backtest(
    request: RunBacktestRequest,
    service: LocalQuantApiService = Depends(get_service),
) -> dict[str, object]:
    """Run rule-only and ML-enhanced backtests when possible."""
    return service.run_backtest(
        symbol=request.symbol,
        timeframe=request.timeframe,
        initial_balance=request.initial_balance,
        risk_percent=request.risk_percent,
    )


@router.get("/latest")
def latest_backtest(
    symbol: str = Query(...),
    timeframe: str = Query(...),
    service: LocalQuantApiService = Depends(get_service),
) -> dict[str, object]:
    """Return latest persisted backtest summary."""
    report = service.latest_backtest(symbol=symbol, timeframe=timeframe)
    if report is None:
        raise HTTPException(status_code=404, detail="No backtest report found.")
    return report
