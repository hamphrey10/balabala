"""Structured logging setup via Loguru."""

from __future__ import annotations

import sys
from typing import Any

from loguru import logger

_CONFIGURED = False


def configure_logging(*, level: str = "INFO", serialize: bool = False) -> None:
    """Configure process-wide Loguru sinks. Idempotent for the first call pattern."""
    global _CONFIGURED
    logger.remove()
    logger.add(
        sys.stderr,
        level=level.upper(),
        serialize=serialize,
        format=(
            "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | {name}:{function}:{line} | {message}"
            if not serialize
            else "{message}"
        ),
        enqueue=False,
        backtrace=False,
        diagnose=False,
    )
    _CONFIGURED = True


def get_logger(name: str | None = None) -> Any:
    """Return a Loguru logger bound with an optional module name."""
    if not _CONFIGURED:
        configure_logging()
    if name:
        return logger.bind(module=name)
    return logger
