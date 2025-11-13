"""Distributed Tracing for ccBitTorrent.

from __future__ import annotations

Provides comprehensive tracing including:
- Request tracing
- Performance profiling
- Span management
- Trace correlation
- OpenTelemetry integration
"""

from __future__ import annotations

import asyncio
import contextvars
import json
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from typing_extensions import Self

from ccbt.utils.events import Event, EventType, emit_event
from ccbt.utils.logging_config import get_logger

logger = get_logger(__name__)


class SpanStatus(Enum):
    """Span status."""

    OK = "ok"
    ERROR = "error"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class SpanKind(Enum):
    """Span kind."""

    CLIENT = "client"
    SERVER = "server"
    PRODUCER = "producer"
    CONSUMER = "consumer"
    INTERNAL = "internal"


@dataclass
class Span:
    """Tracing span."""

    trace_id: str
    span_id: str
    parent_span_id: str | None
    name: str
    kind: SpanKind
    start_time: float
    end_time: float | None = None
    duration: float | None = None
    status: SpanStatus = SpanStatus.OK
    attributes: dict[str, Any] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)
    links: list[dict[str, str]] = field(default_factory=list)
    resource: dict[str, Any] = field(default_factory=dict)


@dataclass
class Trace:
    """Complete trace."""

    trace_id: str
    spans: list[Span] = field(default_factory=list)
    start_time: float | None = None
    end_time: float | None = None
    duration: float = 0.0
    root_span: Span | None = None


class TracingManager:
    """Distributed tracing manager."""

    def __init__(self):
        """Initialize tracing manager."""
        self.active_spans: dict[str, Span] = {}
        self.completed_spans: deque = deque(maxlen=10000)
        self.traces: dict[str, Trace] = {}
        self.trace_context: contextvars.ContextVar[dict[str, str] | None] = (
            contextvars.ContextVar("trace_context", default=None)
        )

        # Configuration
        self.sampling_rate = 1.0  # 100% sampling
        self.max_spans_per_trace = 1000
        self.span_retention_seconds = 3600  # 1 hour

        # Statistics
        self.stats = {
            "spans_created": 0,
            "spans_completed": 0,
            "traces_created": 0,
            "traces_completed": 0,
            "sampling_decisions": 0,
            "sampled_spans": 0,
        }

        # Thread-local storage for context
        self._local = threading.local()

    def start_span(
        self,
        name: str,
        kind: SpanKind = SpanKind.INTERNAL,
        parent_span_id: str | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> str:
        """Start a new span."""
        # Generate trace ID if not in context
        trace_id = self._get_or_create_trace_id()

        # Generate span ID
        span_id = str(uuid.uuid4())

        # Create span
        span = Span(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            name=name,
            kind=kind,
            start_time=time.time(),
            attributes=attributes or {},
        )

        # Store span
        self.active_spans[span_id] = span

        # Update context
        self._update_trace_context(trace_id, span_id)

        # Update statistics
        self.stats["spans_created"] += 1

        # Emit span started event
        task = asyncio.create_task(
            emit_event(
                Event(
                    event_type=EventType.SPAN_STARTED.value,
                    data={
                        "trace_id": trace_id,
                        "span_id": span_id,
                        "name": name,
                        "kind": kind.value,
                        "timestamp": span.start_time,
                    },
                ),
            ),
        )
        task.add_done_callback(lambda _t: None)  # Discard task reference

        return span_id

    def end_span(
        self,
        span_id: str,
        status: SpanStatus = SpanStatus.OK,
        attributes: dict[str, Any] | None = None,
    ) -> Span | None:
        """End a span."""
        if span_id not in self.active_spans:
            return None

        span = self.active_spans[span_id]
        span.end_time = time.time()
        span.duration = span.end_time - span.start_time
        span.status = status

        # Update attributes
        if attributes:
            span.attributes.update(attributes)

        # Move to completed spans
        self.completed_spans.append(span)
        del self.active_spans[span_id]

        # Update trace
        self._update_trace(span)

        # Update statistics
        self.stats["spans_completed"] += 1

        # Emit span ended event
        task = asyncio.create_task(
            emit_event(
                Event(
                    event_type=EventType.SPAN_ENDED.value,
                    data={
                        "trace_id": span.trace_id,
                        "span_id": span_id,
                        "name": span.name,
                        "duration": span.duration,
                        "status": status.value,
                        "timestamp": span.end_time,
                    },
                ),
            ),
        )
        task.add_done_callback(lambda _t: None)  # Discard task reference

        return span

    def add_span_event(
        self,
        span_id: str,
        name: str,
        attributes: dict[str, Any] | None = None,
    ) -> None:
        """Add an event to a span."""
        if span_id not in self.active_spans:
            return

        span = self.active_spans[span_id]
        event = {
            "name": name,
            "timestamp": time.time(),
            "attributes": attributes or {},
        }
        span.events.append(event)

    def add_span_attribute(self, span_id: str, key: str, value: Any) -> None:
        """Add an attribute to a span."""
        if span_id not in self.active_spans:
            return

        span = self.active_spans[span_id]
        span.attributes[key] = value

    def get_active_span(self) -> Span | None:
        """Get the current active span."""
        span_id = self._get_current_span_id()
        if span_id and span_id in self.active_spans:
            return self.active_spans[span_id]
        return None

    def get_trace(self, trace_id: str) -> Trace | None:
        """Get a complete trace."""
        return self.traces.get(trace_id)

    def get_trace_spans(self, trace_id: str) -> list[Span]:
        """Get all spans for a trace."""
        return [span for span in self.completed_spans if span.trace_id == trace_id]

    def get_trace_statistics(self) -> dict[str, Any]:
        """Get trace statistics."""
        return {
            "spans_created": self.stats["spans_created"],
            "spans_completed": self.stats["spans_completed"],
            "traces_created": self.stats["traces_created"],
            "traces_completed": self.stats["traces_completed"],
            "active_spans": len(self.active_spans),
            "completed_spans": len(self.completed_spans),
            "traces": len(self.traces),
            "sampling_rate": self.sampling_rate,
            "sampling_decisions": self.stats["sampling_decisions"],
            "sampled_spans": self.stats["sampled_spans"],
        }

    def export_traces(self, format_type: str = "json") -> str:
        """Export traces in specified format."""
        if format_type == "json":
            traces_data = {}
            for trace_id, trace in self.traces.items():
                traces_data[trace_id] = {
                    "trace_id": trace_id,
                    "start_time": trace.start_time,
                    "end_time": trace.end_time,
                    "duration": trace.duration,
                    "spans": [
                        {
                            "span_id": span.span_id,
                            "parent_span_id": span.parent_span_id,
                            "name": span.name,
                            "kind": span.kind.value,
                            "start_time": span.start_time,
                            "end_time": span.end_time,
                            "duration": span.duration,
                            "status": span.status.value,
                            "attributes": span.attributes,
                            "events": span.events,
                        }
                        for span in trace.spans
                    ],
                }
            return json.dumps(traces_data, indent=2)
        msg = f"Unsupported format: {format_type}"
        raise ValueError(msg)

    def cleanup_old_traces(self, max_age_seconds: int = 3600) -> None:
        """Clean up old traces and spans."""
        current_time = time.time()
        cutoff_time = current_time - max_age_seconds

        # Clean up old completed spans
        while self.completed_spans and self.completed_spans[0].start_time < cutoff_time:
            self.completed_spans.popleft()

        # Clean up old traces
        to_remove = []
        for trace_id, trace in self.traces.items():
            if trace.start_time is not None and trace.start_time < cutoff_time:
                to_remove.append(trace_id)

        for trace_id in to_remove:
            del self.traces[trace_id]

    def set_sampling_rate(self, rate: float) -> None:
        """Set sampling rate (0.0 to 1.0)."""
        self.sampling_rate = max(0.0, min(1.0, rate))

    def _get_or_create_trace_id(self) -> str:
        """Get or create trace ID."""
        context = self.trace_context.get()
        if context is None:
            context = {}
            self.trace_context.set(context)

        trace_id = context.get("trace_id")

        if not trace_id:
            trace_id = str(uuid.uuid4())
            self._update_trace_context(trace_id, None)

        return trace_id

    def _get_current_span_id(self) -> str | None:
        """Get current span ID from context."""
        context = self.trace_context.get()
        if context is None:
            return None
        return context.get("span_id")

    def _update_trace_context(self, trace_id: str, span_id: str | None) -> None:
        """Update trace context."""
        context = {
            "trace_id": trace_id,
            "span_id": span_id,
        }
        # Filter out None values to ensure dict[str, str] type
        filtered_context = {k: v for k, v in context.items() if v is not None}
        self.trace_context.set(filtered_context)

    def _update_trace(self, span: Span) -> None:
        """Update trace with completed span."""
        trace_id = span.trace_id

        if trace_id not in self.traces:
            trace = Trace(trace_id=trace_id)
            self.traces[trace_id] = trace
            self.stats["traces_created"] += 1
        else:
            trace = self.traces[trace_id]

        # Add span to trace
        trace.spans.append(span)

        # Update trace timing
        if trace.start_time is None or span.start_time < trace.start_time:
            trace.start_time = span.start_time
            trace.root_span = span

        if trace.end_time is None or (
            span.end_time is not None and span.end_time > trace.end_time
        ):
            trace.end_time = span.end_time

        if trace.start_time is not None and trace.end_time is not None:
            trace.duration = trace.end_time - trace.start_time

        # Check if trace is complete
        if self._is_trace_complete(trace):
            self.stats["traces_completed"] += 1

            # Emit trace completed event
            task = asyncio.create_task(
                emit_event(
                    Event(
                        event_type=EventType.TRACE_COMPLETED.value,
                        data={
                            "trace_id": trace_id,
                            "duration": trace.duration,
                            "span_count": len(trace.spans),
                            "timestamp": trace.end_time,
                        },
                    ),
                ),
            )
            task.add_done_callback(lambda _t: None)  # Discard task reference

    def _is_trace_complete(self, trace: Trace) -> bool:
        """Check if trace is complete."""
        # A trace is complete when all spans are completed
        # This is a simplified check - in practice, you might need more sophisticated logic
        return len(trace.spans) > 0 and all(
            span.end_time is not None for span in trace.spans
        )

    def _should_sample(self) -> bool:
        """Determine if current trace should be sampled."""
        import random

        self.stats["sampling_decisions"] += 1

        if random.random() < self.sampling_rate:  # nosec B311 - Sampling rate is not security-sensitive
            self.stats["sampled_spans"] += 1
            return True

        return False


class TraceContext:
    """Context manager for tracing."""

    def __init__(
        self,
        tracing_manager: TracingManager,
        name: str,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes: dict[str, Any] | None = None,
    ):
        """Initialize trace context."""
        self.tracing_manager = tracing_manager
        self.name = name
        self.kind = kind
        self.attributes = attributes
        self.span_id: str | None = None

    def __enter__(self) -> Self:
        """Enter the span context manager."""
        # Check if we should sample
        if not self.tracing_manager._should_sample():  # noqa: SLF001
            return self

        # Get parent span ID
        parent_span_id = self.tracing_manager._get_current_span_id()  # noqa: SLF001

        # Start span
        self.span_id = self.tracing_manager.start_span(
            self.name,
            self.kind,
            parent_span_id,
            self.attributes,
        )

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit the span context manager."""
        if self.span_id:
            # Determine status
            status = SpanStatus.ERROR if exc_type is not None else SpanStatus.OK

            # End span
            self.tracing_manager.end_span(self.span_id, status)

    def add_event(self, name: str, attributes: dict[str, Any] | None = None) -> None:
        """Add event to current span."""
        if self.span_id:
            self.tracing_manager.add_span_event(self.span_id, name, attributes)

    def add_attribute(self, key: str, value: Any) -> None:
        """Add attribute to current span."""
        if self.span_id:
            self.tracing_manager.add_span_attribute(self.span_id, key, value)


def trace_function(tracing_manager: TracingManager, name: str | None = None):
    """Decorator for tracing functions."""

    def decorator(func):
        def wrapper(*args, **kwargs):
            trace_name = name or f"{func.__module__}.{func.__name__}"

            with TraceContext(tracing_manager, trace_name):
                return func(*args, **kwargs)

        return wrapper

    return decorator


def trace_async_function(tracing_manager: TracingManager, name: str | None = None):
    """Decorator for tracing async functions."""

    def decorator(func):
        async def wrapper(*args, **kwargs):
            trace_name = name or f"{func.__module__}.{func.__name__}"

            with TraceContext(tracing_manager, trace_name):
                return await func(*args, **kwargs)

        return wrapper

    return decorator
