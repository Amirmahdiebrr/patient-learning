"""
app/core/logging_config.py

Central logging setup. In production (APP_ENV=production) emits
structured JSON lines enriched with per-request context. In
development keeps the human-readable single-line format.
"""

import logging
import sys

from app.core.config import settings
from app.core.structured_logging import JSONRequestFormatter

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        JSONRequestFormatter() if settings.is_production
        else logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    root_logger.handlers = [handler]

    for noisy_logger in ("httpx", "httpcore"):
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)