"""FastAPI app for LocalQuant Assistant."""

from __future__ import annotations

from pathlib import Path
import os
import sys


SRC_DIR = Path(__file__).resolve().parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.routes import backtest, features, market, model, paper, risk, signals
from api.schemas.responses import HealthResponse


def _cors_origins() -> list[str]:
    """Read comma-separated CORS origins for React frontends."""
    raw = os.getenv(
        "LOCALQUANT_CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173",
    )
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def _error_response(status_code: int, code: str, message: str) -> JSONResponse:
    """Build a standard error response envelope."""
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message}},
    )


app = FastAPI(
    title="LocalQuant Assistant API",
    description="REST API for local ML-assisted trading setup recommendations.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(market.router)
app.include_router(features.router)
app.include_router(signals.router)
app.include_router(backtest.router)
app.include_router(model.router)
app.include_router(risk.router)
app.include_router(paper.router)


@app.get("/api/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    """Return API health status."""
    return HealthResponse(status="ok", service="localquant-assistant")


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    """Return standard bad-request errors."""
    return _error_response(status_code=400, code="bad_request", message=str(exc))


@app.exception_handler(HTTPException)
async def http_error_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Return standard HTTP errors."""
    return _error_response(
        status_code=exc.status_code,
        code="http_error",
        message=str(exc.detail),
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Return standard unexpected errors without leaking stack traces."""
    return _error_response(
        status_code=500,
        code="internal_error",
        message="Internal server error.",
    )
