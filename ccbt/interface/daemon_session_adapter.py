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
        
        # Cached state for performance
        self._cached_status: dict[str, Any] = {}
        self._cached_torrents: dict[str, dict[str, Any]] = {}
        self._cache_lock = asyncio.Lock()
        
        # WebSocket subscription
        self._websocket_task: asyncio.Task | None = None
        self._event_callbacks: dict[EventType, list[Callable[[dict[str, Any]], None]]] = {}
        self._websocket_connected = False
        
        # Callbacks (matching AsyncSessionManager interface)
        self.on_torrent_added: Callable[[bytes, str], None] | None = None
        self.on_torrent_removed: Callable[[bytes], None] | None = None
        self.on_torrent_complete: Callable[[bytes, str], None] | None = None
        
        # Properties matching AsyncSessionManager
        self.torrents: dict[bytes, Any] = {}  # Will be populated from cached status
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
                    
                    # Subscribe to relevant events
                    await self._client.subscribe_events([
                        EventType.TORRENT_ADDED,
                        EventType.TORRENT_REMOVED,
                        EventType.TORRENT_COMPLETED,
                        EventType.TORRENT_STATUS_CHANGED,
                    ])
                    
                    # Start event receive loop
                    self._websocket_task = asyncio.create_task(self._websocket_event_loop())
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
                    self.logger.exception("Failed to start daemon interface adapter after %d attempts: %s", max_retries, e)
                    raise

    async def stop(self) -> None:
        """Close IPC connection and cleanup."""
        # Stop WebSocket task
        if self._websocket_task:
            self._websocket_task.cancel()
            with asyncio.suppress(asyncio.CancelledError):
                await self._websocket_task
            self._websocket_task = None
        
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
                event = await self._client.receive_event(timeout=1.0)
                if event:
                    await self._handle_websocket_event(event)
                    # Reset failure count on successful event
                    consecutive_failures = 0
                    reconnect_delay = 1.0
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
            if event.type == EventType.TORRENT_ADDED:
                info_hash_hex = event.data.get("info_hash", "")
                name = event.data.get("name", "")
                if info_hash_hex and self.on_torrent_added:
                    try:
                        info_hash = bytes.fromhex(info_hash_hex)
                        await self.on_torrent_added(info_hash, name)
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
                        if info_hash_hex in self._cached_torrents:
                            self._cached_torrents[info_hash_hex].update(event.data)
            
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
            # Get all torrents
            torrent_list = await self._client.list_torrents()
            
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
                
                # Update global stats
                status = await self._client.get_status()
                self._cached_status = {
                    "num_torrents": status.num_torrents,
                    "num_active": status.num_torrents,  # Approximate
                    "num_paused": 0,  # Not available from status
                    "num_seeding": 0,  # Not available from status
                    "download_rate": 0.0,  # Would need to aggregate
                    "upload_rate": 0.0,  # Would need to aggregate
                    "average_progress": 0.0,  # Would need to calculate
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
            torrent_status = await self._client.get_torrent_status(info_hash_hex)
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
            
            # Add torrent via IPC
            info_hash_hex = await self._client.add_torrent(
                path_or_magnet=str(path),
                output_dir=None,
            )
            
            # Refresh cache
            await self._refresh_cache()
            
            return info_hash_hex
        except Exception as e:
            self.logger.exception("Failed to add torrent via daemon: %s", e)
            raise

    async def add_magnet(self, uri: str, resume: bool = False) -> str:
        """Add a magnet link to the session."""
        try:
            # Add magnet via IPC (same endpoint as torrent)
            info_hash_hex = await self._client.add_torrent(
                path_or_magnet=uri,
                output_dir=None,
            )
            
            # Refresh cache
            await self._refresh_cache()
            
            return info_hash_hex
        except Exception as e:
            self.logger.exception("Failed to add magnet via daemon: %s", e)
            raise

    async def remove(self, info_hash_hex: str) -> bool:
        """Remove a torrent from the session."""
        try:
            result = await self._client.remove_torrent(info_hash_hex)
            if result:
                await self._refresh_cache()
            return result
        except Exception as e:
            self.logger.debug("Error removing torrent: %s", e)
            return False

    async def pause_torrent(self, info_hash_hex: str) -> bool:
        """Pause a torrent download by info hash."""
        try:
            return await self._client.pause_torrent(info_hash_hex)
        except Exception as e:
            self.logger.debug("Error pausing torrent: %s", e)
            return False

    async def resume_torrent(self, info_hash_hex: str) -> bool:
        """Resume a paused torrent by info hash."""
        try:
            return await self._client.resume_torrent(info_hash_hex)
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
            config_dict = new_config.model_dump(mode="json") if hasattr(new_config, "model_dump") else new_config
            await self._client.update_config(config_dict)
            self.config = new_config
        except Exception as e:
            self.logger.warning("Failed to reload config via daemon: %s", e)

    # Properties matching AsyncSessionManager

    @property
    def peers(self) -> list[dict[str, Any]]:
        """Get list of connected peers (placeholder)."""
        return []

    @property
    def dht(self) -> Any | None:
        """Get DHT instance (not available via IPC)."""
        return None

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

