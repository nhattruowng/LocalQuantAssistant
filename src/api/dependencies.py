"""FastAPI dependencies."""

from __future__ import annotations

from functools import lru_cache

from api.services.localquant_service import LocalQuantApiService
from config.loader import load_settings
from utils.logger import setup_logger


@lru_cache(maxsize=1)
def get_service() -> LocalQuantApiService:
    """Return a cached API service instance."""
    settings = load_settings()
    logger = setup_logger(settings.logging)
    return LocalQuantApiService(settings=settings, logger=logger)
