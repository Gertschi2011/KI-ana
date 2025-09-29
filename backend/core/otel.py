from __future__ import annotations
import os

def init_tracing(service_name: str = "kiana-backend") -> None:
    # Minimal stub – can be expanded to configure OTLP exporter
    if not os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
        return
    # Real setup would initialize tracer provider, resource, OTLP exporter
    # Kept compact for scaffold; production can wire OpenTelemetry SDK here.
    return
