"""Telemetry service - OpenTelemetry integration with strict CLI timeouts."""

import atexit
import logging
import time
from contextlib import contextmanager
from typing import Any

logger = logging.getLogger("sift.telemetry.service")

# Singleton instance
_telemetry: "CLITelemetry | None" = None


class NoOpSpan:
    """No-op span for when telemetry is disabled."""

    def set_attribute(self, key: str, value: Any) -> None:
        pass

    def set_status(self, status: Any) -> None:
        pass

    def record_exception(self, exc: Exception) -> None:
        pass

    def end(self) -> None:
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class CLITelemetry:
    """CLI telemetry with OpenTelemetry, designed for short-lived processes.

    Key constraints:
    - Strict 2-second exporter timeout (CLI must never hang)
    - 3-second shutdown timeout
    - Zero overhead when disabled (no-op tracer/counters)
    """

    def __init__(self, enabled: bool = False):
        self._enabled = enabled
        self._tracer = None
        self._meter = None
        self._provider = None
        self._counters: dict[str, Any] = {}
        self._histograms: dict[str, Any] = {}

        if enabled:
            self._setup_otel()

    def _setup_otel(self) -> None:
        """Initialize OpenTelemetry with strict timeouts."""
        try:
            from opentelemetry import metrics, trace
            from opentelemetry.sdk.metrics import MeterProvider
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor

            resource = Resource.create(
                {
                    "service.name": "sift-cli",
                    "service.version": _get_version(),
                }
            )

            # Tracer with batch processor (exports in background)
            tracer_provider = TracerProvider(resource=resource)

            # Try OTLP exporter, fall back to console for debug
            try:
                from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

                exporter = OTLPSpanExporter(timeout=2)
            except ImportError:
                logger.debug("OTLP exporter not available, telemetry spans will not be exported")
                exporter = None

            if exporter:
                processor = BatchSpanProcessor(
                    exporter,
                    max_queue_size=100,
                    max_export_batch_size=50,
                    schedule_delay_millis=1000,
                )
                tracer_provider.add_span_processor(processor)

            trace.set_tracer_provider(tracer_provider)
            self._provider = tracer_provider
            self._tracer = trace.get_tracer("sift")

            # Meter for counters/histograms
            meter_provider = MeterProvider(resource=resource)
            metrics.set_meter_provider(meter_provider)
            self._meter = metrics.get_meter("sift")

            # Define instruments
            self._counters["command.count"] = self._meter.create_counter(
                "sift.command.count",
                description="Number of CLI commands executed",
            )
            self._counters["command.error"] = self._meter.create_counter(
                "sift.command.error",
                description="Number of CLI command errors",
            )
            self._counters["provider.used"] = self._meter.create_counter(
                "sift.provider.used",
                description="AI provider usage count",
            )
            self._histograms["command.duration"] = self._meter.create_histogram(
                "sift.command.duration",
                description="CLI command duration in seconds",
                unit="s",
            )

            # Register bounded shutdown
            atexit.register(self._shutdown)

            logger.debug("OpenTelemetry initialized")

        except ImportError:
            logger.debug("OpenTelemetry SDK not installed, telemetry disabled")
            self._enabled = False
        except Exception:
            logger.debug("Failed to initialize OpenTelemetry", exc_info=True)
            self._enabled = False

    def _shutdown(self) -> None:
        """Graceful shutdown with strict 3-second timeout."""
        if self._provider:
            try:
                self._provider.shutdown(timeout_millis=3000)
            except Exception:
                pass

    @contextmanager
    def track_command(self, command_name: str):
        """Context manager to track command execution."""
        if not self._enabled:
            yield NoOpSpan()
            return

        start = time.monotonic()
        span = NoOpSpan()

        if self._tracer:
            span = self._tracer.start_span(f"sift.{command_name}")
            span.set_attribute("sift.command", command_name)

        try:
            yield span
            # Record success
            if "command.count" in self._counters:
                self._counters["command.count"].add(1, {"command": command_name, "status": "ok"})
        except Exception as exc:
            # Record error (type only, never message/trace)
            if "command.error" in self._counters:
                self._counters["command.error"].add(
                    1,
                    {
                        "command": command_name,
                        "error_type": type(exc).__name__,
                    },
                )
            if hasattr(span, "record_exception"):
                span.record_exception(exc)
            raise
        finally:
            duration = time.monotonic() - start
            if "command.duration" in self._histograms:
                self._histograms["command.duration"].record(duration, {"command": command_name})
            if hasattr(span, "end"):
                span.end()

    def record_provider_used(self, provider_name: str, model: str = "") -> None:
        """Record which AI provider was used."""
        if self._enabled and "provider.used" in self._counters:
            self._counters["provider.used"].add(
                1,
                {
                    "provider": provider_name,
                    "model": model,
                },
            )


def _get_version() -> str:
    """Get sift version safely."""
    try:
        from importlib.metadata import version

        return version("sift-cli")
    except Exception:
        return "0.0.0"


def get_telemetry() -> CLITelemetry:
    """Get the singleton telemetry instance."""
    global _telemetry
    if _telemetry is None:
        from sift.telemetry.consent import ConsentManager

        consent = ConsentManager()
        _telemetry = CLITelemetry(enabled=consent.is_enabled())
    return _telemetry


def reset_telemetry() -> None:
    """Reset the singleton (for testing)."""
    global _telemetry
    _telemetry = None
