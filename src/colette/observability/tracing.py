"""OpenTelemetry tracing setup (FR-ORC-015).

Call ``init_tracing()`` once at application startup.  Then use
``get_tracer()`` in any module to create spans.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

if TYPE_CHECKING:
    from colette.config import Settings

logger = structlog.get_logger(__name__)

_provider: TracerProvider | None = None


def init_tracing(settings: Settings) -> TracerProvider:
    """Initialize the global OTel TracerProvider.

    Safe to call multiple times -- returns the existing provider on re-entry.

    Args:
        settings: Application settings providing service name and exporter endpoint.

    Returns:
        The singleton :class:`TracerProvider` instance.
    """
    global _provider
    if _provider is not None:
        logger.debug("tracing_already_initialized")
        return _provider

    resource = Resource.create({"service.name": settings.otel_service_name})
    _provider = TracerProvider(resource=resource)

    exporter = OTLPSpanExporter(endpoint=settings.otel_exporter_endpoint)
    _provider.add_span_processor(BatchSpanProcessor(exporter))

    trace.set_tracer_provider(_provider)
    logger.info(
        "tracing_initialized",
        service_name=settings.otel_service_name,
        exporter_endpoint=settings.otel_exporter_endpoint,
    )
    return _provider


def get_tracer(name: str) -> trace.Tracer:
    """Return a tracer for the given component name.

    Args:
        name: Typically ``__name__`` of the calling module.

    Returns:
        An OpenTelemetry :class:`Tracer` scoped to *name*.
    """
    return trace.get_tracer(name)
