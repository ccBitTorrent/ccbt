"""Reactive data update system for the tabbed interface.

Provides event-driven updates with WebSocket integration, debouncing, and priority queues.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from enum import IntEnum
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from ccbt.interface.data_provider import DataProvider
else:
    try:
        from ccbt.interface.data_provider import DataProvider
    except ImportError:
        DataProvider = None  # type: ignore[assignment, misc]

logger = logging.getLogger(__name__)


class UpdatePriority(IntEnum):
    """Priority levels for data updates."""

    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


class UpdateEvent:
    """Represents a data update event."""

    def __init__(
        self,
        event_type: str,
        data: dict[str, Any],
        priority: UpdatePriority = UpdatePriority.NORMAL,
        timestamp: float | None = None,
    ) -> None:
        """Initialize update event.

        Args:
            event_type: Type of event (e.g., "torrent_status_changed", "global_stats_updated")
            data: Event data dictionary
            priority: Update priority level
            timestamp: Event timestamp (defaults to current time)
        """
        self.event_type = event_type
        self.data = data
        self.priority = priority
        self.timestamp = timestamp or time.time()


class ReactiveUpdateManager:
    """Manages reactive data updates with debouncing and priority queues."""

    def __init__(
        self,
        data_provider: DataProvider,
        debounce_interval: float = 0.05,  # Reduced from 0.1s to 0.05s for tighter updates
        max_queue_size: int = 1000,
    ) -> None:
        """Initialize reactive update manager.

        Args:
            data_provider: DataProvider instance
            debounce_interval: Minimum time between updates (seconds)
            max_queue_size: Maximum size of update queue
        """
        self._data_provider = data_provider
        self._debounce_interval = debounce_interval
        self._max_queue_size = max_queue_size
        
        # Priority queues (one per priority level)
        self._queues: dict[UpdatePriority, deque[UpdateEvent]] = {
            priority: deque() for priority in UpdatePriority
        }
        
        # Subscribers: event_type -> list of callbacks
        self._subscribers: dict[str, list[Callable[[UpdateEvent], None]]] = {}
        
        # Debounce timers: event_type -> last update time
        self._last_update_times: dict[str, float] = {}
        
        # Processing task
        self._processing_task: asyncio.Task | None = None
        self._running = False
        
        # Lock for thread safety
        self._lock = asyncio.Lock()

        # Default subscribers to keep DataProvider caches coherent
        def _invalidate_global(event: UpdateEvent) -> None:
            try:
                from ccbt.daemon.ipc_protocol import EventType
                if hasattr(self._data_provider, "invalidate_on_event"):
                    self._data_provider.invalidate_on_event(EventType.GLOBAL_STATS_UPDATED)
            except ImportError:
                pass

        def _invalidate_torrent(event: UpdateEvent) -> None:
            try:
                from ccbt.daemon.ipc_protocol import EventType
                if hasattr(self._data_provider, "invalidate_on_event"):
                    info_hash = event.data.get("info_hash")
                    self._data_provider.invalidate_on_event(
                        EventType.TORRENT_STATUS_CHANGED,
                        info_hash,
                    )
            except ImportError:
                pass

        def _invalidate_tracker(event: UpdateEvent) -> None:
            try:
                from ccbt.daemon.ipc_protocol import EventType
                if hasattr(self._data_provider, "invalidate_on_event"):
                    info_hash = event.data.get("info_hash")
                    self._data_provider.invalidate_on_event(
                        EventType.TRACKER_ANNOUNCE_SUCCESS,
                        info_hash,
                    )
            except ImportError:
                pass

        def _invalidate_metadata(event: UpdateEvent) -> None:
            try:
                from ccbt.daemon.ipc_protocol import EventType
                if hasattr(self._data_provider, "invalidate_on_event"):
                    info_hash = event.data.get("info_hash")
                    self._data_provider.invalidate_on_event(
                        EventType.METADATA_FETCH_COMPLETED,
                        info_hash,
                    )
            except ImportError:
                pass

        self.subscribe("global_stats_updated", _invalidate_global)
        self.subscribe("torrent_delta", _invalidate_torrent)
        self.subscribe("tracker_event", _invalidate_tracker)
        self.subscribe("metadata_event", _invalidate_metadata)

    async def start(self) -> None:  # pragma: no cover
        """Start the reactive update manager."""
        if self._running:
            return
        
        self._running = True
        self._processing_task = asyncio.create_task(self._process_updates())
        logger.debug("Reactive update manager started")

    async def stop(self) -> None:  # pragma: no cover
        """Stop the reactive update manager."""
        self._running = False
        if self._processing_task:
            self._processing_task.cancel()
            try:
                await self._processing_task
            except asyncio.CancelledError:
                pass
        logger.debug("Reactive update manager stopped")

    def subscribe(
        self, event_type: str, callback: Callable[[UpdateEvent], None]
    ) -> None:  # pragma: no cover
        """Subscribe to an event type.

        Args:
            event_type: Type of event to subscribe to
            callback: Callback function to call when event occurs
        """
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)

    def unsubscribe(
        self, event_type: str, callback: Callable[[UpdateEvent], None]
    ) -> None:  # pragma: no cover
        """Unsubscribe from an event type.

        Args:
            event_type: Type of event to unsubscribe from
            callback: Callback function to remove
        """
        if event_type in self._subscribers:
            try:
                self._subscribers[event_type].remove(callback)
            except ValueError:
                pass

    async def emit(
        self,
        event_type: str,
        data: dict[str, Any],
        priority: UpdatePriority = UpdatePriority.NORMAL,
    ) -> None:  # pragma: no cover
        """Emit an update event.

        Args:
            event_type: Type of event
            data: Event data
            priority: Update priority
        """
        async with self._lock:
            # Check debounce
            now = time.time()
            last_update = self._last_update_times.get(event_type, 0)
            if now - last_update < self._debounce_interval:
                # Debounce: update existing event in queue if present
                # Find and update existing event of same type
                for queue in self._queues.values():
                    for event in queue:
                        if event.event_type == event_type:
                            # Update existing event
                            event.data.update(data)
                            event.timestamp = now
                            return
                # If not found, will add new event below
            
            # Check queue size
            total_size = sum(len(q) for q in self._queues.values())
            if total_size >= self._max_queue_size:
                # Remove oldest low-priority event
                if self._queues[UpdatePriority.LOW]:
                    self._queues[UpdatePriority.LOW].popleft()
                else:
                    logger.warning("Update queue full, dropping event")
                    return
            
            # Add new event
            event = UpdateEvent(event_type, data, priority, now)
            self._queues[priority].append(event)
            self._last_update_times[event_type] = now

    async def _process_updates(self) -> None:  # pragma: no cover
        """Process update events from priority queues."""
        while self._running:
            try:
                # Process events in priority order (CRITICAL -> HIGH -> NORMAL -> LOW)
                event: UpdateEvent | None = None
                
                for priority in [
                    UpdatePriority.CRITICAL,
                    UpdatePriority.HIGH,
                    UpdatePriority.NORMAL,
                    UpdatePriority.LOW,
                ]:
                    if self._queues[priority]:
                        event = self._queues[priority].popleft()
                        break
                
                if event:
                    # Notify subscribers
                    callbacks = self._subscribers.get(event.event_type, [])
                    for callback in callbacks:
                        try:
                            # Call callback (may be sync or async)
                            if asyncio.iscoroutinefunction(callback):
                                await callback(event)
                            else:
                                callback(event)
                        except Exception as e:
                            logger.debug("Error in update callback: %s", e)
                else:
                    # No events, sleep briefly
                    await asyncio.sleep(0.01)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug("Error processing updates: %s", e)
                await asyncio.sleep(0.1)

    async def setup_websocket_subscriptions(
        self, session: Any
    ) -> None:  # pragma: no cover
        """Set up WebSocket subscriptions for real-time updates.

        Args:
            session: Session manager (AsyncSessionManager or DaemonInterfaceAdapter)
        """
        from ccbt.interface.daemon_session_adapter import DaemonInterfaceAdapter
        from ccbt.daemon.ipc_protocol import EventType

        if isinstance(session, DaemonInterfaceAdapter):
            # Set up WebSocket event callbacks
            def on_torrent_status_changed(data: dict[str, Any]) -> None:
                """Handle torrent status change from WebSocket."""
                asyncio.create_task(
                    self.emit(
                        "torrent_status_changed",
                        data,
                        UpdatePriority.HIGH,
                    )
                )

            def on_torrent_added(data: dict[str, Any]) -> None:
                """Handle torrent added event."""
                asyncio.create_task(
                    self.emit("torrent_added", data, UpdatePriority.HIGH)
                )

            def on_torrent_removed(data: dict[str, Any]) -> None:
                """Handle torrent removed event."""
                asyncio.create_task(
                    self.emit("torrent_removed", data, UpdatePriority.HIGH)
                )

            def on_torrent_completed(data: dict[str, Any]) -> None:
                """Handle torrent completed event."""
                asyncio.create_task(
                    self.emit("torrent_completed", data, UpdatePriority.CRITICAL)
                )

            # Register callbacks if session supports it
            if hasattr(session, "register_event_callback"):
                session.register_event_callback(  # type: ignore[attr-defined]
                    EventType.TORRENT_STATUS_CHANGED, on_torrent_status_changed
                )
                session.register_event_callback(  # type: ignore[attr-defined]
                    EventType.TORRENT_ADDED, on_torrent_added
                )
                session.register_event_callback(  # type: ignore[attr-defined]
                    EventType.TORRENT_REMOVED, on_torrent_removed
                )
                session.register_event_callback(  # type: ignore[attr-defined]
                    EventType.TORRENT_COMPLETED, on_torrent_completed
                )
                logger.debug("WebSocket subscriptions set up for reactive updates")
        else:
            # For local session, we'd need to poll or use internal events
            # This is a placeholder for future enhancement
            logger.debug("Local session - WebSocket subscriptions not available")

    def subscribe_to_adapter(self, adapter: Any) -> None:
        """Bind daemon adapter callbacks to reactive update events."""
        if not adapter:
            return

        async def _handle_global_stats(payload: dict[str, Any]) -> None:
            await self.emit("global_stats_updated", payload, UpdatePriority.NORMAL)

        async def _handle_torrent_delta(payload: dict[str, Any]) -> None:
            await self.emit("torrent_delta", payload, UpdatePriority.HIGH)

        async def _handle_peer_metrics(payload: dict[str, Any]) -> None:
            await self.emit("peer_metrics", payload, UpdatePriority.NORMAL)

        async def _handle_tracker_event(payload: dict[str, Any]) -> None:
            await self.emit("tracker_event", payload, UpdatePriority.NORMAL)

        async def _handle_metadata_event(payload: dict[str, Any]) -> None:
            await self.emit("metadata_event", payload, UpdatePriority.NORMAL)

        adapter.on_global_stats = _handle_global_stats
        adapter.on_torrent_list_delta = _handle_torrent_delta
        adapter.on_peer_metrics = _handle_peer_metrics
        adapter.on_tracker_event = _handle_tracker_event
        adapter.on_metadata_event = _handle_metadata_event





















