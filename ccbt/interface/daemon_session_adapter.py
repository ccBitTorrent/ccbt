"""Daemon interface adapter for Textual interface.

Provides AsyncSessionManager-like interface that wraps IPCClient for daemon communication.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import sys
from typing import TYPE_CHECKING, Any, Callable, Optional, Union

if TYPE_CHECKING:
    from ccbt.daemon.ipc_client import IPCClient
    from ccbt.daemon.ipc_protocol import EventType, WebSocketEvent

from ccbt.config.config import get_config
from ccbt.daemon.ipc_protocol import EventType
from ccbt.interface.data_provider import (
    _normalize_global_stats_read_model,
    _normalize_torrent_read_model,
)

logger = logging.getLogger(__name__)


class _SnapshotTorrentRef:
    """Minimal ref for a torrent entry from a UI snapshot (used for self.torrents after resync)."""

    __slots__ = ("_data", "info_hash")

    def __init__(self, info_hash_hex: str, data: dict[str, Any]) -> None:
        self.info_hash = info_hash_hex
        self._data = data

    def model_dump(self) -> dict[str, Any]:
        return self._data


WEBSOCKET_EVENT_SUBSCRIPTIONS = (
    EventType.TORRENT_ADDED,
    EventType.TORRENT_REMOVED,
    EventType.TORRENT_COMPLETED,
    EventType.TORRENT_STATUS_CHANGED,
    EventType.METADATA_READY,
    EventType.METADATA_FETCH_STARTED,
    EventType.METADATA_FETCH_PROGRESS,
    EventType.METADATA_FETCH_COMPLETED,
    EventType.METADATA_FETCH_FAILED,
    EventType.FILE_SELECTION_CHANGED,
    EventType.FILE_PRIORITY_CHANGED,
    EventType.PEER_CONNECTED,
    EventType.PEER_DISCONNECTED,
    EventType.PEER_HANDSHAKE_COMPLETE,
    EventType.PEER_BITFIELD_RECEIVED,
    EventType.SEEDING_STARTED,
    EventType.SEEDING_STOPPED,
    EventType.SEEDING_STATS_UPDATED,
    EventType.GLOBAL_STATS_UPDATED,
    EventType.TRACKER_ANNOUNCE_STARTED,
    EventType.TRACKER_ANNOUNCE_SUCCESS,
    EventType.TRACKER_ANNOUNCE_ERROR,
    EventType.PIECE_REQUESTED,
    EventType.PIECE_DOWNLOADED,
    EventType.PIECE_VERIFIED,
    EventType.PIECE_COMPLETED,
    EventType.PROGRESS_UPDATED,
    EventType.MEDIA_STREAM_STARTED,
    EventType.MEDIA_STREAM_BUFFERING,
    EventType.MEDIA_STREAM_READY,
    EventType.MEDIA_STREAM_STOPPED,
    EventType.MEDIA_STREAM_ERROR,
    EventType.XET_FOLDER_ADDED,
    EventType.XET_FOLDER_REMOVED,
    EventType.XET_FOLDER_CHANGED,
    EventType.XET_SYNC_PROGRESS,
    EventType.XET_SYNC_ERROR,
    EventType.XET_METADATA_READY,
)


class DaemonInterfaceAdapter:
    """Adapter that makes IPCClient look like AsyncSessionManager.

    This adapter provides the same interface as AsyncSessionManager but routes
    all operations through the daemon IPC interface. It also manages WebSocket
    subscriptions for real-time updates.
    """

    def __init__(self, ipc_client: IPCClient):
        """Initialize daemon interface adapter.

        Args:
            ipc_client: IPC client instance for daemon communication
        """
        self._client = ipc_client
        self.config = get_config()
        self.output_dir = "."

        # CRITICAL: Use executor pattern for all command-based operations
        # This ensures consistency with CLI and proper routing through ExecutorManager
        from ccbt.executor.manager import ExecutorManager
        executor_manager = ExecutorManager.get_instance()
        self._executor = executor_manager.get_executor(ipc_client=ipc_client)
        self._executor_adapter = self._executor.adapter  # Get the DaemonSessionAdapter

        # Cached state for performance
        self._cached_status: dict[str, Any] = {}
        self._cached_torrents: dict[str, dict[str, Any]] = {}
        self._cache_lock = asyncio.Lock()
        # Event-driven caches (used by _handle_websocket_event)
        self._torrent_status_cache: dict[str, Any] = {}
        self._torrent_files_cache: dict[str, Any] = {}
        self._torrent_peers_cache: dict[str, Any] = {}
        self._torrent_trackers_cache: dict[str, Any] = {}
        self._media_status_cache: dict[str, Any] = {}
        self._global_stats_cache: Optional[dict[str, Any]] = None

        # WebSocket subscription
        self._websocket_task: Optional[asyncio.Task] = None
        self._peers_update_task: Optional[asyncio.Task] = None
        self._event_callbacks: dict[EventType, list[Callable[[dict[str, Any]], None]]] = {}
        self._websocket_connected = False
        # CRITICAL: Track the event loop that start() bound the WebSocket tasks to.
        # If a previous start() ran on a throwaway asyncio.run() loop that has since
        # closed (e.g. the old CLI launch path), _ensure_adapter_ready must detect
        # this and restart the adapter on the current (Textual) loop. Without this
        # check, _websocket_connected stays True while the tasks are dead, and the
        # UI silently fails to bind to live data ("Event loop is closed" swallowed).
        self._start_loop: Optional[asyncio.AbstractEventLoop] = None

        # Widget event callbacks - widgets that want to receive real-time updates
        self._widget_callbacks: list[Any] = []  # List of widget instances with event handler methods

        # List-based adapter listeners (R4 fix). The legacy single-slot `on_*`
        # callbacks below are kept for backward compatibility with direct
        # assignment, but ReactiveUpdateManager.subscribe_to_adapter() and any
        # other multi-consumer must register via add_adapter_listener() so that
        # multiple subscribers can coexist without overwriting each other. The
        # _handle_websocket_event dispatcher invokes BOTH the single-slot and
        # every list listener, so direct assignment continues to work and list
        # subscribers are additive.
        self._adapter_listeners: dict[str, list[Callable[..., Any]]] = {}

        # Callbacks (matching AsyncSessionManager interface)
        self.on_torrent_added: Optional[Callable[[bytes, str], None]] = None
        self.on_torrent_removed: Optional[Callable[[bytes], None]] = None
        self.on_torrent_complete: Optional[Callable[[bytes, str], None]] = None
        # New async hooks for WebSocket-driven UI updates
        self.on_global_stats: Optional[Callable[[dict[str, Any]], None]] = None
        self.on_torrent_list_delta: Optional[Callable[[dict[str, Any]], None]] = None
        self.on_peer_metrics: Optional[Callable[[dict[str, Any]], None]] = None
        self.on_tracker_event: Optional[Callable[[dict[str, Any]], None]] = None
        self.on_metadata_event: Optional[Callable[[dict[str, Any]], None]] = None
        self.on_media_event: Optional[Callable[[dict[str, Any]], None]] = None
        # XET folder callbacks
        self.on_xet_folder_added: Optional[Callable[[str, str], None]] = None
        self.on_xet_folder_removed: Optional[Callable[[str], None]] = None
        self.on_xet_event: Optional[Callable[[dict[str, Any]], None]] = None

        # Properties matching AsyncSessionManager
        self.torrents: dict[bytes, Any] = {}  # Will be populated from cached status
        self.xet_folders: dict[str, Any] = {}  # Will be populated from cached status
        self.lock = asyncio.Lock()  # Compatibility with AsyncSessionManager
        self.dht_client: Optional[Any] = None  # Not available via IPC
        self.metrics: Optional[Any] = None  # Not directly available
        self.peer_service: Optional[Any] = None  # Not directly available
        self.security_manager: Optional[Any] = None  # Not directly available
        self.nat_manager: Optional[Any] = None  # Not directly available
        self.tcp_server: Optional[Any] = None  # Not directly available

        self.logger = logger

    @staticmethod
    def _subscription_events() -> list[EventType]:
        """Return the full websocket subscription set."""
        return list(WEBSOCKET_EVENT_SUBSCRIPTIONS)

    def add_adapter_listener(
        self, name: str, callback: Callable[..., Any]
    ) -> None:
        """Register an additional listener for an adapter callback slot.

        R4 fix: the adapter's ``on_*`` attributes (on_global_stats,
        on_torrent_list_delta, ...) are single-slot — direct assignment
        overwrites any prior consumer. ReactiveUpdateManager and any other
        multi-consumer must register through this method so multiple
        subscribers coexist without race. The dispatcher invokes every list
        listener in addition to the legacy single-slot value.

        Args:
            name: Adapter callback slot name (e.g. "on_global_stats",
                "on_torrent_added", "on_torrent_list_delta").
            callback: Callback to append. Must match the slot's signature
                (dict for the ``on_*_event``/``on_global_stats``/
                ``on_torrent_list_delta`` slots; ``(bytes, str)`` for
                ``on_torrent_added``/``on_torrent_complete``; ``(bytes,)`` for
                ``on_torrent_removed``; ``(str, str)`` for
                ``on_xet_folder_added``; ``(str,)`` for
                ``on_xet_folder_removed``).
        """
        self._adapter_listeners.setdefault(name, []).append(callback)

    def remove_adapter_listener(
        self, name: str, callback: Callable[..., Any]
    ) -> None:
        """Remove a previously-registered list listener.

        Args:
            name: Adapter callback slot name.
            callback: Callback to remove (no-op if not registered).
        """
        listeners = self._adapter_listeners.get(name)
        if not listeners:
            return
        try:
            listeners.remove(callback)
        except ValueError:
            pass

    async def _dispatch_listeners(self, name: str, *args: Any) -> None:
        """Invoke every list listener registered for ``name``.

        Awaits coroutine return values. Errors in one listener do not stop the
        others (matches the resilience of the legacy ``_dispatch`` helper).
        """
        listeners = self._adapter_listeners.get(name)
        if not listeners:
            return
        for callback in list(listeners):
            try:
                result = callback(*args)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as cb_error:
                self.logger.debug(
                    "Error in adapter listener %s: %s",
                    getattr(callback, "__name__", "?"),
                    cb_error,
                )

    def _is_started_on_current_loop(self) -> bool:
        """Return True if start() previously bound WebSocket tasks to the running loop.

        Guards against the dead-loop trap: if start() ran on a throwaway
        asyncio.run() loop that has since closed, _websocket_connected stays True
        but the tasks are gone. Callers (_ensure_adapter_ready) use this to decide
        whether to restart the adapter on the current loop.
        """
        if self._start_loop is None:
            return False
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            return False
        if self._start_loop is not current_loop:
            return False
        if self._start_loop.is_closed():
            return False
        # Tasks must still be alive (or not yet created if WS connect failed)
        if self._websocket_task is not None and self._websocket_task.done():
            return False
        return True

    async def _take_over_websocket_receive(self) -> None:
        """Cancel IPCClient's internal WebSocket receive loop and take it over.

        connect_websocket() spawns IPCClient._websocket_receive_loop() as
        IPCClient._websocket_task. The adapter runs its own _websocket_event_loop()
        to batch/dispatch events, so two concurrent ``receive()`` calls would race
        on the same aiohttp WebSocket ("Concurrent call to receive() is not
        allowed"). This helper cancels the IPC client's task and waits for it to
        settle before the adapter subscribes / starts its own loop.

        Used by both the initial start() and the reconnect path in
        _websocket_event_loop().
        """
        client_task = getattr(self._client, "_websocket_task", None)
        if client_task and not client_task.done():
            client_task.cancel()
            try:
                await asyncio.wait_for(client_task, timeout=0.5)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                # Cancellation completed or timed out - either way, task is cancelled
                pass
            except Exception:
                # Any other exception - task is likely cancelled anyway
                pass
            finally:
                self._client._websocket_task = None  # type: ignore[attr-defined]
        # Small delay so the async-for loop fully releases the WebSocket receiver
        # before we subscribe / start our own loop. Prevents a receive() race.
        await asyncio.sleep(0.1)

    async def start(self) -> None:
        """Connect to daemon and start WebSocket subscription.

        Loop-aware: if a previous start() bound tasks to a different (now likely
        closed) loop, stop those stale resources first, then re-bind to the
        current running loop. This makes the adapter safe to call from
        _ensure_adapter_ready() inside Textual's on_mount even if the CLI launch
        path accidentally invoked start() on a throwaway asyncio.run() loop.
        """
        # If we are already started on this very loop, do not double-connect.
        if self._is_started_on_current_loop():
            self.logger.debug("Daemon interface adapter already started on this loop, skipping")
            return

        # If started on a stale/different loop, tear down those resources first.
        if self._start_loop is not None or self._websocket_task is not None or self._peers_update_task is not None:
            self.logger.info(
                "Restarting daemon interface adapter on a new event loop (previous loop=%s, closed=%s)",
                self._start_loop,
                self._start_loop.is_closed() if self._start_loop is not None else "n/a",
            )
            with contextlib.suppress(Exception):
                await self.stop()

        max_retries = 3
        retry_delay = 1.0
        use_websocket = (
            sys.platform != "win32"
            or os.environ.get("CCBT_DASHBOARD_WEBSOCKET", "").lower()
            in ("1", "true", "yes")
        )

        for attempt in range(max_retries):
            try:
                # Verify connection
                if not await self._client.is_daemon_running():
                    if attempt < max_retries - 1:
                        self.logger.warning(
                            "Daemon is not running or not accessible (attempt %d/%d), retrying...",
                            attempt + 1,
                            max_retries,
                        )
                        await asyncio.sleep(retry_delay)
                        continue
                    message = (
                        f"Daemon is not running or not accessible after {max_retries} attempts"
                    )
                    raise RuntimeError(message)

                if not use_websocket:
                    self.logger.info(
                        "Using HTTP polling for dashboard updates on Windows "
                        "(set CCBT_DASHBOARD_WEBSOCKET=1 to enable WebSocket)"
                    )
                    # Hydration is handled by the dashboard poll loop; avoid a
                    # blocking list+stats IPC round-trip during Textual mount.
                    self._start_loop = asyncio.get_running_loop()
                    self.logger.info("Daemon interface adapter started (polling mode)")
                    return

                # Connect WebSocket for real-time updates
                if await self._client.connect_websocket():
                    self._websocket_connected = True

                    # CRITICAL: Cancel IPC client's receive loop - we'll use our own.
                    # This prevents "Concurrent call to receive() is not allowed" error.
                    # The IPC client starts _websocket_receive_loop() in connect_websocket(),
                    # but we need to use our own _websocket_event_loop() for proper event
                    # handling. Same logic is reused by the reconnect path.
                    await self._take_over_websocket_receive()

                    # Subscribe to relevant events
                    await self._client.subscribe_events(self._subscription_events())
                    # Snapshot resync so caches match daemon state (no silent drift after connect)
                    await self._resync_from_snapshot()
                    # Mapping reference for UI planning:
                    #   GLOBAL_STATS_UPDATED   -> dashboard overview/speeds.
                    #   TORRENT_* events       -> torrents table + selectors.
                    #   PEER_* / SEEDING_*     -> per-peer/per-torrent panels.
                    #   TRACKER_*              -> tracker widgets.
                    #   PIECE_* / PROGRESS_*   -> graph widgets & piece metrics.

                    # Start event receive loop (our own, not IPC client's)
                    self._websocket_task = asyncio.create_task(self._websocket_event_loop())

                    # Start background task to update peers cache periodically
                    self._peers_update_task = asyncio.create_task(self._peers_update_loop())

                    # Record the loop we bound to so _is_started_on_current_loop()
                    # can detect a future dead-loop situation.
                    self._start_loop = asyncio.get_running_loop()

                    self.logger.info("WebSocket connected and subscribed to events")
                else:
                    self.logger.warning("Failed to connect WebSocket, will use polling only")

                # Initial status fetch (if WebSocket failed we still need cache)
                if not self._websocket_connected:
                    await self._refresh_cache()
                else:
                    # Even on success, record the loop so restart detection works.
                    self._start_loop = asyncio.get_running_loop()

                self.logger.info("Daemon interface adapter started")
                return

            except Exception as e:
                if attempt < max_retries - 1:
                    self.logger.warning(
                        "Failed to start daemon interface adapter (attempt %d/%d): %s, retrying...",
                        attempt + 1,
                        max_retries,
                        e
                    )
                    await asyncio.sleep(retry_delay)
                    retry_delay = min(retry_delay * 2.0, 5.0)  # Exponential backoff
                else:
                    self.logger.exception("Failed to start daemon interface adapter after %d attempts", max_retries)
                    raise

    async def stop(self) -> None:
        """Close IPC connection and cleanup."""
        # Stop WebSocket task
        if self._websocket_task:
            self._websocket_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._websocket_task
            self._websocket_task = None

        # Stop peers update task
        if self._peers_update_task:
            self._peers_update_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._peers_update_task
            self._peers_update_task = None

        # Close WebSocket
        if self._websocket_connected:
            await self._client._close_websocket()
            self._websocket_connected = False

        # Close HTTP session
        await self._client.close()

        # Clear cache
        async with self._cache_lock:
            self._cached_status.clear()
            self._cached_torrents.clear()
            self.torrents.clear()

        self.logger.info("Daemon interface adapter stopped")

    async def _websocket_event_loop(self) -> None:
        """Background task to receive and process WebSocket events."""
        reconnect_delay = 1.0
        max_reconnect_delay = 30.0
        consecutive_failures = 0

        while self._websocket_connected:
            try:
                # Note: Use batch receiving for better efficiency - process multiple events at once
                # This reduces latency and improves throughput for high-frequency events
                events = await self._client.receive_events_batch(timeout=0.3, max_events=20)
                if events:
                    # Process all events in the batch
                    for event in events:
                        await self._handle_websocket_event(event)
                    # Reset failure count on successful events
                    consecutive_failures = 0
                    reconnect_delay = 1.0
                else:
                    # No events received, but connection is still alive - continue
                    pass
            except asyncio.CancelledError:
                break
            except Exception as e:
                consecutive_failures += 1
                self.logger.debug("Error in WebSocket event loop (failure %d): %s", consecutive_failures, e)

                # Try to reconnect with exponential backoff
                await asyncio.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 2.0, max_reconnect_delay)

                if self._websocket_connected:
                    try:
                        # Verify daemon is still running
                        if not await self._client.is_daemon_running():
                            self.logger.warning("Daemon is not running, cannot reconnect WebSocket")
                            self._websocket_connected = False
                            break

                        # Try to reconnect WebSocket
                        if await self._client.connect_websocket():
                            # CRITICAL: cancel the IPC client's freshly-spawned receive loop
                            # before subscribing, exactly as the initial start() does. Without
                            # this, two concurrent receive() calls race on the same WebSocket
                            # ("Concurrent call to receive() is not allowed") and event flow
                            # stops mid-session. Reuses the same helper as start() for parity.
                            await self._take_over_websocket_receive()
                            await self._client.subscribe_events(
                                self._subscription_events(),
                            )
                            await self._resync_from_snapshot()
                            self.logger.info("WebSocket reconnected successfully")
                            consecutive_failures = 0
                            reconnect_delay = 1.0
                        else:
                            self.logger.warning("Failed to reconnect WebSocket, will retry in %.1fs", reconnect_delay)
                    except Exception as reconnect_error:
                        self.logger.warning("Error reconnecting WebSocket: %s", reconnect_error)

                        # If too many consecutive failures, mark as disconnected
                        if consecutive_failures >= 10:
                            self.logger.error("Too many WebSocket reconnection failures, giving up")
                            self._websocket_connected = False
                            break

    async def _handle_websocket_event(self, event: WebSocketEvent) -> None:
        """Handle WebSocket event and update cache."""
        try:
            async def _dispatch(callback: Optional[Callable[..., Any]], *args: Any) -> None:
                """Invoke optional callback, awaiting if it returns coroutine."""
                if not callback:
                    return
                try:
                    result = callback(*args)
                    if asyncio.iscoroutine(result):
                        await result
                except Exception as cb_error:
                    self.logger.debug("Error in adapter callback %s: %s", getattr(callback, "__name__", "?"), cb_error)

            def _event_payload() -> dict[str, Any]:
                """Build a consistent event payload for UI consumers."""
                payload = dict(event.data or {})
                payload.setdefault("event", event.type.value)
                if getattr(event, "raw_type", None):
                    payload["raw_type"] = event.raw_type
                if getattr(event, "event_id", None):
                    payload["event_id"] = event.event_id
                if getattr(event, "source", None):
                    payload["source"] = event.source
                if getattr(event, "priority", None):
                    payload["priority"] = event.priority
                if getattr(event, "correlation_id", None):
                    payload["correlation_id"] = event.correlation_id
                return payload

            if event.type == EventType.TORRENT_ADDED:
                info_hash_hex = event.data.get("info_hash", "")
                name = event.data.get("name", "")
                self.logger.debug(
                    "DaemonInterfaceAdapter: Received TORRENT_ADDED WebSocket event - info_hash: %s, name: %s",
                    info_hash_hex,
                    name,
                )
                if info_hash_hex and self.on_torrent_added:
                    try:
                        info_hash = bytes.fromhex(info_hash_hex)
                        self.logger.debug(
                            "DaemonInterfaceAdapter: Calling on_torrent_added callback for %s",
                            info_hash_hex,
                        )
                        await self.on_torrent_added(info_hash, name)
                        self.logger.debug(
                            "DaemonInterfaceAdapter: on_torrent_added callback completed for %s",
                            info_hash_hex,
                        )
                    except ValueError as e:
                        self.logger.warning(
                            "DaemonInterfaceAdapter: Invalid info_hash hex in TORRENT_ADDED event: %s - %s",
                            info_hash_hex,
                            e,
                        )
                    except Exception as e:
                        self.logger.error(
                            "DaemonInterfaceAdapter: Error in on_torrent_added callback: %s",
                            e,
                            exc_info=True,
                        )
                else:
                    if not info_hash_hex:
                        self.logger.warning(
                            "DaemonInterfaceAdapter: TORRENT_ADDED event missing info_hash"
                        )
                    if not self.on_torrent_added:
                        self.logger.warning(
                            "DaemonInterfaceAdapter: TORRENT_ADDED event received but on_torrent_added callback not set"
                        )
                # R4 fix: also dispatch to list-based listeners (add_adapter_listener).
                # Multiple subscribers (e.g. ReactiveUpdateManager + App auto-select)
                # coexist without overwriting the single-slot on_torrent_added.
                if info_hash_hex:
                    try:
                        info_hash = bytes.fromhex(info_hash_hex)
                        await self._dispatch_listeners("on_torrent_added", info_hash, name)
                    except ValueError:
                        pass
                await self._refresh_cache()

            elif event.type == EventType.TORRENT_REMOVED:
                info_hash_hex = event.data.get("info_hash", "")
                if info_hash_hex and self.on_torrent_removed:
                    try:
                        info_hash = bytes.fromhex(info_hash_hex)
                        await self.on_torrent_removed(info_hash)
                    except ValueError:
                        pass
                if info_hash_hex:
                    try:
                        info_hash = bytes.fromhex(info_hash_hex)
                        await self._dispatch_listeners("on_torrent_removed", info_hash)
                    except ValueError:
                        pass
                await self._refresh_cache()

            elif event.type == EventType.TORRENT_COMPLETED:
                info_hash_hex = event.data.get("info_hash", "")
                name = event.data.get("name", "")
                if info_hash_hex and self.on_torrent_complete:
                    try:
                        info_hash = bytes.fromhex(info_hash_hex)
                        await self.on_torrent_complete(info_hash, name)
                    except ValueError:
                        pass
                if info_hash_hex:
                    try:
                        info_hash = bytes.fromhex(info_hash_hex)
                        await self._dispatch_listeners("on_torrent_complete", info_hash, name)
                    except ValueError:
                        pass
                await self._refresh_cache()

            elif event.type == EventType.TORRENT_STATUS_CHANGED:
                # Update cached status for this torrent
                info_hash_hex = event.data.get("info_hash", "")
                if info_hash_hex:
                    async with self._cache_lock:
                        # Invalidate cached status to force refresh
                        if info_hash_hex in self._torrent_status_cache:
                            del self._torrent_status_cache[info_hash_hex]
                        self._cached_torrents.pop(info_hash_hex, None)
                        self._cached_status.clear()

            elif event.type == EventType.METADATA_READY:
                # Metadata is now available - trigger cache refresh
                info_hash_hex = event.data.get("info_hash", "")
                if info_hash_hex:
                    async with self._cache_lock:
                        # Invalidate cached files to force refresh
                        if info_hash_hex in self._torrent_files_cache:
                            del self._torrent_files_cache[info_hash_hex]
                        self._cached_torrents.pop(info_hash_hex, None)

            elif event.type == EventType.XET_FOLDER_ADDED:
                folder_key = event.data.get("folder_key", "")
                folder_path = event.data.get("folder_path", "")
                if folder_key and self.on_xet_folder_added:
                    await _dispatch(self.on_xet_folder_added, folder_key, folder_path)
                await self._dispatch_listeners("on_xet_folder_added", folder_key, folder_path)
                await self._refresh_xet_folders_cache()
                await _dispatch(self.on_xet_event, _event_payload())
                await self._dispatch_listeners("on_xet_event", _event_payload())

            elif event.type == EventType.XET_FOLDER_REMOVED:
                folder_key = event.data.get("folder_key", "")
                if folder_key and self.on_xet_folder_removed:
                    await _dispatch(self.on_xet_folder_removed, folder_key)
                await self._dispatch_listeners("on_xet_folder_removed", folder_key)
                await self._refresh_xet_folders_cache()
                await _dispatch(self.on_xet_event, _event_payload())
                await self._dispatch_listeners("on_xet_event", _event_payload())

            elif event.type in (
                EventType.XET_FOLDER_CHANGED,
                EventType.XET_SYNC_PROGRESS,
                EventType.XET_SYNC_ERROR,
                EventType.XET_METADATA_READY,
            ):
                await self._refresh_xet_folders_cache()
                await _dispatch(self.on_xet_event, _event_payload())
                await self._dispatch_listeners("on_xet_event", _event_payload())

            elif event.type in (
                EventType.MEDIA_STREAM_STARTED,
                EventType.MEDIA_STREAM_BUFFERING,
                EventType.MEDIA_STREAM_READY,
                EventType.MEDIA_STREAM_STOPPED,
                EventType.MEDIA_STREAM_ERROR,
            ):
                info_hash_hex = event.data.get("info_hash", "")
                stream_id = event.data.get("stream_id", "")
                async with self._cache_lock:
                    if info_hash_hex:
                        self._media_status_cache.pop(info_hash_hex, None)
                        self._torrent_status_cache.pop(info_hash_hex, None)
                    if stream_id:
                        self._media_status_cache.pop(stream_id, None)
                self._notify_widgets_media_event(event.type.value, event.data)
                await _dispatch(self.on_media_event, _event_payload())
                await self._dispatch_listeners("on_media_event", _event_payload())

            elif event.type in [
                EventType.METADATA_FETCH_STARTED,
                EventType.METADATA_FETCH_PROGRESS,
                EventType.METADATA_FETCH_COMPLETED,
                EventType.METADATA_FETCH_FAILED,
            ]:
                # Metadata fetch events - just log for now, could trigger UI updates
                self.logger.debug("Metadata fetch event: %s for %s", event.type, event.data.get("info_hash", ""))
                await _dispatch(self.on_metadata_event, _event_payload())
                await self._dispatch_listeners("on_metadata_event", _event_payload())

            elif event.type in [
                EventType.FILE_SELECTION_CHANGED,
                EventType.FILE_PRIORITY_CHANGED,
            ]:
                # File selection events - invalidate files cache
                info_hash_hex = event.data.get("info_hash", "")
                if info_hash_hex:
                    async with self._cache_lock:
                        if info_hash_hex in self._torrent_files_cache:
                            del self._torrent_files_cache[info_hash_hex]
                        self._cached_torrents.pop(info_hash_hex, None)

            elif event.type in [
                EventType.PEER_CONNECTED,
                EventType.PEER_DISCONNECTED,
                EventType.PEER_HANDSHAKE_COMPLETE,
                EventType.PEER_BITFIELD_RECEIVED,
            ]:
                # Peer events - invalidate peers cache
                info_hash_hex = event.data.get("info_hash", "")
                if info_hash_hex:
                    async with self._cache_lock:
                        if info_hash_hex in self._torrent_peers_cache:
                            del self._torrent_peers_cache[info_hash_hex]
                # Don't refresh immediately - peers update loop will handle it
                self._notify_widgets_peer_event(event.type.value, event.data)
                await _dispatch(self.on_peer_metrics, _event_payload())
                await self._dispatch_listeners("on_peer_metrics", _event_payload())

            elif event.type in [
                EventType.SEEDING_STARTED,
                EventType.SEEDING_STOPPED,
                EventType.SEEDING_STATS_UPDATED,
            ]:
                # Seeding events - update status cache
                info_hash_hex = event.data.get("info_hash", "")
                if info_hash_hex:
                    async with self._cache_lock:
                        if info_hash_hex in self._torrent_status_cache:
                            del self._torrent_status_cache[info_hash_hex]
                        self._cached_torrents.pop(info_hash_hex, None)
                async with self._cache_lock:
                    self._cached_status.clear()

            elif event.type == EventType.GLOBAL_STATS_UPDATED:
                # Global stats updated - invalidate global stats cache
                async with self._cache_lock:
                    self._global_stats_cache = None
                # Notify listeners with fresh metrics payload (if provided)
                await _dispatch(self.on_global_stats, _event_payload())
                await self._dispatch_listeners("on_global_stats", _event_payload())
                # Don't refresh immediately - let polling handle it or trigger specific update

            elif event.type in [
                EventType.TRACKER_ANNOUNCE_STARTED,
                EventType.TRACKER_ANNOUNCE_SUCCESS,
                EventType.TRACKER_ANNOUNCE_ERROR,
            ]:
                # Tracker events - invalidate trackers cache
                info_hash_hex = event.data.get("info_hash", "")
                if info_hash_hex:
                    async with self._cache_lock:
                        if info_hash_hex in self._torrent_trackers_cache:
                            del self._torrent_trackers_cache[info_hash_hex]
                # Notify widgets about tracker events for timeline annotations
                self._notify_widgets_tracker_event(event.type.value, event.data)
                # Don't refresh immediately - trackers update on demand
                await _dispatch(self.on_tracker_event, _event_payload())
                await self._dispatch_listeners("on_tracker_event", _event_payload())

            elif event.type in [
                EventType.PIECE_REQUESTED,
                EventType.PIECE_DOWNLOADED,
                EventType.PIECE_VERIFIED,
                EventType.PIECE_COMPLETED,
            ]:
                # Piece events - invalidate torrent status to refresh piece counts
                # Data provider will handle its own cache invalidation via invalidate_on_event()
                info_hash_hex = event.data.get("info_hash", "")
                if info_hash_hex:
                    async with self._cache_lock:
                        if info_hash_hex in self._torrent_status_cache:
                            del self._torrent_status_cache[info_hash_hex]
                        self._cached_torrents.pop(info_hash_hex, None)
                        self._cached_status.clear()
                # Notify registered widgets
                self._notify_widgets_piece_event(event.type.value, event.data)

            elif event.type == EventType.PROGRESS_UPDATED:
                # Progress events - invalidate progress-related caches
                # Data provider will handle its own cache invalidation via invalidate_on_event()
                info_hash_hex = event.data.get("info_hash", "")
                if info_hash_hex:
                    async with self._cache_lock:
                        # Invalidate torrent status (contains progress)
                        if info_hash_hex in self._torrent_status_cache:
                            del self._torrent_status_cache[info_hash_hex]
                        # Invalidate global stats (contains average progress)
                        self._global_stats_cache = None
                        self._cached_torrents.pop(info_hash_hex, None)
                        self._cached_status.clear()
                # Notify registered widgets
                self._notify_widgets_progress_event(event.type.value, event.data)

            # Emit torrent delta callbacks for UI patching
            if event.type in [
                EventType.TORRENT_STATUS_CHANGED,
                EventType.TORRENT_ADDED,
                EventType.TORRENT_REMOVED,
                EventType.SEEDING_STARTED,
                EventType.SEEDING_STOPPED,
                EventType.SEEDING_STATS_UPDATED,
            ]:
                await _dispatch(
                    self.on_torrent_list_delta,
                    _event_payload(),
                )
                await self._dispatch_listeners("on_torrent_list_delta", _event_payload())

            # Call registered callbacks
            if event.type in self._event_callbacks:
                for callback in self._event_callbacks[event.type]:
                    try:
                        callback(_event_payload())
                    except Exception as e:
                        self.logger.debug("Error in event callback: %s", e)
        except Exception as e:
            self.logger.debug("Error handling WebSocket event: %s", e)

    async def _resync_from_snapshot(self) -> None:
        """Resync adapter caches from daemon UI snapshot (after subscribe or reconnect)."""
        try:
            response = await asyncio.wait_for(
                self._client.get_ui_snapshot(),
                timeout=20.0,
            )
            gs = _normalize_global_stats_read_model(
                response.global_stats if isinstance(response.global_stats, dict) else {},
            )
            torrents_normalized = [
                _normalize_torrent_read_model(
                    t if isinstance(t, dict) else getattr(t, "model_dump", dict)(),
                )
                for t in (response.torrents or [])
            ]
            async with self._cache_lock:
                self._cached_status = gs
                self._global_stats_cache = gs
                self._cached_torrents.clear()
                self.torrents.clear()
                for t in torrents_normalized:
                    info_hash_hex = t.get("info_hash") or t.get("info_hash_hex") or ""
                    if not info_hash_hex:
                        continue
                    try:
                        info_hash = bytes.fromhex(info_hash_hex)
                    except ValueError:
                        continue
                    self._cached_torrents[info_hash_hex] = t
                    self.torrents[info_hash] = _SnapshotTorrentRef(info_hash_hex, t)
            # Pre-populate the aggregated peers cache from the snapshot (R9) so
            # the peer panel paints on first connect/reconnect instead of
            # waiting for the 3s _peers_update_loop.
            snapshot_peers = getattr(response, "peers", None) or []
            if snapshot_peers:
                import time as _time

                self._cached_peers = (list(snapshot_peers), _time.time())
            self.logger.debug("Resynced adapter caches from UI snapshot")
        except Exception as e:
            self.logger.debug("Resync from snapshot failed: %s", e)

    async def _refresh_cache(self) -> None:
        """Refresh cached status from daemon."""
        try:
            torrent_list = await self._executor_adapter.list_torrents()

            async with self._cache_lock:
                self._cached_torrents.clear()
                self.torrents.clear()

                for torrent_status in torrent_list:
                    info_hash_hex = torrent_status.info_hash
                    try:
                        info_hash = bytes.fromhex(info_hash_hex)
                        self.torrents[info_hash] = torrent_status  # Store status object

                        self._cached_torrents[info_hash_hex] = _normalize_torrent_read_model(
                            torrent_status.model_dump(),
                        )
                    except ValueError:
                        continue

                stats = await self._executor_adapter.get_global_stats()
                self._cached_status = _normalize_global_stats_read_model(stats)
        except Exception as e:
            self.logger.debug("Error refreshing cache: %s", e)

    async def _refresh_global_stats_cache(self) -> None:
        """Refresh only the global stats cache (lighter than full cache refresh)."""
        try:
            stats = await self._executor_adapter.get_global_stats()
            async with self._cache_lock:
                self._cached_status = _normalize_global_stats_read_model(stats)
        except Exception as e:
            self.logger.debug("Error refreshing global stats cache: %s", e)

    # AsyncSessionManager interface methods

    async def get_status(self) -> dict[str, Any]:
        """Get status of all torrents."""
        await self._refresh_cache()
        async with self._cache_lock:
            return dict(self._cached_torrents)

    async def get_torrent_status(self, info_hash_hex: str) -> Optional[dict[str, Any]]:
        """Get status of a specific torrent."""
        try:
            # CRITICAL: Use executor adapter (consistent with CLI)
            torrent_status = await self._executor_adapter.get_torrent_status(info_hash_hex)
            if not torrent_status:
                return None

            return _normalize_torrent_read_model(torrent_status.model_dump())
        except Exception as e:
            self.logger.debug("Error getting torrent status: %s", e)
            return None

    async def add_torrent(
        self,
        path: Union[str, dict[str, Any]],
        resume: bool = False,
    ) -> str:
        """Add a torrent file or torrent data to the session."""
        try:
            # Handle both file paths and torrent dictionaries
            if isinstance(path, dict):
                # For dict, we need to save it as a temp file or use a different approach
                # For now, raise error - this case is less common
                raise ValueError("Adding torrent from dict not supported via daemon IPC")

            # CRITICAL: Use executor for all operations (consistent with CLI)
            result = await self._executor.execute(
                "torrent.add",
                path_or_magnet=str(path),
                output_dir=None,
                resume=resume,
            )

            if not result.success:
                raise RuntimeError(result.error or "Failed to add torrent")

            info_hash_hex = result.data.get("info_hash", "")
            if not info_hash_hex:
                raise RuntimeError("Torrent added but no info hash returned")

            # Refresh cache
            await self._refresh_cache()

            return info_hash_hex
        except Exception:
            self.logger.exception("Failed to add torrent via daemon")
            raise

    async def add_magnet(self, uri: str, resume: bool = False) -> str:
        """Add a magnet link to the session."""
        try:
            # CRITICAL: Use executor for all operations (consistent with CLI)
            result = await self._executor.execute(
                "torrent.add",
                path_or_magnet=uri,
                output_dir=None,
                resume=resume,
            )

            if not result.success:
                raise RuntimeError(result.error or "Failed to add magnet")

            info_hash_hex = result.data.get("info_hash", "")
            if not info_hash_hex:
                raise RuntimeError("Magnet added but no info hash returned")

            # Refresh cache
            await self._refresh_cache()

            return info_hash_hex
        except Exception:
            self.logger.exception("Failed to add magnet via daemon")
            raise

    async def remove(self, info_hash_hex: str) -> bool:
        """Remove a torrent from the session."""
        try:
            # CRITICAL: Use executor for all operations (consistent with CLI)
            result = await self._executor.execute(
                "torrent.remove",
                info_hash=info_hash_hex,
            )
            if result.success:
                await self._refresh_cache()
            return result.success
        except Exception as e:
            self.logger.debug("Error removing torrent: %s", e)
            return False

    async def pause_torrent(self, info_hash_hex: str) -> bool:
        """Pause a torrent download by info hash."""
        try:
            # CRITICAL: Use executor for all operations (consistent with CLI)
            result = await self._executor.execute(
                "torrent.pause",
                info_hash=info_hash_hex,
            )
            return result.success
        except Exception as e:
            self.logger.debug("Error pausing torrent: %s", e)
            return False

    async def resume_torrent(self, info_hash_hex: str) -> bool:
        """Resume a paused torrent by info hash."""
        try:
            # CRITICAL: Use executor for all operations (consistent with CLI)
            result = await self._executor.execute(
                "torrent.resume",
                info_hash=info_hash_hex,
            )
            return result.success
        except Exception as e:
            self.logger.debug("Error resuming torrent: %s", e)
            return False

    async def get_global_stats(self) -> dict[str, Any]:
        """Aggregate global statistics across all torrents."""
        await self._refresh_global_stats_cache()
        async with self._cache_lock:
            return dict(self._cached_status)

    async def get_peers_for_torrent(self, info_hash_hex: str) -> list[dict[str, Any]]:
        """Return list of peers for a torrent via daemon IPC."""
        try:
            return await self._executor_adapter.get_peers_for_torrent(info_hash_hex)
        except Exception as e:
            self.logger.debug("Error getting peers for torrent %s: %s", info_hash_hex[:8], e)
            return []

    # XET folder methods (matching AsyncSessionManager interface)

    async def add_xet_folder(
        self,
        folder_path: str,
        tonic_file: Optional[str] = None,
        tonic_link: Optional[str] = None,
        sync_mode: Optional[str] = None,
        source_peers: Optional[list[str]] = None,
        check_interval: Optional[float] = None,
    ) -> dict[str, Any]:
        """Add XET folder for synchronization. Returns dict with folder_key, workspace_id, sync_mode, folder_name, allowlist_hash."""
        try:
            # Get adapter from executor
            from ccbt.executor.manager import ExecutorManager
            executor_manager = ExecutorManager.get_instance()
            executor = executor_manager.get_executor(session_manager=self)

            result = await executor.execute(
                "xet.add_xet_folder",
                folder_path=folder_path,
                tonic_file=tonic_file,
                tonic_link=tonic_link,
                sync_mode=sync_mode,
                source_peers=source_peers,
                check_interval=check_interval,
            )

            if not result.success:
                raise RuntimeError(result.error or "Failed to add XET folder")

            data = result.data if isinstance(result.data, dict) else {}
            folder_key = data.get("folder_key", folder_path)

            # Refresh cache
            await self._refresh_xet_folders_cache()

            # Trigger callback
            if self.on_xet_folder_added:
                await self.on_xet_folder_added(folder_key, folder_path)

            # Return full structured result (folder_key, workspace_id, sync_mode, folder_name, allowlist_hash)
            return data if data.get("workspace_id") else {"folder_key": folder_key}
        except Exception:
            self.logger.exception("Failed to add XET folder via daemon")
            raise

    async def get_xet_folder_metadata_bytes(self, folder_key: str) -> Optional[bytes]:
        """Get raw metadata bytes for a registered XET folder via executor."""
        try:
            from ccbt.executor.manager import ExecutorManager
            executor_manager = ExecutorManager.get_instance()
            executor = executor_manager.get_executor(session_manager=self)
            result = await executor.execute(
                "xet.get_xet_folder_metadata_bytes",
                folder_key=folder_key,
            )
            if result.success and isinstance(result.data, dict):
                return result.data.get("metadata_bytes")
            return None
        except Exception as e:
            self.logger.debug("Error getting XET folder metadata bytes: %s", e)
            return None

    async def remove_xet_folder(self, folder_key: str) -> bool:
        """Remove XET folder from synchronization."""
        try:
            # Get adapter from executor
            from ccbt.executor.manager import ExecutorManager
            executor_manager = ExecutorManager.get_instance()
            executor = executor_manager.get_executor(session_manager=self)

            result = await executor.execute(
                "xet.remove_xet_folder",
                folder_key=folder_key,
            )

            if not result.success:
                return False

            removed = result.data.get("removed", False)

            if removed:
                # Refresh cache
                await self._refresh_xet_folders_cache()

                # Trigger callback
                if self.on_xet_folder_removed:
                    await self.on_xet_folder_removed(folder_key)

            return removed
        except Exception as e:
            self.logger.debug("Error removing XET folder: %s", e)
            return False

    async def get_xet_folder(self, folder_key: str) -> Optional[Any]:
        """Get XET folder by key."""
        await self._refresh_xet_folders_cache()
        async with self._cache_lock:
            return self.xet_folders.get(folder_key)

    async def list_xet_folders(self) -> list[dict[str, Any]]:
        """List all registered XET folders."""
        await self._refresh_xet_folders_cache()
        async with self._cache_lock:
            return list(self.xet_folders.values())

    async def get_xet_folder_status(self, folder_key: str) -> Optional[dict[str, Any]]:
        """Get XET folder status."""
        try:
            # Get adapter from executor
            from ccbt.executor.manager import ExecutorManager
            executor_manager = ExecutorManager.get_instance()
            executor = executor_manager.get_executor(session_manager=self)

            result = await executor.execute(
                "xet.get_xet_folder_status",
                folder_key=folder_key,
            )

            if not result.success:
                return None

            return result.data.get("status")
        except Exception as e:
            self.logger.debug("Error getting XET folder status: %s", e)
            return None

    async def get_media_stream_status(
        self,
        info_hash_hex: Optional[str] = None,
        stream_id: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        """Get media stream status via daemon executor."""
        try:
            result = await self._executor.execute(
                "media.status",
                info_hash=info_hash_hex,
                stream_id=stream_id,
            )
            if not result.success:
                return None
            return result.data.get("status")
        except Exception as e:
            self.logger.debug("Error getting media stream status: %s", e)
            return None

    async def _refresh_xet_folders_cache(self) -> None:
        """Refresh XET folders cache from daemon."""
        try:
            # Get adapter from executor
            from ccbt.executor.manager import ExecutorManager
            executor_manager = ExecutorManager.get_instance()
            executor = executor_manager.get_executor(session_manager=self)

            result = await executor.execute("xet.list_xet_folders")

            if result.success:
                folders = result.data.get("folders", [])
                async with self._cache_lock:
                    self.xet_folders = {
                        folder.get("folder_key"): folder
                        for folder in folders
                    }
        except Exception as e:
            self.logger.debug("Error refreshing XET folders cache: %s", e)

    async def force_announce(self, info_hash_hex: str) -> bool:
        """Force a tracker announce for a given torrent via daemon IPC."""
        try:
            result = await self._executor.execute(
                "torrent.force_announce",
                info_hash=info_hash_hex,
            )
            return bool(result.success)
        except Exception as e:
            self.logger.debug("Error forcing announce for %s: %s", info_hash_hex[:8], e)
            return False

    async def set_rate_limits(
        self,
        info_hash_hex: str,
        download_kib: int,
        upload_kib: int,
    ) -> bool:
        """Set per-torrent rate limits via daemon IPC."""
        try:
            result = await self._executor.execute(
                "torrent.set_rate_limits",
                info_hash=info_hash_hex,
                download_kib=download_kib,
                upload_kib=upload_kib,
            )
            return bool(result.success)
        except Exception as e:
            self.logger.debug(
                "Error setting rate limits for %s: %s", info_hash_hex[:8], e
            )
            return False

    async def reload_config(self, new_config: Any) -> None:
        """Reload configuration."""
        try:
            # CRITICAL: Use executor for all operations (consistent with CLI)
            config_dict = new_config.model_dump(mode="json") if hasattr(new_config, "model_dump") else new_config
            result = await self._executor.execute(
                "config.update",
                config_dict=config_dict,
            )
            if result.success:
                self.config = new_config
            else:
                raise RuntimeError(result.error or "Failed to update config")
        except Exception as e:
            self.logger.warning("Failed to reload config via daemon: %s", e)

    # Properties matching AsyncSessionManager

    @property
    def peers(self) -> list[dict[str, Any]]:
        """Get list of connected peers aggregated from all torrents."""
        # This is a synchronous property, but we need async data
        # Return cached peers if available, otherwise empty list
        # The cache should be updated via WebSocket events or periodic polling
        if hasattr(self, "_cached_peers"):
            peers_data, timestamp = self._cached_peers
            # Return cached data if less than 3 seconds old
            import time
            if time.time() - timestamp < 3.0:
                return peers_data
        return []

    async def _update_peers_cache(self) -> None:
        """Update cached peers list by aggregating from all torrents."""
        try:
            all_peers: list[dict[str, Any]] = []
            seen_peers: set[tuple[str, int]] = set()

            # CRITICAL: Use executor adapter for all operations (consistent with CLI)
            torrent_list = await self._executor_adapter.list_torrents()

            # Aggregate peers from all torrents (executor returns list of dicts)
            for torrent_status in torrent_list:
                info_hash_hex = getattr(torrent_status, "info_hash", "")
                if not info_hash_hex:
                    continue
                try:
                    peer_list = await self._executor_adapter.get_peers_for_torrent(info_hash_hex)
                    if not isinstance(peer_list, list):
                        continue
                    for peer_info in peer_list:
                        if not isinstance(peer_info, dict):
                            continue
                        ip = peer_info.get("ip", "")
                        port = int(peer_info.get("port", 0))
                        peer_key = (ip, port)
                        if peer_key not in seen_peers:
                            seen_peers.add(peer_key)
                            all_peers.append({
                                "ip": ip,
                                "port": port,
                                "download_rate": peer_info.get("download_rate", 0.0),
                                "upload_rate": peer_info.get("upload_rate", 0.0),
                                "choked": peer_info.get("choked", False),
                                "client": peer_info.get("client"),
                            })
                except Exception as e:
                    self.logger.debug("Error getting peers for torrent %s: %s", info_hash_hex, e)

            # Cache the results
            import time
            self._cached_peers = (all_peers, time.time())
        except Exception as e:
            self.logger.debug("Error updating peers cache: %s", e)

    async def _peers_update_loop(self) -> None:
        """Background task to periodically update peers cache."""
        while self._websocket_connected:
            try:
                await self._update_peers_cache()
                # Update every 3 seconds
                await asyncio.sleep(3.0)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.debug("Error in peers update loop: %s", e)
                await asyncio.sleep(3.0)

    @property
    def dht(self) -> Optional[Any]:
        """Get DHT instance (not available via IPC)."""
        return None

    def parse_magnet_link(self, magnet_uri: str) -> Optional[dict[str, Any]]:
        """Parse magnet link and return torrent data.
        
        Args:
            magnet_uri: Magnet URI string
            
        Returns:
            Dictionary with minimal torrent data or None if parsing fails
        """
        from ccbt.session.torrent_utils import parse_magnet_link as parse_magnet
        return parse_magnet(magnet_uri, logger=self.logger)

    # Additional helper methods

    def register_event_callback(
        self,
        event_type: EventType,
        callback: Callable[[dict[str, Any]], None],
    ) -> None:
        """Register a callback for a specific event type."""
        if event_type not in self._event_callbacks:
            self._event_callbacks[event_type] = []
        self._event_callbacks[event_type].append(callback)

    def unregister_event_callback(
        self,
        event_type: EventType,
        callback: Callable[[dict[str, Any]], None],
    ) -> None:
        """Unregister a callback for a specific event type."""
        if event_type in self._event_callbacks:
            try:
                self._event_callbacks[event_type].remove(callback)
            except ValueError:
                pass

    def register_widget(self, widget: Any) -> None:
        """Register a widget to receive event-driven updates.
        
        Args:
            widget: Widget instance that has on_piece_event, on_progress_event, and/or on_peer_event methods
        """
        if widget not in self._widget_callbacks:
            self._widget_callbacks.append(widget)
            logger.debug("Registered widget %s for event-driven updates", type(widget).__name__)

    def unregister_widget(self, widget: Any) -> None:
        """Unregister a widget from event-driven updates.
        
        Args:
            widget: Widget instance to unregister
        """
        try:
            self._widget_callbacks.remove(widget)
            logger.debug("Unregistered widget %s from event-driven updates", type(widget).__name__)
        except ValueError:
            pass

    def _notify_widgets_piece_event(self, event_type: str, event_data: dict[str, Any]) -> None:
        """Notify all registered widgets about a piece event."""
        for widget in self._widget_callbacks:
            try:
                if hasattr(widget, "on_piece_event"):
                    widget.on_piece_event(event_type, event_data)
            except Exception as e:
                logger.debug("Error notifying widget %s about piece event: %s", type(widget).__name__, e)

    def _notify_widgets_progress_event(self, event_type: str, event_data: dict[str, Any]) -> None:
        """Notify all registered widgets about a progress event."""
        for widget in self._widget_callbacks:
            try:
                if hasattr(widget, "on_progress_event"):
                    widget.on_progress_event(event_type, event_data)
            except Exception as e:
                logger.debug("Error notifying widget %s about progress event: %s", type(widget).__name__, e)

    def _notify_widgets_peer_event(self, event_type: str, event_data: dict[str, Any]) -> None:
        """Notify all registered widgets about a peer event."""
        for widget in self._widget_callbacks:
            try:
                if hasattr(widget, "on_peer_event"):
                    widget.on_peer_event(event_type, event_data)
            except Exception as e:
                logger.debug("Error notifying widget %s about peer event: %s", type(widget).__name__, e)

    def _notify_widgets_tracker_event(self, event_type: str, event_data: dict[str, Any]) -> None:
        """Notify all registered widgets about a tracker event."""
        for widget in self._widget_callbacks:
            try:
                if hasattr(widget, "on_tracker_event"):
                    widget.on_tracker_event(event_type, event_data)
            except Exception as e:
                logger.debug("Error notifying widget %s about tracker event: %s", type(widget).__name__, e)

    def _notify_widgets_media_event(self, event_type: str, event_data: dict[str, Any]) -> None:
        """Notify all registered widgets about a media-stream event."""
        for widget in self._widget_callbacks:
            try:
                if hasattr(widget, "on_media_event"):
                    widget.on_media_event(event_type, event_data)
            except Exception as e:
                logger.debug(
                    "Error notifying widget %s about media event: %s",
                    type(widget).__name__,
                    e,
                )
