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

from ccbt.utils.exceptions import CCBTError
from ccbt.utils.logging_config import LoggingContext, get_logger


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
    EXTENSION_STARTED = "extension_started"
    EXTENSION_STOPPED = "extension_stopped"

    # SSL Extension events
    SSL_NEGOTIATION = "ssl_negotiation"

    # Xet Extension events
    XET_CHUNK_REQUESTED = "xet_chunk_requested"
    XET_CHUNK_RECEIVED = "xet_chunk_received"
    XET_CHUNK_PROVIDED = "xet_chunk_provided"
    XET_CHUNK_NOT_FOUND = "xet_chunk_not_found"
    XET_CHUNK_ERROR = "xet_chunk_error"

    # XET Folder Sync events
    FOLDER_CHANGED = "folder_changed"
    FOLDER_SYNC_CHECK = "folder_sync_check"
    FOLDER_SYNC_STARTED = "folder_sync_started"
    FOLDER_SYNC_COMPLETED = "folder_sync_completed"
    FOLDER_SYNC_ERROR = "folder_sync_error"

    # PEX events
    PEER_DISCOVERED = "peer_discovered"
    PEER_DROPPED = "peer_dropped"

    # DHT events
    DHT_NODE_ADDED = "dht_node_added"
    DHT_NODE_REMOVED = "dht_node_removed"
    DHT_ERROR = "dht_error"
    DHT_AGGRESSIVE_MODE_ENABLED = "dht_aggressive_mode_enabled"
    DHT_AGGRESSIVE_MODE_DISABLED = "dht_aggressive_mode_disabled"
    DHT_ITERATIVE_LOOKUP_COMPLETE = "dht_iterative_lookup_complete"
    
    # IMPROVEMENT: Peer quality events
    PEER_QUALITY_RANKED = "peer_quality_ranked"
    CONNECTION_POOL_QUALITY_CLEANUP = "connection_pool_quality_cleanup"
    PEER_CHOKING_OPTIMIZED = "peer_choking_optimized"

    # WebSeed events
    WEBSEED_ADDED = "webseed_added"
    WEBSEED_REMOVED = "webseed_removed"
    WEBSEED_DOWNLOAD_SUCCESS = "webseed_download_success"
    WEBSEED_DOWNLOAD_FAILED = "webseed_download_failed"
    WEBSEED_ERROR = "webseed_error"

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
    MONITORING_HEARTBEAT = "monitoring_heartbeat"

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

    def __init__(
        self,
        max_queue_size: int = 10000,
        batch_size: int = 50,
        batch_timeout: float = 0.05,
        emit_timeout: float = 0.01,
        queue_full_threshold: float = 0.9,
        throttle_intervals: dict[str, float] | None = None,
    ):
        """Initialize event bus.

        Args:
            max_queue_size: Maximum size of event queue
            batch_size: Maximum number of events to process per batch
            batch_timeout: Timeout in seconds to wait when collecting a batch
            emit_timeout: Timeout in seconds when trying to emit to a full queue
            queue_full_threshold: Queue fullness threshold (0.0-1.0) for dropping low-priority events
            throttle_intervals: Dictionary mapping event types to throttle intervals in seconds.
                If None, uses default throttling intervals.

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

        # Batch processing configuration
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
        self.emit_timeout = emit_timeout
        self.queue_full_threshold = queue_full_threshold

        self._throttle_times: dict[str, float] = {}
        if throttle_intervals is not None:
            self._throttle_intervals: dict[str, float] = throttle_intervals
        else:
            self._throttle_intervals: dict[str, float] = {
                "dht_node_found": 0.1,  
                "dht_node_added": 0.1,  
                "monitoring_heartbeat": 1.0,  
                "global_metrics_update": 0.5, 
            }

        # Statistics
        self.stats = {
            "events_processed": 0,
            "events_dropped": 0,
            "handlers_registered": 0,
            "queue_size": 0,
            "events_throttled": 0,
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
            except ValueError:  # pragma: no cover
                # Defensive: Handler already removed or never registered
                pass

    async def emit(self, event: Event) -> None:
        """Emit an event.

        Args:
            event: Event to emit

        """
        try:
            # Throttle high-frequency events
            if event.event_type in self._throttle_intervals:
                now = time.time()
                last_emit = self._throttle_times.get(event.event_type, 0)
                interval = self._throttle_intervals[event.event_type]
                if now - last_emit < interval:
                    self.stats["events_throttled"] += 1
                    return  # Drop throttled event
                self._throttle_times[event.event_type] = now

            # Add to replay buffer
            self.replay_buffer.append(event)
            if len(self.replay_buffer) > self.max_replay_events:
                self.replay_buffer.pop(0)

            # If we somehow switched loops between start/emit, rebind queue lazily
            if self._loop is None:
                try:
                    self._loop = asyncio.get_running_loop()
                except RuntimeError:  # pragma: no cover
                    # Edge case: No running loop, get event loop instead
                    self._loop = asyncio.get_event_loop()
            try:
                current_loop = asyncio.get_running_loop()
            except RuntimeError:  # pragma: no cover
                # Fallback to event loop for compatibility
                current_loop = asyncio.get_event_loop()
            if self._loop is not current_loop:  # pragma: no cover
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

            # Try non-blocking put first
            try:
                self.event_queue.put_nowait(event)
                self.stats["queue_size"] = self.event_queue.qsize()
            except asyncio.QueueFull:
                # Queue is full - check if we should drop this event
                # Drop low-priority events when queue is very full
                should_drop = (
                    event.priority.value < EventPriority.NORMAL.value
                    and self.event_queue.qsize() >= self.max_queue_size * self.queue_full_threshold
                )
                
                if should_drop:
                    self.stats["events_dropped"] += 1
                    if event.event_type not in self._throttle_intervals:
                        self.logger.debug(
                            "Event queue full, dropping low-priority event: %s (priority=%s)",
                            event.event_type,
                            event.priority.name,
                        )
                    return
                
                # This gives batch processing a chance to make room
                try:
                    await asyncio.wait_for(
                        self.event_queue.put(event),
                        timeout=self.emit_timeout,
                    )
                    self.stats["queue_size"] = self.event_queue.qsize()
                except asyncio.TimeoutError:
                    self.stats["events_dropped"] += 1
                    if event.event_type not in self._throttle_intervals:
                        self.logger.warning(
                            "Event queue full, dropping event: %s (priority=%s)",
                            event.event_type,
                            event.priority.name,
                        )

        except Exception:
            self.logger.exception("Failed to emit event")


    async def start(self) -> None:
        """Start the event bus."""
        if self.running:
            return

        # Rebind to the current running loop and recreate the queue if needed
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:  # pragma: no cover
            # Edge case: No running loop detected at start
            # Fallback to event loop for compatibility
            current_loop = asyncio.get_event_loop()

        if self._loop is not current_loop:
            # Cancel any previous processing task bound to another loop
            if self._task is not None and not self._task.done():
                with contextlib.suppress(Exception):  # pragma: no cover
                    # Defensive: Suppress exceptions during task cancellation
                    # Task may already be cancelled or done, which is fine
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
        """Process events from the queue with batch processing."""
        while self.running:
            try:
                # Collect a batch of events for parallel processing
                batch: list[Event] = []

                # Get first event (blocking with timeout)
                try:
                    first_event = await asyncio.wait_for(
                        self.event_queue.get(),
                        timeout=self.batch_timeout,
                    )
                    batch.append(first_event)
                except asyncio.TimeoutError:
                    # No events available, continue to next iteration
                    continue

                # Collect additional events up to batch_size (non-blocking)
                while len(batch) < self.batch_size:
                    try:
                        event = self.event_queue.get_nowait()
                        batch.append(event)
                    except asyncio.QueueEmpty:
                        break

                # Process batch in parallel
                if batch:
                    tasks = [self._handle_event(event) for event in batch]
                    await asyncio.gather(*tasks, return_exceptions=True)
                    self.stats["events_processed"] += len(batch)
                    self.stats["queue_size"] = self.event_queue.qsize()

            except asyncio.CancelledError:
                break
            except Exception:
                self.logger.exception("Error processing event batch")

    async def _handle_event(self, event: Event) -> None:
        """Handle a single event."""
        start_time = time.time()
        try:
            # Get handlers for this event type
            handlers = self.handlers.get(event.event_type, [])

            # Also get handlers for wildcard events
            wildcard_handlers = self.handlers.get("*", [])
            all_handlers = handlers + wildcard_handlers

            if not all_handlers:
                # Only log at DEBUG for unhandled events to reduce noise
                self.logger.debug(
                    "No handlers registered for event: %s (id=%s)",
                    event.event_type,
                    event.event_id[:8] if event.event_id else "unknown",
                )
                return

            # Filter handlers that can actually handle this event
            processable_handlers = [h for h in all_handlers if h.can_handle(event)]
            
            if not processable_handlers:
                self.logger.debug(
                    "No processable handlers for event: %s (id=%s, registered=%d)",
                    event.event_type,
                    event.event_id[:8] if event.event_id else "unknown",
                    len(all_handlers),
                )
                return

            # Process handlers
            tasks = []
            for handler in processable_handlers:
                task = asyncio.create_task(
                    self._handle_with_handler(event, handler),
                )
                tasks.append(task)

            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            
            # Only log slow event handling or important events at INFO level
            duration = time.time() - start_time
            important_events = {
                "torrent_completed", "torrent_added", "torrent_removed",
                "system_start", "system_stop", "system_error",
                "peer_connected", "peer_disconnected",
            }
            
            if duration > 0.1 or event.event_type in important_events:
                # Log slow or important events at INFO level
                self.logger.info(
                    "Handled event: %s (id=%s, handlers=%d, duration=%.3fs)",
                    event.event_type,
                    event.event_id[:8] if event.event_id else "unknown",
                    len(processable_handlers),
                    duration,
                )
            else:
                # Fast, routine events at DEBUG level
                self.logger.debug(
                    "Handled event: %s (id=%s, handlers=%d, duration=%.3fs)",
                    event.event_type,
                    event.event_id[:8] if event.event_id else "unknown",
                    len(processable_handlers),
                    duration,
                )

        except Exception:
            duration = time.time() - start_time
            self.logger.exception(
                "Error handling event: %s (id=%s, duration=%.3fs)",
                event.event_type,
                event.event_id[:8] if event.event_id else "unknown",
                duration,
            )

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
            "events_throttled": self.stats["events_throttled"],
            "handlers_registered": self.stats["handlers_registered"],
            "replay_buffer_size": len(self.replay_buffer),
        }


# Global event bus instance
_event_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    """Get the global event bus."""
    global _event_bus
    if _event_bus is None:
        # Try to get config, but don't fail if config isn't initialized yet
        try:
            from ccbt.config.config import get_config
            
            config = get_config()
            obs_config = config.observability
            
            # Build throttle intervals from config
            throttle_intervals = {
                "dht_node_found": obs_config.event_bus_throttle_dht_node_found,
                "dht_node_added": obs_config.event_bus_throttle_dht_node_added,
                "monitoring_heartbeat": obs_config.event_bus_throttle_monitoring_heartbeat,
                "global_metrics_update": obs_config.event_bus_throttle_global_metrics_update,
            }
            
            _event_bus = EventBus(
                max_queue_size=obs_config.event_bus_max_queue_size,
                batch_size=obs_config.event_bus_batch_size,
                batch_timeout=obs_config.event_bus_batch_timeout,
                emit_timeout=obs_config.event_bus_emit_timeout,
                queue_full_threshold=obs_config.event_bus_queue_full_threshold,
                throttle_intervals=throttle_intervals,
            )
        except Exception:
            # Fallback to defaults if config not available
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
