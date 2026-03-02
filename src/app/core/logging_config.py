"""
Structured JSON logging configuration.

Provides consistent, machine-parseable log output with:
  - ISO-8601 timestamps
  - Log level, logger name, module
  - Request correlation IDs (when available)
  - Extra fields passed via `logger.info("msg", extra={...})`

Usage:
  Call `setup_logging()` once at app startup (in lifespan).
"""

import logging
import sys

from pythonjsonlogger.json import JsonFormatter

from app.core.config import settings


def setup_logging() -> None:
    """Configure root logger with JSON output for production, human-readable for dev."""
    root = logging.getLogger()

    # Remove any existing handlers (uvicorn adds its own)
    root.handlers.clear()

    level = logging.DEBUG if settings.ENV == "development" else logging.INFO
    root.setLevel(level)

    handler = logging.StreamHandler(sys.stdout)

    if settings.LOG_FORMAT == "json":
        formatter = JsonFormatter(
            fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
            rename_fields={"asctime": "timestamp", "levelname": "level", "name": "logger"},
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )
    else:
        formatter = logging.Formatter(
            fmt="%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )

    handler.setFormatter(formatter)
    root.addHandler(handler)

    # Quiet noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
