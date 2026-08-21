"""Structured logging configuration."""

import logging
import sys
from typing import TextIO

import structlog


def configure_logging(level: str, stream: TextIO | None = None) -> None:
    """Configure JSON logs for the application."""
    logging.basicConfig(
        format="%(message)s",
        level=level.upper(),
        stream=stream or sys.stdout,
        force=True,
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelNamesMapping().get(level.upper(), logging.INFO)
        ),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
