"""Structured logging configuration using structlog (FR-ORC-015).

Call :func:`configure_logging` once at application startup to set up
structured JSON logging with consistent formatting, log level filtering,
and standard library integration.

Example::

    from colette.observability.logging import configure_logging
    configure_logging(log_level="DEBUG", log_format="console")
"""

from __future__ import annotations

import logging
import sys

import structlog


def configure_logging(
    *,
    log_level: str = "INFO",
    log_format: str = "json",
) -> None:
    """Initialize structlog with shared processors and stdlib integration.

    Args:
        log_level: Minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_format: Output format -- ``"json"`` for machine-readable or
            ``"console"`` for human-readable colored output.
    """
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if log_format == "console":
        renderer: structlog.types.Processor = structlog.dev.ConsoleRenderer()
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
        foreign_pre_chain=shared_processors,
    )

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(log_level.upper())

    # Quiet noisy third-party loggers
    for name in ("httpx", "httpcore", "litellm", "opentelemetry"):
        logging.getLogger(name).setLevel(logging.WARNING)
