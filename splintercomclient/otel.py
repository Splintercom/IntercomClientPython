import logging
import os

LOG = logging.getLogger(__name__)


def setup_telemetry(service_name: str) -> None:
    api_key = os.getenv("HONEYCOMB_API_KEY", "")
    if not api_key:
        return

    from opentelemetry import trace
    from opentelemetry.baggage.propagation import W3CBaggagePropagator
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.requests import RequestsInstrumentor
    from opentelemetry.propagate import set_global_textmap
    from opentelemetry.propagators.composite import CompositeHTTPPropagator
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.trace.propagation.tracecontext import (
        TraceContextTextMapPropagator,
    )

    from splintercomclient.host_metrics import HostMetricsSpanProcessor, warmup

    set_global_textmap(
        CompositeHTTPPropagator(
            [TraceContextTextMapPropagator(), W3CBaggagePropagator()]
        )
    )

    warmup()

    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(HostMetricsSpanProcessor())
    provider.add_span_processor(
        BatchSpanProcessor(
            OTLPSpanExporter(
                endpoint="https://api.honeycomb.io/v1/traces",
                headers={"x-honeycomb-team": api_key},
            )
        )
    )
    trace.set_tracer_provider(provider)

    RequestsInstrumentor().instrument()

    LOG.info("OpenTelemetry -> Honeycomb: service=%s", service_name)
