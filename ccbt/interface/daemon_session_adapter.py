"""Daemon interface adapter for Textual interface.

Provides AsyncSessionManager-like interface that wraps IPCClient for daemon communication.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from ccbt.daemon.ipc_client import IPCClient
    from ccbt.daemon.ipc_protocol import EventType, WebSocketEvent

from ccbt.config.config import get_config
from ccbt.daemon.ipc_protocol import EventType

logger = logging.getLogger(__name__)


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
        
        # WebSocket subscription
        self._websocket_task: asyncio.Task | None = None
        self._event_callbacks: dict[EventType, list[Callable[[dict[str, Any]], None]]] = {}
        self._websocket_connected = False
        
        # Widget event callbacks - widgets that want to receive real-time updates
        self._widget_callbacks: list[Any] = []  # List of widget instances with event handler methods
        
        # Callbacks (matching AsyncSessionManager interface)
        self.on_torrent_added: Callable[[bytes, str], None] | None = None
        self.on_torrent_removed: Callable[[bytes], None] | None = None
        self.on_torrent_complete: Callable[[bytes, str], None] | None = None
        # New async hooks for WebSocket-driven UI updates
        self.on_global_stats: Callable[[dict[str, Any]], None] | None = None
        self.on_torrent_list_delta: Callable[[dict[str, Any]], None] | None = None
        self.on_peer_metrics: Callable[[dict[str, Any]], None] | None = None
        self.on_tracker_event: Callable[[dict[str, Any]], None] | None = None
        self.on_metadata_event: Callable[[dict[str, Any]], None] | None = None
        # XET folder callbacks
        self.on_xet_folder_added: Callable[[str, str], None] | None = None
        self.on_xet_folder_removed: Callable[[str], None] | None = None
        
        # Properties matching AsyncSessionManager
        self.torrents: dict[bytes, Any] = {}  # Will be populated from cached status
        self.xet_folders: dict[str, Any] = {}  # Will be populated from cached status
        self.lock = asyncio.Lock()  # Compatibility with AsyncSessionManager
        self.dht_client: Any | None = None  # Not available via IPC
        self.metrics: Any | None = None  # Not directly available
        self.peer_service: Any | None = None  # Not directly available
        self.security_manager: Any | None = None  # Not directly available
        self.nat_manager: Any | None = None  # Not directly available
        self.tcp_server: Any | None = None  # Not directly available
        
        self.logger = logger

    async def start(self) -> None:
        """Connect to daemon and start WebSocket subscription."""
        max_retries = 3
        retry_delay = 1.0
        
        for attempt in range(max_retries):
            try:
                # Verify connection
                if not await self._client.is_daemon_running():
                    if attempt < max_retries - 1:
                        self.logger.warning(
                            "Daemon is not running or not accessible (attempt %d/%d), retrying...",
                            attempt + 1,
                            max_retries
                        )
                        await asyncio.sleep(retry_delay)
                        continue
                    else:
                        raise RuntimeError("Daemon is not running or not accessible after %d attempts" % max_retries)
                
                # Connect WebSocket for real-time updates
                if await self._client.connect_websocket():
                    self._websocket_connected = True
                    
                    # CRITICAL: Cancel IPC client's receive loop - we'll use our own
                    # This prevents "Concurrent call to receive() is not allowed" error
                    # The IPC client starts _websocket_receive_loop() in connect_websocket(),
                    # but we need to use our own _websocket_event_loop() for proper event handling
                    import contextlib
                    if self._client._websocket_task and not self._client._websocket_task.done():  # type: ignore[attr-defined]
                        self._client._websocket_task.cancel()  # type: ignore[attr-defined]
                        # Wait for cancellation to complete with timeout
                        try:
                            await asyncio.wait_for(
                                self._client._websocket_task,  # type: ignore[attr-defined]
                                timeout=0.5
                            )
                        except (asyncio.CancelledError, asyncio.TimeoutError):
                            # Cancellation completed or timed out - either way, task is cancelled
                            pass
                        except Exception:
                            # Any other exception - task is likely cancelled anyway
                            pass
                        finally:
                            self._client._websocket_task = None  # type: ignore[attr-defined]
                    
                    # CRITICAL: Add a small delay to ensure the async for loop has fully stopped
                    # This prevents race conditions where the loop might still be waiting for a message
                    await asyncio.sleep(0.1)
                    
                    # Subscribe to relevant events
                    await self._client.subscribe_events([
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
                        # Piece events for real-time piece updates
                        EventType.PIECE_REQUESTED,
                        EventType.PIECE_DOWNLOADED,
                        EventType.PIECE_VERIFIED,
                        EventType.PIECE_COMPLETED,
                        # Progress events for real-time progress updates
                        EventType.PROGRESS_UPDATED,
                    ])
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
                    
                    self.logger.info("WebSocket connected and subscribed to events")
                else:
                    self.logger.warning("Failed to connect WebSocket, will use polling only")
                
                # Initial status fetch
                await self._refresh_cache()
                
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
            with asyncio.suppress(asyncio.CancelledError):
                await self._websocket_task
            self._websocket_task = None
        
        # Stop peers update task
        if self._peers_update_task:
            self._peers_update_task.cancel()
            with asyncio.suppress(asyncio.CancelledError):
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
                # CRITICAL FIX: Use batch receiving for better efficiency - process multiple events at once
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
                            await self._client.subscribe_events([
                                EventType.TORRENT_ADDED,
                                EventType.TORRENT_REMOVED,
                                EventType.TORRENT_COMPLETED,
                                EventType.TORRENT_STATUS_CHANGED,
                            ])
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
            async def _dispatch(callback: Callable[..., Any] | None, *args: Any) -> None:
                """Invoke optional callback, awaiting if it returns coroutine."""
                if not callback:
                    return
                try:
                    result = callback(*args)
                    if asyncio.iscoroutine(result):
                        await result
                except Exception as cb_error:
                    self.logger.debug("Error in adapter callback %s: %s", getattr(callback, "__name__", "?"), cb_error)

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
                await self._refresh_cache()
            
            elif event.type == EventType.TORRENT_REMOVED:
                info_hash_hex = event.data.get("info_hash", "")
                if info_hash_hex and self.on_torrent_removed:
                    try:
                        info_hash = bytes.fromhex(info_hash_hex)
                        await self.on_torrent_removed(info_hash)
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
                await self._refresh_cache()
            
            elif event.type == EventType.TORRENT_STATUS_CHANGED:
                # Update cached status for this torrent
                info_hash_hex = event.data.get("info_hash", "")
                if info_hash_hex:
                    async with self._cache_lock:
                        # Invalidate cached status to force refresh
                        if info_hash_hex in self._torrent_status_cache:
                            del self._torrent_status_cache[info_hash_hex]
                await self._refresh_cache()
            
            elif event.type == EventType.METADATA_READY:
                # Metadata is now available - trigger cache refresh
                info_hash_hex = event.data.get("info_hash", "")
                if info_hash_hex:
                    async with self._cache_lock:
                        # Invalidate cached files to force refresh
                        if info_hash_hex in self._torrent_files_cache:
                            del self._torrent_files_cache[info_hash_hex]
                await self._refresh_cache()
            
            elif event.type in [
                EventType.METADATA_FETCH_STARTED,
                EventType.METADATA_FETCH_PROGRESS,
                EventType.METADATA_FETCH_COMPLETED,
                EventType.METADATA_FETCH_FAILED,
            ]:
                # Metadata fetch events - just log for now, could trigger UI updates
                self.logger.debug("Metadata fetch event: %s for %s", event.type, event.data.get("info_hash", ""))
                payload = {"event": event.type.value, **(event.data or {})}
                await _dispatch(self.on_metadata_event, payload)
            
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
                await self._refresh_cache()
            
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
                await self._refresh_cache()
            
            elif event.type == EventType.GLOBAL_STATS_UPDATED:
                # Global stats updated - invalidate global stats cache
                async with self._cache_lock:
                    self._global_stats_cache = None
                # Notify listeners with fresh metrics payload (if provided)
                await _dispatch(self.on_global_stats, event.data or {})
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
                payload = {"event": event.type.value, **(event.data or {})}
                await _dispatch(self.on_tracker_event, payload)
            
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
                        # Invalidate torrent status cache if it exists
                        if hasattr(self, "_torrent_status_cache") and info_hash_hex in self._torrent_status_cache:
                            del self._torrent_status_cache[info_hash_hex]
                # Trigger cache refresh for real-time updates
                await self._refresh_cache()
                # Notify registered widgets
                self._notify_widgets_piece_event(event.type.value, event.data)
            
            elif event.type == EventType.PROGRESS_UPDATED:
                # Progress events - invalidate progress-related caches
                # Data provider will handle its own cache invalidation via invalidate_on_event()
                info_hash_hex = event.data.get("info_hash", "")
                if info_hash_hex:
                    async with self._cache_lock:
                        # Invalidate torrent status (contains progress) if it exists
                        if hasattr(self, "_torrent_status_cache") and info_hash_hex in self._torrent_status_cache:
                            del self._torrent_status_cache[info_hash_hex]
                        # Invalidate global stats (contains average progress) if it exists
                        if hasattr(self, "_global_stats_cache"):
                            self._global_stats_cache = None
                # Trigger cache refresh for real-time updates
                await self._refresh_cache()
                # Notify registered widgets
                self._notify_widgets_progress_event(event.type.value, event.data)
            
            elif event.type in [
                EventType.PEER_CONNECTED,
                EventType.PEER_DISCONNECTED,
                EventType.PEER_HANDSHAKE_COMPLETE,
                EventType.PEER_BITFIELD_RECEIVED,
            ]:
                # Notify widgets about peer events (in addition to cache invalidation above)
                self._notify_widgets_peer_event(event.type.value, event.data)
                await _dispatch(self.on_peer_metrics, event.data or {})
            
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
                    {
                        "event": event.type.value,
                        **(event.data or {}),
                    },
                )
            
            # Call registered callbacks
            if event.type in self._event_callbacks:
                for callback in self._event_callbacks[event.type]:
                    try:
                        callback(event.data)
                    except Exception as e:
                        self.logger.debug("Error in event callback: %s", e)
        except Exception as e:
            self.logger.debug("Error handling WebSocket event: %s", e)

    async def _refresh_cache(self) -> None:
        """Refresh cached status from daemon."""
        try:
            # CRITICAL: Use executor adapter for all operations (consistent with CLI)
            torrent_list = await self._executor_adapter.list_torrents()
            
            async with self._cache_lock:
                self._cached_torrents.clear()
                self.torrents.clear()
                
                for torrent_status in torrent_list:
                    info_hash_hex = torrent_status.info_hash
                    try:
                        info_hash = bytes.fromhex(info_hash_hex)
                        self.torrents[info_hash] = torrent_status  # Store status object
                        
                        # Convert to dict format for compatibility
                        self._cached_torrents[info_hash_hex] = {
                            "info_hash": info_hash_hex,
                            "name": torrent_status.name,
                            "status": torrent_status.status,
                            "progress": torrent_status.progress,
                            "download_rate": torrent_status.download_rate,
                            "upload_rate": torrent_status.upload_rate,
                            "peers": torrent_status.num_peers,
                            "seeds": torrent_status.num_seeds,
                            "total_size": torrent_status.total_size,
                            "downloaded": torrent_status.downloaded,
                            "uploaded": torrent_status.uploaded,
                        }
                    except ValueError:
                        continue
                
                # Update global stats using executor adapter
                stats = await self._executor_adapter.get_global_stats()
                
                # Aggregate download_rate, upload_rate, and average_progress from all torrents
                total_download_rate = 0.0
                total_upload_rate = 0.0
                total_progress = 0.0
                torrent_count = 0
                
                for torrent_status in torrent_list:
                    if hasattr(torrent_status, 'download_rate'):
                        total_download_rate += torrent_status.download_rate
                    elif isinstance(torrent_status, dict):
                        total_download_rate += torrent_status.get("download_rate", 0.0)
                    
                    if hasattr(torrent_status, 'upload_rate'):
                        total_upload_rate += torrent_status.upload_rate
                    elif isinstance(torrent_status, dict):
                        total_upload_rate += torrent_status.get("upload_rate", 0.0)
                    
                    if hasattr(torrent_status, 'progress'):
                        total_progress += torrent_status.progress
                    elif isinstance(torrent_status, dict):
                        total_progress += torrent_status.get("progress", 0.0)
                    
                    torrent_count += 1
                
                # Calculate averages
                average_progress = total_progress / torrent_count if torrent_count > 0 else 0.0
                
                # Use aggregated values if available, otherwise fall back to stats from executor
                download_rate = total_download_rate if total_download_rate > 0.0 else stats.get("download_rate", 0.0)
                upload_rate = total_upload_rate if total_upload_rate > 0.0 else stats.get("upload_rate", 0.0)
                
                self._cached_status = {
                    "num_torrents": stats.get("num_torrents", torrent_count),
                    "num_active": stats.get("num_active", 0),
                    "num_paused": stats.get("num_paused", 0),
                    "num_seeding": stats.get("num_seeding", 0),
                    "download_rate": download_rate,
                    "upload_rate": upload_rate,
                    "average_progress": average_progress,
                }
        except Exception as e:
            self.logger.debug("Error refreshing cache: %s", e)

    # AsyncSessionManager interface methods

    async def get_status(self) -> dict[str, Any]:
        """Get status of all torrents."""
        await self._refresh_cache()
        async with self._cache_lock:
            return dict(self._cached_torrents)

    async def get_torrent_status(self, info_hash_hex: str) -> dict[str, Any] | None:
        """Get status of a specific torrent."""
        try:
            # CRITICAL: Use executor adapter (consistent with CLI)
            torrent_status = await self._executor_adapter.get_torrent_status(info_hash_hex)
            if not torrent_status:
                return None
            
            return {
                "info_hash": torrent_status.info_hash,
                "name": torrent_status.name,
                "status": torrent_status.status,
                "progress": torrent_status.progress,
                "download_rate": torrent_status.download_rate,
                "upload_rate": torrent_status.upload_rate,
                "peers": torrent_status.num_peers,
                "seeds": torrent_status.num_seeds,
                "total_size": torrent_status.total_size,
                "downloaded": torrent_status.downloaded,
                "uploaded": torrent_status.uploaded,
            }
        except Exception as e:
            self.logger.debug("Error getting torrent status: %s", e)
            return None

    async def add_torrent(
        self,
        path: str | dict[str, Any],
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
        except Exception as e:
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
        except Exception as e:
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
        await self._refresh_cache()
        async with self._cache_lock:
            stats = dict(self._cached_status)
            
            # Calculate aggregate stats from torrents
            total_download_rate = 0.0
            total_upload_rate = 0.0
            total_progress = 0.0
            num_active = 0
            num_paused = 0
            num_seeding = 0
            
            for torrent_data in self._cached_torrents.values():
                status = torrent_data.get("status", "")
                if status == "paused":
                    num_paused += 1
                elif status == "seeding":
                    num_seeding += 1
                else:
                    num_active += 1
                
                total_download_rate += float(torrent_data.get("download_rate", 0.0))
                total_upload_rate += float(torrent_data.get("upload_rate", 0.0))
                total_progress += float(torrent_data.get("progress", 0.0))
            
            stats.update({
                "num_active": num_active,
                "num_paused": num_paused,
                "num_seeding": num_seeding,
                "download_rate": total_download_rate,
                "upload_rate": total_upload_rate,
                "average_progress": total_progress / len(self._cached_torrents) if self._cached_torrents else 0.0,
            })
            
            return stats

    async def get_peers_for_torrent(self, info_hash_hex: str) -> list[dict[str, Any]]:
        """Return list of peers for a torrent."""
        # IPC doesn't provide detailed peer info, return empty list
        # This could be extended if IPC adds peer details endpoint
        return []

    # XET folder methods (matching AsyncSessionManager interface)

    async def add_xet_folder(
        self,
        folder_path: str,
        tonic_file: str | None = None,
        tonic_link: str | None = None,
        sync_mode: str | None = None,
        source_peers: list[str] | None = None,
        check_interval: float | None = None,
    ) -> str:
        """Add XET folder for synchronization."""
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
            
            folder_key = result.data.get("folder_key", folder_path)
            
            # Refresh cache
            await self._refresh_xet_folders_cache()
            
            # Trigger callback
            if self.on_xet_folder_added:
                await self.on_xet_folder_added(folder_key, folder_path)
            
            return folder_key
        except Exception as e:
            self.logger.exception("Failed to add XET folder via daemon")
            raise

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

    async def get_xet_folder(self, folder_key: str) -> Any | None:
        """Get XET folder by key."""
        await self._refresh_xet_folders_cache()
        async with self._cache_lock:
            return self.xet_folders.get(folder_key)

    async def list_xet_folders(self) -> list[dict[str, Any]]:
        """List all registered XET folders."""
        await self._refresh_xet_folders_cache()
        async with self._cache_lock:
            return list(self.xet_folders.values())

    async def get_xet_folder_status(self, folder_key: str) -> dict[str, Any] | None:
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
        """Force a tracker announce for a given torrent if possible."""
        # IPC doesn't provide force announce, return False
        return False

    async def set_rate_limits(
        self,
        info_hash_hex: str,
        download_kib: int,
        upload_kib: int,
    ) -> bool:
        """Set per-torrent rate limits."""
        # IPC doesn't provide rate limit setting, return False
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
            
            # Aggregate peers from all torrents
            for torrent_status in torrent_list:
                info_hash_hex = torrent_status.info_hash
                try:
                    peer_list = await self._executor_adapter.get_peers_for_torrent(info_hash_hex)
                    for peer_info in peer_list.peers:
                        peer_key = (peer_info.ip, peer_info.port)
                        if peer_key not in seen_peers:
                            seen_peers.add(peer_key)
                            all_peers.append({
                                "ip": peer_info.ip,
                                "port": peer_info.port,
                                "download_rate": peer_info.download_rate,
                                "upload_rate": peer_info.upload_rate,
                                "choked": peer_info.choked,
                                "client": peer_info.client,
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
    def dht(self) -> Any | None:
        """Get DHT instance (not available via IPC)."""
        return None

    def parse_magnet_link(self, magnet_uri: str) -> dict[str, Any] | None:
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
