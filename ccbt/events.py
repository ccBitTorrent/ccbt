"""Event-driven architecture for ccBitTorrent.

from __future__ import annotations

Provides a comprehensive event system for decoupled communication
between components with typed events and event replay capability.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from ccbt.exceptions import CCBTError
from ccbt.logging_config import LoggingContext, get_logger


class EventPriority(Enum):
    """Event priority levels."""

    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


class EventType(Enum):
    """Built-in event types."""

    # Peer events
    PEER_CONNECTED = "peer_connected"
    PEER_DISCONNECTED = "peer_disconnected"
    PEER_HANDSHAKE_COMPLETE = "peer_handshake_complete"
    PEER_BITFIELD_RECEIVED = "peer_bitfield_received"

    # Piece events
    PIECE_REQUESTED = "piece_requested"
    PIECE_DOWNLOADED = "piece_downloaded"
    PIECE_VERIFIED = "piece_verified"
    PIECE_COMPLETED = "piece_completed"

    # Torrent events
    TORRENT_ADDED = "torrent_added"
    TORRENT_REMOVED = "torrent_removed"
    TORRENT_STARTED = "torrent_started"
    TORRENT_STOPPED = "torrent_stopped"
    TORRENT_COMPLETED = "torrent_completed"

    # Tracker events
    TRACKER_ANNOUNCE = "tracker_announce"
    TRACKER_ANNOUNCE_SUCCESS = "tracker_announce_success"
    TRACKER_ANNOUNCE_ERROR = "tracker_announce_error"

    # DHT events
    DHT_NODE_FOUND = "dht_node_found"
    DHT_PEER_FOUND = "dht_peer_found"
    DHT_QUERY_COMPLETE = "dht_query_complete"

    # System events
    SYSTEM_START = "system_start"
    SYSTEM_STOP = "system_stop"
    SYSTEM_ERROR = "system_error"

    # Performance events
    PERFORMANCE_METRIC = "performance_metric"
    BANDWIDTH_UPDATE = "bandwidth_update"
    DISK_IO_UPDATE = "disk_io_update"

    # Fast Extension events
    PIECE_SUGGESTED = "piece_suggested"
    PEER_HAVE_ALL = "peer_have_all"
    PEER_HAVE_NONE = "peer_have_none"
    REQUEST_REJECTED = "request_rejected"
    PIECE_ALLOWED_FAST = "piece_allowed_fast"

    # Extension Protocol events
    EXTENSION_HANDSHAKE = "extension_handshake"
    UNKNOWN_EXTENSION_MESSAGE = "unknown_extension_message"
    EXTENSION_ERROR = "extension_error"

    # PEX events
    PEER_DISCOVERED = "peer_discovered"
    PEER_DROPPED = "peer_dropped"

    # DHT events
    DHT_NODE_ADDED = "dht_node_added"
    DHT_NODE_REMOVED = "dht_node_removed"
    DHT_ERROR = "dht_error"

    # WebSeed events
    WEBSEED_ADDED = "webseed_added"
    WEBSEED_REMOVED = "webseed_removed"
    WEBSEED_DOWNLOAD_SUCCESS = "webseed_download_success"
    WEBSEED_DOWNLOAD_FAILED = "webseed_download_failed"
    WEBSEED_ERROR = "webseed_error"

    # Extension management events
    EXTENSION_STARTED = "extension_started"
    EXTENSION_STOPPED = "extension_stopped"

    # Protocol events
    PROTOCOL_STARTED = "protocol_started"
    PROTOCOL_STOPPED = "protocol_stopped"
    PROTOCOL_STATE_CHANGED = "protocol_state_changed"
    PROTOCOL_REGISTERED = "protocol_registered"
    PROTOCOL_UNREGISTERED = "protocol_unregistered"
    PROTOCOL_ERROR = "protocol_error"
    SUB_PROTOCOL_STARTED = "sub_protocol_started"
    SUB_PROTOCOL_STOPPED = "sub_protocol_stopped"
    SUB_PROTOCOL_ERROR = "sub_protocol_error"
    SUB_PROTOCOL_ANNOUNCE = "sub_protocol_announce"
    HYBRID_ANNOUNCE = "hybrid_announce"

    # WebTorrent events
    WEBRTC_CONNECTION_ESTABLISHED = "webrtc_connection_established"
    WEBRTC_CONNECTION_FAILED = "webrtc_connection_failed"
    DATA_CHANNEL_OPENED = "data_channel_opened"
    DATA_CHANNEL_CLOSED = "data_channel_closed"

    # IPFS events
    IPFS_CONTENT_ADDED = "ipfs_content_added"
    IPFS_CONTENT_RETRIEVED = "ipfs_content_retrieved"
    IPFS_CONTENT_PINNED = "ipfs_content_pinned"
    IPFS_CONTENT_UNPINNED = "ipfs_content_unpinned"
    IPFS_PEER_DISCOVERED = "ipfs_peer_discovered"

    # Peer events
    PEER_ADDED = "peer_added"
    PEER_REMOVED = "peer_removed"
    PEER_CONNECTION_FAILED = "peer_connection_failed"

    # Tracker events
    TRACKER_ERROR = "tracker_error"

    # Security events
    SECURITY_EVENT = "security_event"
    SECURITY_BLACKLIST_ADDED = "security_blacklist_added"
    SECURITY_BLACKLIST_REMOVED = "security_blacklist_removed"
    SECURITY_WHITELIST_ADDED = "security_whitelist_added"
    SECURITY_WHITELIST_REMOVED = "security_whitelist_removed"

    # Encryption events
    ENCRYPTION_INITIATED = "encryption_initiated"
    ENCRYPTION_HANDSHAKE_COMPLETED = "encryption_handshake_completed"
    ENCRYPTION_HANDSHAKE_FAILED = "encryption_handshake_failed"
    ENCRYPTION_ERROR = "encryption_error"

    # ML events
    ML_PEER_PREDICTION = "ml_peer_prediction"
    ML_PIECE_PREDICTION = "ml_piece_prediction"
    ML_BANDWIDTH_ESTIMATED = "ml_bandwidth_estimated"
    ML_RATE_ADJUSTED = "ml_rate_adjusted"
    ML_ANOMALY_DETECTED = "ml_anomaly_detected"

    # Anomaly detection events
    ANOMALY_DETECTED = "anomaly_detected"

    # Rate limiting events
    RATE_LIMIT_ADAPTIVE_CHANGED = "rate_limit_adaptive_changed"

    # Monitoring events
    MONITORING_STARTED = "monitoring_started"
    MONITORING_STOPPED = "monitoring_stopped"
    MONITORING_ERROR = "monitoring_error"

    # Alert events
    ALERT_TRIGGERED = "alert_triggered"
    ALERT_RESOLVED = "alert_resolved"
    NOTIFICATION_ERROR = "notification_error"

    # Dashboard events
    DASHBOARD_CREATED = "dashboard_created"
    WIDGET_ADDED = "widget_added"
    WIDGET_REMOVED = "widget_removed"
    WIDGET_UPDATED = "widget_updated"
    DASHBOARD_ERROR = "dashboard_error"

    # Tracing events
    SPAN_STARTED = "span_started"
    SPAN_ENDED = "span_ended"
    TRACE_COMPLETED = "trace_completed"

    # Profiling events
    PROFILING_STARTED = "profiling_started"
    PROFILING_STOPPED = "profiling_stopped"
    BOTTLENECK_DETECTED = "bottleneck_detected"

    # Global metrics events
    GLOBAL_METRICS_UPDATE = "global_metrics_update"


class EventError(CCBTError):
    """Exception raised for event-related errors."""


@dataclass
class Event:
    """Base event class."""

    event_type: str = ""
    timestamp: float = field(default_factory=time.time)
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    priority: EventPriority = EventPriority.NORMAL
    source: str | None = None
    data: dict[str, Any] = field(default_factory=dict)
    correlation_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert event to dictionary."""
        return {
            "event_type": self.event_type,
            "timestamp": self.timestamp,
            "event_id": self.event_id,
            "priority": self.priority.value,
            "source": self.source,
            "data": self.data,
            "correlation_id": self.correlation_id,
        }

    def to_json(self) -> str:
        """Convert event to JSON string."""
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Event:
        """Create event from dictionary."""
        return cls(
            event_type=data["event_type"],
            timestamp=data["timestamp"],
            event_id=data["event_id"],
            priority=EventPriority(data["priority"]),
            source=data.get("source"),
            data=data["data"],
            correlation_id=data.get("correlation_id"),
        )

    @classmethod
    def from_json(cls, json_str: str) -> Event:
        """Create event from JSON string."""
        return cls.from_dict(json.loads(json_str))


# Typed event classes
@dataclass
class PeerConnectedEvent(Event):
    """Event emitted when a peer connects."""

    peer_ip: str = ""
    peer_port: int = 0
    peer_id: str | None = None

    def __post_init__(self):
        """Initialize event type and data."""
        self.event_type = EventType.PEER_CONNECTED.value
        self.data.update(
            {
                "peer_ip": self.peer_ip,
                "peer_port": self.peer_port,
                "peer_id": self.peer_id,
            },
        )


@dataclass
class PeerDisconnectedEvent(Event):
    """Event emitted when a peer disconnects."""

    peer_ip: str = ""
    peer_port: int = 0
    reason: str | None = None

    def __post_init__(self):
        """Initialize event type and data."""
        self.event_type = EventType.PEER_DISCONNECTED.value
        self.data.update(
            {
                "peer_ip": self.peer_ip,
                "peer_port": self.peer_port,
                "reason": self.reason,
            },
        )


@dataclass
class PieceDownloadedEvent(Event):
    """Event emitted when a piece is downloaded."""

    piece_index: int = 0
    piece_size: int = 0
    download_time: float = 0.0
    peer_ip: str | None = None

    def __post_init__(self):
        """Initialize event type and data."""
        self.event_type = EventType.PIECE_DOWNLOADED.value
        self.data.update(
            {
                "piece_index": self.piece_index,
                "piece_size": self.piece_size,
                "download_time": self.download_time,
                "peer_ip": self.peer_ip,
            },
        )


@dataclass
class TorrentCompletedEvent(Event):
    """Event emitted when a torrent is completed."""

    torrent_name: str = ""
    total_size: int = 0
    download_time: float = 0.0
    average_speed: float = 0.0

    def __post_init__(self):
        """Initialize event data after object creation."""
        self.event_type = EventType.TORRENT_COMPLETED.value
        self.data.update(
            {
                "torrent_name": self.torrent_name,
                "total_size": self.total_size,
                "download_time": self.download_time,
                "average_speed": self.average_speed,
            },
        )


@dataclass
class PerformanceMetricEvent(Event):
    """Event emitted for performance metrics."""

    metric_name: str = ""
    metric_value: float = 0.0
    metric_unit: str = ""
    tags: dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        """Initialize event data after object creation."""
        self.event_type = EventType.PERFORMANCE_METRIC.value
        self.data.update(
            {
                "metric_name": self.metric_name,
                "metric_value": self.metric_value,
                "metric_unit": self.metric_unit,
                "tags": self.tags,
            },
        )


class EventHandler(ABC):
    """Base class for event handlers."""

    def __init__(self, name: str):
        """Initialize event handler."""
        self.name = name
        self.logger = get_logger(f"event_handler.{name}")

    @abstractmethod
    async def handle(self, event: Event) -> None:
        """Handle an event."""

    def can_handle(self, _event: Event) -> bool:
        """Check if this handler can handle the event."""
        return True


class EventBus:
    """Event bus for managing events and handlers."""

    def __init__(self, max_queue_size: int = 10000):
        """Initialize event bus.

        Args:
            max_queue_size: Maximum size of event queue
        """
        self.max_queue_size = max_queue_size
        self.handlers: dict[str, list[EventHandler]] = {}
        self.event_queue: asyncio.Queue = asyncio.Queue(maxsize=max_queue_size)
        self.replay_buffer: list[Event] = []
        self.max_replay_events = 1000
        self.running = False
        self.logger = get_logger(__name__)
        self._loop: asyncio.AbstractEventLoop | None = None
        self._task: asyncio.Task | None = None

        # Statistics
        self.stats = {
            "events_processed": 0,
            "events_dropped": 0,
            "handlers_registered": 0,
            "queue_size": 0,
        }

    def register_handler(self, event_type: str, handler: EventHandler) -> None:
        """Register an event handler.

        Args:
            event_type: Type of event to handle
            handler: Handler instance
        """
        if event_type not in self.handlers:
            self.handlers[event_type] = []

        self.handlers[event_type].append(handler)
        self.stats["handlers_registered"] += 1
        self.logger.debug(
            "Registered handler '%s' for event type '%s'",
            handler.name,
            event_type,
        )

    def unregister_handler(self, event_type: str, handler: EventHandler) -> None:
        """Unregister an event handler.

        Args:
            event_type: Type of event
            handler: Handler instance
        """
        if event_type in self.handlers:
            try:
                self.handlers[event_type].remove(handler)
                self.logger.debug(
                    "Unregistered handler '%s' for event type '%s'",
                    handler.name,
                    event_type,
                )
            except ValueError:
                pass

    async def emit(self, event: Event) -> None:
        """Emit an event.

        Args:
            event: Event to emit
        """
        try:
            # Add to replay buffer
            self.replay_buffer.append(event)
            if len(self.replay_buffer) > self.max_replay_events:
                self.replay_buffer.pop(0)

            # Add to queue
            if self.event_queue.full():
                self.stats["events_dropped"] += 1
                self.logger.warning(
                    "Event queue full, dropping event: %s",
                    event.event_type,
                )
                return

            # If we somehow switched loops between start/emit, rebind queue lazily
            if self._loop is None:
                try:
                    self._loop = asyncio.get_running_loop()
                except RuntimeError:
                    self._loop = asyncio.get_event_loop()
            try:
                current_loop = asyncio.get_running_loop()
            except RuntimeError:
                current_loop = asyncio.get_event_loop()
            if self._loop is not current_loop:
                # Recreate queue on current loop to avoid cross-loop errors
                old_q = self.event_queue
                self.event_queue = asyncio.Queue(maxsize=self.max_queue_size)
                self._loop = current_loop
                # Drain old queue non-blocking into new one to preserve events
                try:
                    while True:
                        item = old_q.get_nowait()
                        await self.event_queue.put(item)
                except asyncio.QueueEmpty:
                    pass

            await self.event_queue.put(event)
            self.stats["queue_size"] = self.event_queue.qsize()

        except Exception:
            self.logger.exception("Failed to emit event")

    async def start(self) -> None:
        """Start the event bus."""
        if self.running:
            return

        # Rebind to the current running loop and recreate the queue if needed
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = asyncio.get_event_loop()

        if self._loop is not current_loop:
            # Cancel any previous processing task bound to another loop
            if self._task is not None and not self._task.done():
                with contextlib.suppress(Exception):
                    self._task.cancel()
            self._task = None
            # Recreate queue bound to this loop
            self.event_queue = asyncio.Queue(maxsize=self.max_queue_size)
            self._loop = current_loop

        self.running = True
        self.logger.info("Event bus started")

        # Start event processing task on this loop
        self._task = asyncio.create_task(self._process_events())

    async def stop(self) -> None:
        """Stop the event bus."""
        if not self.running:
            return

        self.running = False
        self.logger.info("Event bus stopped")
        # Cancel and await processing task to avoid stray logging on closed streams
        if self._task is not None:
            self._task.cancel()
            # Ensure cancellation is processed; ignore cancellation-related errors
            with contextlib.suppress(Exception):
                await asyncio.gather(self._task, return_exceptions=True)
            self._task = None

    async def _process_events(self) -> None:
        """Process events from the queue."""
        while self.running:
            try:
                event = await asyncio.wait_for(self.event_queue.get(), timeout=1.0)
                await self._handle_event(event)
                self.stats["events_processed"] += 1
                self.stats["queue_size"] = self.event_queue.qsize()

            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception:
                self.logger.exception("Error processing event")

    async def _handle_event(self, event: Event) -> None:
        """Handle a single event."""
        try:
            with LoggingContext(
                "event_handle",
                event_type=event.event_type,
                event_id=event.event_id,
            ):
                # Get handlers for this event type
                handlers = self.handlers.get(event.event_type, [])

                # Also get handlers for wildcard events
                wildcard_handlers = self.handlers.get("*", [])
                all_handlers = handlers + wildcard_handlers

                if not all_handlers:
                    self.logger.debug(
                        "No handlers for event type: %s",
                        event.event_type,
                    )
                    return

                # Process handlers
                tasks = []
                for handler in all_handlers:
                    if handler.can_handle(event):
                        task = asyncio.create_task(
                            self._handle_with_handler(event, handler),
                        )
                        tasks.append(task)

                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)

        except Exception:
            self.logger.exception("Error handling event")

    async def _handle_with_handler(self, event: Event, handler: EventHandler) -> None:
        """Handle event with a specific handler."""
        try:
            await handler.handle(event)
        except Exception:
            self.logger.exception(
                "Handler '%s' failed for event '%s'",
                handler.name,
                event.event_type,
            )

    def get_replay_events(
        self,
        event_type: str | None = None,
        limit: int = 100,
    ) -> list[Event]:
        """Get events from replay buffer.

        Args:
            event_type: Filter by event type
            limit: Maximum number of events to return

        Returns:
            List of events
        """
        events = self.replay_buffer[-limit:] if limit > 0 else self.replay_buffer

        if event_type:
            events = [e for e in events if e.event_type == event_type]

        return events

    def get_stats(self) -> dict[str, Any]:
        """Get event bus statistics."""
        return {
            "running": self.running,
            "queue_size": self.stats["queue_size"],
            "events_processed": self.stats["events_processed"],
            "events_dropped": self.stats["events_dropped"],
            "handlers_registered": self.stats["handlers_registered"],
            "replay_buffer_size": len(self.replay_buffer),
        }


# Global event bus instance
_event_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    """Get the global event bus."""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus


async def emit_event(event: Event) -> None:
    """Emit an event to the global event bus."""
    bus = get_event_bus()
    await bus.emit(event)


async def emit_peer_connected(
    peer_ip: str,
    peer_port: int,
    peer_id: str | None = None,
) -> None:
    """Emit peer connected event."""
    event = PeerConnectedEvent(
        event_type=EventType.PEER_CONNECTED.value,
        peer_ip=peer_ip,
        peer_port=peer_port,
        peer_id=peer_id,
    )
    await emit_event(event)


async def emit_peer_disconnected(
    peer_ip: str,
    peer_port: int,
    reason: str | None = None,
) -> None:
    """Emit peer disconnected event."""
    event = PeerDisconnectedEvent(
        event_type=EventType.PEER_DISCONNECTED.value,
        peer_ip=peer_ip,
        peer_port=peer_port,
        reason=reason,
    )
    await emit_event(event)


async def emit_piece_downloaded(
    piece_index: int,
    piece_size: int,
    download_time: float,
    peer_ip: str | None = None,
) -> None:
    """Emit piece downloaded event."""
    event = PieceDownloadedEvent(
        event_type=EventType.PIECE_DOWNLOADED.value,
        piece_index=piece_index,
        piece_size=piece_size,
        download_time=download_time,
        peer_ip=peer_ip,
    )
    await emit_event(event)


async def emit_torrent_completed(
    torrent_name: str,
    total_size: int,
    download_time: float,
    average_speed: float,
) -> None:
    """Emit torrent completed event."""
    event = TorrentCompletedEvent(
        event_type=EventType.TORRENT_COMPLETED.value,
        torrent_name=torrent_name,
        total_size=total_size,
        download_time=download_time,
        average_speed=average_speed,
    )
    await emit_event(event)


async def emit_performance_metric(
    metric_name: str,
    metric_value: float,
    metric_unit: str,
    tags: dict[str, str] | None = None,
) -> None:
    """Emit performance metric event."""
    event = PerformanceMetricEvent(
        event_type=EventType.PERFORMANCE_METRIC.value,
        metric_name=metric_name,
        metric_value=metric_value,
        metric_unit=metric_unit,
        tags=tags or {},
    )
    await emit_event(event)
