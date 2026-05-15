"""Logging setup."""

from __future__ import annotations

import logging
import sys

from config.settings import LoggingSettings


def setup_logger(settings: LoggingSettings) -> logging.Logger:
    """Configure and return the application logger."""
    logging.basicConfig(
        level=settings.level.upper(),
        stream=sys.stderr,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        force=True,
    )
    return logging.getLogger("localquant")
