"""Pydantic response schemas for the REST API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ErrorEnvelope(BaseModel):
    """Standard API error envelope."""

    error: dict[str, str]


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    service: str


class ListResponse(BaseModel):
    """Simple list response."""

    items: list[str]


class CandleResponse(BaseModel):
    """OHLCV candle response."""

    symbol: str
    timeframe: str
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float


class DataUpdateResponse(BaseModel):
    """Market data update response."""

    inserted: int


class FeatureBuildResponse(BaseModel):
    """Feature build response."""

    rows: int
    columns: list[str]


class ModelTrainResponse(BaseModel):
    """Model training response."""

    model_path: str
    metadata_path: str
    model_type: str
    metrics: dict[str, Any]
    feature_columns: list[str]
