from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from typing import Any, Callable, cast

from ccbt.config.config import get_config
from ccbt.core.magnet import (
    build_torrent_data_from_metadata,
    parse_magnet,
)
from ccbt.discovery.tracker import AsyncTrackerClient
from ccbt.peer import AsyncPeerConnectionManager
from ccbt.piece.async_metadata_exchange import fetch_metadata_from_peers
from ccbt.piece.async_piece_manager import AsyncPieceManager


class AsyncDownloadManager:
    """High-performance async download manager."""

    def __init__(
        self,
        torrent_data: dict[str, Any] | Any,
        output_dir: str = ".",
        peer_id: bytes | None = None,
        security_manager: Any | None = None,
    ):
        """Initialize async download manager."""
        # Normalize torrent_data to dict shape expected by piece manager
        if hasattr(torrent_data, "model_dump"):
            self.torrent_data = torrent_data.model_dump()  # type: ignore[call-arg]
        else:
            self.torrent_data = torrent_data

        if isinstance(self.torrent_data, list):
            error_msg = (
                f"torrent_data cannot be a list, got {type(self.torrent_data)}. "
                "Expected dict or TorrentInfo object."
            )
            raise TypeError(error_msg)
        if not isinstance(self.torrent_data, dict) and not hasattr(
            torrent_data, "model_dump"
        ):
            error_msg = f"torrent_data must be a dict or TorrentInfo, got {type(self.torrent_data)}"
            raise TypeError(error_msg)

        self.output_dir = output_dir
        self.config = get_config()
        self.security_manager = security_manager

        if peer_id is None:
            from ccbt.utils.version import get_full_peer_id

            peer_id = get_full_peer_id()
        self.our_peer_id = peer_id

        # Prepare dict for piece manager
        if hasattr(torrent_data, "model_dump") and callable(torrent_data.model_dump):
            torrent_dict = torrent_data.model_dump()
        else:
            torrent_dict = torrent_data
        if not isinstance(torrent_dict, dict):
            msg = f"Expected dict for torrent_dict, got {type(torrent_dict)}"
            raise TypeError(msg)
        torrent_dict = cast("dict[str, Any]", torrent_dict)
        if "pieces_info" not in torrent_dict and {
            "piece_length",
            "pieces",
            "num_pieces",
            "total_length",
            "info_hash",
            "name",
        }.issubset(torrent_dict.keys()):
            torrent_dict = {
                "info_hash": torrent_dict["info_hash"],
                "name": torrent_dict.get("name", ""),
                "announce": torrent_dict.get("announce", ""),
                "announce_list": torrent_dict.get("announce_list", []),
                "file_info": {
                    "total_length": torrent_dict["total_length"],
                },
                "pieces_info": {
                    "piece_length": torrent_dict["piece_length"],
                    "num_pieces": torrent_dict["num_pieces"],
                    "piece_hashes": torrent_dict["pieces"],
                },
            }

        try:
            self.piece_manager = AsyncPieceManager(torrent_dict)
        except (KeyError, AttributeError, TypeError) as e:
            self._init_error = e
            self.piece_manager = None
        else:
            self._init_error = None
        self.peer_manager: Any | None = None

        # State
        self.download_complete = False
        self.start_time: float | None = None
        self._background_tasks: set[asyncio.Task] = set()

        # Metadata fetch tracking
        self._metadata_fetching = False
        self._metadata_fetched = False
        self._metadata_fetch_attempts = 0

        # Rate tracking
        self._bytes_downloaded_history: deque[tuple[float, int]] = deque(maxlen=60)
        self._bytes_uploaded_history: deque[tuple[float, int]] = deque(maxlen=60)
        self._last_rate_calculation: float = 0.0
        self._download_rate: float = 0.0
        self._upload_rate: float = 0.0

        # Callbacks
        self.on_peer_connected: Callable | None = None
        self.on_peer_disconnected: Callable | None = None
        self.on_piece_completed: Callable | None = None
        self.on_download_complete: Callable | None = None

        self.logger = logging.getLogger(__name__)

    async def start(self) -> None:
        """Start the download manager."""
        if self._init_error is not None:
            msg = f"Download manager initialization failed: {self._init_error}"
            raise RuntimeError(msg) from self._init_error
        if self.piece_manager is None:
            msg = "Piece manager not initialized"
            raise RuntimeError(msg)
        await self.piece_manager.start()
        self.logger.info("Async download manager started")

    async def stop(self) -> None:
        """Stop the download manager."""
        if self._background_tasks:
            for task in list(self._background_tasks):
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                    except Exception as e:
                        self.logger.debug("Error waiting for background task: %s", e)
            self._background_tasks.clear()

        if self.peer_manager:
            await self.peer_manager.stop()
        if self.piece_manager:
            await self.piece_manager.stop()
        self.logger.info("Async download manager stopped")

    async def start_download(
        self, peers: list[dict[str, Any]], max_peers_per_torrent: int | None = None
    ) -> None:
        """Start the download process.
        
        Args:
            peers: List of peer dictionaries to connect to
            max_peers_per_torrent: Optional maximum peers per torrent (overrides config)
        """
        self.start_time = time.time()

        # Extract is_private (BEP 27)
        is_private = False
        try:
            if isinstance(self.torrent_data, dict):
                is_private = self.torrent_data.get("is_private", False)
            elif hasattr(self.torrent_data, "is_private"):
                is_private = getattr(self.torrent_data, "is_private", False)
        except Exception as e:
            self.logger.warning("Failed to extract is_private flag: %s", e)
            is_private = False

        if self.piece_manager is None:
            msg = "Piece manager not initialized - start() must be called first"
            raise RuntimeError(msg)

        # Reuse existing peer_manager when possible
        if self.peer_manager is not None:
            existing_connections = (
                len(self.peer_manager.connections)
                if hasattr(self.peer_manager, "connections")
                else 0
            )
            self.logger.info(
                "Peer manager already exists with %d connections - reusing",
                existing_connections,
            )
            await self.piece_manager.start_download(self.peer_manager)
            if peers:
                await self.peer_manager.connect_to_peers(peers)
            self.logger.info(
                "Download started successfully (reused existing peer manager)"
            )
            return

        if not isinstance(self.torrent_data, dict):
            error_msg = (
                f"torrent_data must be a dict, got {type(self.torrent_data)}. "
                "Cannot initialize peer manager."
            )
            self.logger.error(error_msg)
            raise TypeError(error_msg)

        try:
            self.peer_manager = AsyncPeerConnectionManager(
                self.torrent_data,
                self.piece_manager,
                self.our_peer_id,
                max_peers_per_torrent=max_peers_per_torrent,
            )
        except Exception:
            self.logger.exception("Failed to initialize peer manager")
            raise
        self.peer_manager._security_manager = self.security_manager  # type: ignore[attr-defined]
        self.peer_manager._is_private = is_private  # type: ignore[attr-defined]

        # Wire callbacks
        self.peer_manager.on_peer_connected = self._on_peer_connected
        self.peer_manager.on_peer_disconnected = self._on_peer_disconnected
        self.peer_manager.on_piece_received = self._on_piece_received
        self.peer_manager.on_bitfield_received = self._on_bitfield_received
        
        # CRITICAL FIX: Propagate callbacks to existing connections if any exist
        # This handles the case where connections are created before callbacks are registered
        # The property setters will automatically propagate, but we also do it explicitly here
        # to ensure it happens immediately
        if hasattr(self.peer_manager, "connections") and hasattr(self.peer_manager, "_propagate_callbacks_to_connections"):
            try:
                # Try to propagate immediately if event loop is running
                loop = asyncio.get_running_loop()
                # Schedule propagation (non-blocking)
                asyncio.create_task(self.peer_manager._propagate_callbacks_to_connections())
                self.logger.debug("Scheduled callback propagation to existing connections")
            except RuntimeError:
                # No running event loop - property setters will handle propagation when loop starts
                self.logger.debug("No running event loop, callbacks will propagate when connections are created")

        self.piece_manager.on_piece_completed = self._on_piece_completed
        # CRITICAL FIX: Don't override on_piece_verified if it's already set by session
        # The session's callback writes to disk, this one just broadcasts HAVE
        # Only set if not already set (session will set it before start_download is called)
        # Check if callback exists and is not None - if session set it, keep it
        existing_callback = getattr(self.piece_manager, 'on_piece_verified', None)
        if existing_callback is None:
            # No callback set yet - use download manager's callback (will be overridden by session if needed)
            self.piece_manager.on_piece_verified = self._on_piece_verified
        self.piece_manager.on_download_complete = self._on_download_complete

        if hasattr(self.peer_manager, "start") and callable(
            getattr(self.peer_manager, "start", None)
        ):
            await self.peer_manager.start()  # type: ignore[misc]

        # LOGGING OPTIMIZATION: Changed to DEBUG - use -vv to see peer connection details
        self.logger.debug("Connecting to %s peers...", len(peers))
        await self.peer_manager.connect_to_peers(peers)
        # LOGGING OPTIMIZATION: Changed to DEBUG - use -vv to see piece download start
        self.logger.debug("Starting piece download...")
        await self.piece_manager.start_download(self.peer_manager)
        self.logger.info("Download started successfully!")

    def _calculate_rates(self) -> tuple[float, float]:
        current_time = time.time()
        peer_manager = self.peer_manager
        if peer_manager is not None:
            total_download_rate = 0.0
            total_upload_rate = 0.0
            for connection in peer_manager.get_connected_peers():
                if hasattr(connection, "stats"):
                    stats = connection.stats
                    if hasattr(stats, "download_rate"):
                        total_download_rate += stats.download_rate
                    if hasattr(stats, "upload_rate"):
                        total_upload_rate += stats.upload_rate

            self._download_rate = total_download_rate
            self._upload_rate = total_upload_rate
            self._last_rate_calculation = current_time
            return (total_download_rate, total_upload_rate)

        return (self._download_rate, self._upload_rate)

    async def get_status(self) -> dict[str, Any]:
        has_metadata = (
            self.torrent_data
            and isinstance(self.torrent_data, dict)
            and self.torrent_data.get("pieces_info") is not None
        )
        if not has_metadata:
            status = "metadata_fetching"
        elif not self.piece_manager:
            status = "initializing"
        elif self.download_complete:
            status = "seeding"
        else:
            status = "downloading"

        if not self.piece_manager:
            return {
                "status": status,
                "progress": 0.0,
                "piece_status": {},
                "connected_peers": 0,
                "active_peers": 0,
                "download_time": time.time() - self.start_time
                if self.start_time
                else 0,
                "download_complete": False,
                "download_rate": 0.0,
                "upload_rate": 0.0,
                "metadata_fetching": self._metadata_fetching,
                "metadata_fetched": self._metadata_fetched,
                "metadata_fetch_attempts": self._metadata_fetch_attempts,
            }

        piece_status = self.piece_manager.get_piece_status()
        progress = self.piece_manager.get_download_progress()

        connected_peers = 0
        active_peers = 0
        if self.peer_manager:
            connected_peers = len(self.peer_manager.get_connected_peers())
            active_peers = len(self.peer_manager.get_active_peers())

        download_rate, upload_rate = self._calculate_rates()

        return {
            "status": status,
            "progress": progress,
            "piece_status": piece_status,
            "connected_peers": connected_peers,
            "active_peers": active_peers,
            "download_time": time.time() - self.start_time if self.start_time else 0,
            "download_complete": self.download_complete,
            "download_rate": download_rate,
            "upload_rate": upload_rate,
            "metadata_fetching": self._metadata_fetching,
            "metadata_fetched": self._metadata_fetched,
            "metadata_fetch_attempts": self._metadata_fetch_attempts,
        }

    def _on_peer_connected(self, connection) -> None:
        # LOGGING OPTIMIZATION: Changed to DEBUG - use -vv to see peer connection details
        self.logger.debug("Connected to peer: %s", connection.peer_info)
        if self.on_peer_connected:
            self.on_peer_connected(connection)

    def _on_peer_disconnected(self, connection) -> None:
        # LOGGING OPTIMIZATION: Changed to DEBUG - use -vv to see peer disconnection details
        self.logger.debug("Disconnected from peer: %s", connection.peer_info)
        if self.on_peer_disconnected:
            self.on_peer_disconnected(connection)

    def _on_bitfield_received(self, connection, bitfield_message) -> None:
        bitfield_length = (
            len(bitfield_message.bitfield)
            if bitfield_message and bitfield_message.bitfield
            else 0
        )
        self.logger.info(
            "Received bitfield from %s (bitfield length=%d bytes)",
            connection.peer_info,
            bitfield_length,
        )

        if (
            self.piece_manager
            and bitfield_message
            and hasattr(self.piece_manager, "update_peer_availability")
        ):
            self.logger.info(
                "Updating piece manager with peer availability for %s",
                connection.peer_info,
            )

            async def update_availability():
                try:
                    await self.piece_manager.update_peer_availability(  # type: ignore[union-attr]
                        str(connection.peer_info),
                        bitfield_message.bitfield,
                    )
                    self.logger.info(
                        "Successfully updated peer availability for %s",
                        connection.peer_info,
                    )
                except Exception:
                    self.logger.exception(
                        "Error updating peer availability for %s",
                        connection.peer_info,
                    )

            async def update_and_wait() -> None:
                task = asyncio.create_task(update_availability())
                self._background_tasks.add(task)
                task.add_done_callback(self._background_tasks.discard)
                try:
                    await asyncio.wait_for(task, timeout=5.0)
                    self.logger.debug(
                        "Peer availability updated for %s, piece selection can proceed",
                        connection.peer_info,
                    )
                except asyncio.TimeoutError:
                    self.logger.warning(
                        "Peer availability update timed out for %s (continuing anyway)",
                        connection.peer_info,
                    )

            update_task = asyncio.create_task(update_and_wait())
            self._background_tasks.add(update_task)
            update_task.add_done_callback(self._background_tasks.discard)
        else:
            self.logger.warning(
                "Cannot update peer availability: piece_manager=%s, bitfield_message=%s",
                self.piece_manager is not None,
                bitfield_message is not None,
            )

        if self.piece_manager and self.peer_manager and bitfield_message:
            missing_pieces = self.piece_manager.get_missing_pieces()
            if missing_pieces:
                bitfield = bitfield_message.bitfield
                has_needed_piece = False
                for piece_idx in missing_pieces[:10]:
                    byte_idx = piece_idx // 8
                    bit_idx = piece_idx % 8
                    if byte_idx < len(bitfield) and bitfield[byte_idx] & (
                        1 << (7 - bit_idx)
                    ):
                        has_needed_piece = True
                        break

                if has_needed_piece and not connection.am_interested:

                    async def send_interested():
                        try:
                            from ccbt.peer.peer import InterestedMessage

                            if connection.writer is not None:
                                message = InterestedMessage()
                                data = message.encode()
                                connection.writer.write(data)
                                await connection.writer.drain()
                                connection.am_interested = True
                                self.logger.debug(
                                    "Sent interested to %s (fallback after bitfield)",
                                    connection.peer_info,
                                )
                            else:
                                self.logger.warning(
                                    "Cannot send interested to %s: writer is None",
                                    connection.peer_info,
                                )
                        except Exception as e:
                            self.logger.warning(
                                "Failed to send interested to %s: %s",
                                connection.peer_info,
                                e,
                            )

                    task = asyncio.create_task(send_interested())
                    self._background_tasks.add(task)
                    task.add_done_callback(self._background_tasks.discard)
                elif has_needed_piece and connection.am_interested:
                    self.logger.debug(
                        "Peer %s has needed pieces and we're already interested",
                        connection.peer_info,
                    )

    def _on_piece_received(self, connection, piece_message) -> None:
        """Handle received piece block from peer."""
        # CRITICAL FIX: Log at INFO level to track piece reception (suppress during shutdown)
        from ccbt.utils.shutdown import is_shutting_down
        
        if not is_shutting_down():
            self.logger.info(
                "DOWNLOAD_MANAGER: Received piece %d block from %s (offset=%d, size=%d bytes)",
                piece_message.piece_index,
                connection.peer_info,
                piece_message.begin,
                len(piece_message.block),
            )
        else:
            # During shutdown, only log at debug level
            self.logger.debug(
                "DOWNLOAD_MANAGER: Received piece %d block from %s (shutdown in progress)",
                piece_message.piece_index,
                connection.peer_info,
            )
        
        if not self.piece_manager:
            self.logger.warning(
                "Received piece %d from %s but piece_manager is None!",
                piece_message.piece_index,
                connection.peer_info,
            )
            return
            
        # Update peer availability
        task = asyncio.create_task(
            self.piece_manager.update_peer_have(
                str(connection.peer_info),
                piece_message.piece_index,
            ),
        )
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

        # Handle the piece block with peer information for performance tracking
        peer_key = f"{connection.peer_info.ip}:{connection.peer_info.port}"
        task = asyncio.create_task(
            self.piece_manager.handle_piece_block(
                piece_message.piece_index,
                piece_message.begin,
                piece_message.block,
                peer_key=peer_key,
            ),
        )
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    def _on_piece_completed(self, piece_index: int) -> None:
        # LOGGING OPTIMIZATION: Changed to DEBUG - use -vv to see individual piece completion
        self.logger.debug("Completed piece %s", piece_index)
        if self.on_piece_completed:
            self.on_piece_completed(piece_index)

    async def _on_piece_verified(self, piece_index: int) -> None:
        # NOTE: This method is typically overridden by the session's async callback
        # If called directly, send HAVE messages synchronously
        self.logger.debug("Download manager _on_piece_verified called for piece %s", piece_index)
        if self.peer_manager:
            await self.peer_manager.broadcast_have(piece_index)

    def _on_download_complete(self) -> None:
        self.download_complete = True
        self.logger.info("Download complete!")
        if self.on_download_complete:
            self.on_download_complete()


async def _announce_to_trackers(
    torrent_data: dict[str, Any],
    download_manager: AsyncDownloadManager,
    port: int = 6881,
) -> None:
    """Announce to trackers and start download with discovered peers."""
    tracker_urls = torrent_data.get("announce_list", [])
    if not tracker_urls:
        announce = torrent_data.get("announce")
        if announce:
            tracker_urls = [announce]
    tracker_urls = [url for url in tracker_urls if url]
    if not tracker_urls:
        return

    tracker_client = AsyncTrackerClient()
    all_peers: list[dict[str, Any]] = []
    seen_peers: set[tuple[str, int]] = set()

    try:
        await tracker_client.start()
        announce_torrent_data = torrent_data.copy()
        if "peer_id" not in announce_torrent_data:
            announce_torrent_data["peer_id"] = tracker_client._generate_peer_id()  # noqa: SLF001

        responses = await tracker_client.announce_to_multiple(
            announce_torrent_data,
            tracker_urls,
            port=port,
            event="started",
        )

        for response in responses:
            # CRITICAL FIX: Handle None response (UDP tracker client unavailable)
            if response is None:
                continue
            if not hasattr(response, "peers") or not response.peers:
                continue
            for peer_info in response.peers:
                peer = cast("Any", peer_info)
                peer_key = (peer.ip, peer.port)
                if peer_key not in seen_peers:
                    seen_peers.add(peer_key)
                    all_peers.append(
                        {
                            "ip": peer.ip,
                            "port": peer.port,
                            "peer_source": peer.peer_source or "tracker",
                        }
                    )

        if all_peers:
            logger = logging.getLogger(__name__)
            # LOGGING OPTIMIZATION: Keep as INFO - this is an important operation start
            logger.info("Starting download with %s peers from trackers", len(all_peers))
            await download_manager.start_download(all_peers)
        else:
            logging.getLogger(__name__).warning("No peers discovered from trackers")
    except Exception as e:
        logging.getLogger(__name__).warning("Failed to announce to trackers: %s", e)
    finally:
        try:
            await tracker_client.stop()
        except Exception as e:
            logging.getLogger(__name__).debug("Error stopping tracker client: %s", e)


async def download_torrent(torrent_path: str, output_dir: str = ".") -> AsyncDownloadManager | None:
    """Download a single torrent file (compat helper for tests)."""
    import contextlib

    from ccbt.core.torrent import TorrentParser

    download_manager = None
    monitor_task = None

    try:
        parser = TorrentParser()
        torrent_data = parser.parse(torrent_path)
        download_manager = AsyncDownloadManager(torrent_data, output_dir)
        await download_manager.start()

        async def monitor_progress():
            while not download_manager.download_complete:
                _ = await download_manager.get_status()
                await asyncio.sleep(1)

        monitor_task = asyncio.create_task(monitor_progress())
        config = get_config()
        td = (
            torrent_data.model_dump()
            if hasattr(torrent_data, "model_dump")
            else torrent_data
        )  # type: ignore[union-attr]
        if not isinstance(td, dict):
            td = cast("dict[str, Any]", td)
        await _announce_to_trackers(
            td, download_manager, port=config.network.listen_port
        )
        with contextlib.suppress(asyncio.CancelledError):
            await asyncio.wait_for(monitor_task, timeout=10.0)
    except Exception:
        pass
    finally:
        # Ensure proper cleanup
        if monitor_task and not monitor_task.done():
            monitor_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await monitor_task

    return download_manager


async def download_magnet(magnet_uri: str, output_dir: str = ".") -> AsyncDownloadManager | None:
    """Download from a magnet link (compat helper for tests)."""
    download_manager = None
    tracker_clients = []

    def track_tracker_client(client):
        tracker_clients.append(client)
        return client

    try:
        magnet_info = parse_magnet(magnet_uri)
        peers: list[dict[str, Any]] = []
        if magnet_info.trackers:
            tracker_client = track_tracker_client(AsyncTrackerClient())
            try:
                await tracker_client.start()
                torrent_data = {
                    "info_hash": magnet_info.info_hash,
                    "peer_id": tracker_client._generate_peer_id(),  # noqa: SLF001
                    "file_info": {"total_length": 0},
                }
                for url in magnet_info.trackers:
                    if not url:
                        continue
                    td_copy = torrent_data.copy()
                    td_copy["announce"] = url
                    try:
                        response = await tracker_client.announce(
                            td_copy,
                            port=get_config().network.listen_port,
                            event="started",
                        )
                        # CRITICAL FIX: Handle None response (UDP tracker client unavailable)
                        if response is None:
                            continue
                        if not hasattr(response, "peers") or not response.peers:
                            continue
                        for peer_info in response.peers:
                            peer = cast("Any", peer_info)
                            peers.append(
                                {
                                    "ip": peer.ip,
                                    "port": peer.port,
                                    "peer_source": peer.peer_source or "tracker",
                                }
                            )
                    except Exception as e:
                        logging.getLogger(__name__).warning(
                            "Failed to announce to tracker %s: %s", url, e
                        )
            finally:
                try:
                    await tracker_client.stop()
                except Exception as e:
                    logging.getLogger(__name__).debug(
                        "Error stopping tracker client: %s", e
                    )

        metadata = await fetch_metadata_from_peers(magnet_info.info_hash, peers)
        if metadata:
            torrent_data = build_torrent_data_from_metadata(
                magnet_info.info_hash,
                metadata,
            )
            download_manager = AsyncDownloadManager(torrent_data, output_dir)
            await download_manager.start()

            download_peers: list[dict[str, Any]] = []
            if magnet_info.trackers:
                tracker_client = track_tracker_client(AsyncTrackerClient())
                try:
                    await tracker_client.start()
                    announce_torrent_data = torrent_data.copy()
                    announce_torrent_data["peer_id"] = (
                        tracker_client._generate_peer_id()  # noqa: SLF001
                    )
                    responses = await tracker_client.announce_to_multiple(
                        announce_torrent_data,
                        magnet_info.trackers,
                        port=get_config().network.listen_port,
                        event="started",
                    )
                    seen_peers: set[tuple[str, int]] = set()
                    for response in responses:
                        # CRITICAL FIX: Handle None response (UDP tracker client unavailable)
                        if response is None:
                            continue
                        if not hasattr(response, "peers") or not response.peers:
                            continue
                        for peer_info in response.peers:
                            peer = cast("Any", peer_info)
                            peer_key = (peer.ip, peer.port)
                            if peer_key not in seen_peers:
                                seen_peers.add(peer_key)
                                download_peers.append(
                                    {
                                        "ip": peer.ip,
                                        "port": peer.port,
                                        "peer_source": peer.peer_source or "tracker",
                                    }
                                )
                finally:
                    try:
                        await tracker_client.stop()
                    except Exception as e:
                        logging.getLogger(__name__).debug(
                            "Error stopping tracker client: %s", e
                        )

            if download_peers:
                await download_manager.start_download(download_peers)
            else:
                logging.getLogger(__name__).warning(
                    "No peers available to start download"
                )
            await asyncio.sleep(1)
            await download_manager.stop()
        else:
            logging.getLogger(__name__).warning(
                "Failed to fetch metadata for magnet link"
            )
            return None
    except Exception:
        pass
    finally:
        # Stop all tracker clients (but don't stop download manager here - caller will handle it)
        for tracker_client in tracker_clients:
            try:
                await tracker_client.stop()
            except Exception as e:
                logging.getLogger(__name__).debug(f"Error stopping tracker client: {e}")

    return download_manager
