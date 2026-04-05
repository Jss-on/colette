"""Structured logging configuration using structlog (FR-ORC-015).

Call :func:`configure_logging` once at application startup to set up
structured JSON logging with consistent formatting, log level filtering,
and standard library integration.

Example::

    from colette.observability.logging import configure_logging
    configure_logging(log_level="DEBUG", log_format="console")

Phase 6 adds :func:`cli_console_renderer` — a pipeline-aware renderer
that formats log events with ``[stage:X] [agent:Y] [model:Z]`` tags
for human-readable CLI output.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import MutableMapping
from typing import Any

import structlog


def cli_console_renderer(
    _logger: Any, _method_name: str, event_dict: MutableMapping[str, Any]
) -> str:
    """Pipeline-aware console renderer for ``--log-format console``.

    Formats log events as::

        2026-03-31T14:02:31Z [    INFO] [stage:requirements] [agent:analyst] stage.start
        2026-03-31T14:03:01Z [    INFO] [stage:design] [agent:architect] stage.start | endpoints=12

    Context keys ``stage``, ``agent``, and ``model`` are rendered as
    bracket tags.  Remaining keys are appended as ``key=value`` pairs.

    This is a **terminal renderer** — it returns a ``str``, not a dict,
    so it must be the last processor in the chain.
    """
    # Extract pipeline context tags.
    stage = event_dict.pop("stage", "")
    agent = event_dict.pop("agent", "")
    model = event_dict.pop("model", "")

    # Extract standard fields.
    timestamp = event_dict.pop("timestamp", "")
    level = str(event_dict.pop("log_level", "info")).upper()
    event_dict.pop("logger_name", None)
    event = event_dict.pop("event", "")

    # Build tag prefix.
    tags: list[str] = []
    if stage:
        tags.append(f"[stage:{stage}]")
    if agent:
        tags.append(f"[agent:{agent}]")
    if model:
        tags.append(f"[model:{model}]")

    tag_str = " ".join(tags)
    if tag_str:
        tag_str += " "

    # Format remaining context as key=value (skip internal keys).
    extra_parts = [f"{k}={v}" for k, v in sorted(event_dict.items()) if not k.startswith("_")]
    extra = " ".join(extra_parts)

    # Compose the line.
    line = f"{timestamp} [{level:>8s}] {tag_str}{event}"
    if extra:
        line += f" | {extra}"

    return line


def configure_logging(
    *,
    log_level: str = "INFO",
    log_format: str = "json",
) -> None:
    """Initialize structlog with shared processors and stdlib integration.

    Args:
        log_level: Minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_format: Output format -- ``"json"`` for machine-readable or
            ``"console"`` for human-readable colored output (Phase 6).
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
        renderer: structlog.types.Processor = cli_console_renderer
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
    for name in ("httpx", "httpcore", "opentelemetry"):
        logging.getLogger(name).setLevel(logging.WARNING)
