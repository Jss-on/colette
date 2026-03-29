"""OpenTelemetry tracing setup (FR-ORC-015).

Call ``init_tracing()`` once at application startup.  Then use
``get_tracer()`` in any module to create spans.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

if TYPE_CHECKING:
    from colette.config import Settings

_provider: TracerProvider | None = None


def init_tracing(settings: Settings) -> TracerProvider:
    """Initialize the global OTel TracerProvider.

    Safe to call multiple times — returns the existing provider on re-entry.
    """
    global _provider
    if _provider is not None:
        return _provider

    resource = Resource.create({"service.name": settings.otel_service_name})
    _provider = TracerProvider(resource=resource)

    exporter = OTLPSpanExporter(endpoint=settings.otel_exporter_endpoint)
    _provider.add_span_processor(BatchSpanProcessor(exporter))

    trace.set_tracer_provider(_provider)
    return _provider


def get_tracer(name: str) -> trace.Tracer:
    """Return a tracer for the given component name."""
    return trace.get_tracer(name)
