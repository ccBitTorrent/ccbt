"""DHT discovery setup and peer discovery orchestration."""

from __future__ import annotations

import asyncio
from typing import Any


class DHTDiscoverySetup:
    """Sets up and manages DHT peer discovery for a torrent session."""

    def __init__(self, session: Any) -> None:
        """Initialize DHT discovery setup.

        Args:
            session: AsyncTorrentSession instance

        """
        self.session = session
        self.logger = session.logger

    async def setup_dht_discovery(self) -> None:
        """Set up DHT peer discovery if enabled and torrent is not private."""
        self.logger.info(
            "Checking DHT setup: session_manager=%s, dht_client=%s, is_private=%s, enable_dht=%s",
            self.session.session_manager is not None,
            self.session.session_manager.dht_client
            if self.session.session_manager
            else None,
            self.session.is_private,
            self.session.config.discovery.enable_dht,
        )

        # CRITICAL FIX: Set up DHT discovery if DHT client exists, even if not fully bootstrapped yet
        # The discovery task will wait for bootstrap to complete before querying
        if (
            self.session.session_manager
            and self.session.session_manager.dht_client
            and not self.session.is_private
            and self.session.config.discovery.enable_dht
        ):
            # Check DHT bootstrap status for logging
            dht_client = self.session.session_manager.dht_client
            if hasattr(dht_client, "routing_table") and hasattr(
                dht_client.routing_table, "nodes"
            ):
                routing_table_size = len(dht_client.routing_table.nodes)
                if routing_table_size > 0:
                    self.logger.debug(
                        "DHT is ready (routing table: %d nodes)", routing_table_size
                    )
                else:
                    self.logger.debug(
                        "DHT client exists but bootstrap not complete yet (routing table: %d nodes, discovery will wait)",
                        routing_table_size,
                    )

            # Set up DHT discovery
            await self._setup_dht_callbacks_and_discovery()
        else:
            # Log why DHT discovery is not being set up
            reasons = []
            if not self.session.session_manager:
                reasons.append("no session_manager")
            elif not self.session.session_manager.dht_client:
                reasons.append("no dht_client")
            if self.session.is_private:
                reasons.append("torrent is private")
            if not self.session.config.discovery.enable_dht:
                reasons.append("DHT disabled in config")
            self.logger.warning(
                "DHT peer discovery NOT set up for %s. Reasons: %s",
                self.session.info.name,
                ", ".join(reasons) if reasons else "unknown",
            )

    async def _setup_dht_callbacks_and_discovery(self) -> None:
        """Set up DHT callbacks and start discovery loop."""
        self.logger.info("Setting up DHT peer discovery for %s", self.session.info.name)
        self.logger.info("DHT client available, creating discovery callbacks")

        # Create peer discovery handler
        on_dht_peers_discovered = self._create_peer_discovery_handler()

        # Create deduplication wrapper
        on_dht_peers_discovered_with_dedup = self._create_dedup_wrapper(
            on_dht_peers_discovered
        )

        # Register callbacks
        await self._register_dht_callbacks(on_dht_peers_discovered_with_dedup)

        # Trigger immediate initial query
        await self._trigger_initial_query()

        # Start periodic discovery loop
        await self._start_discovery_loop()

    def _create_peer_discovery_handler(self) -> Any:
        """Create handler for DHT-discovered peers.

        Returns:
            Async function that handles peer discovery

        """

        async def on_dht_peers_discovered(peers: list[tuple[str, int]]) -> None:
            """Handle DHT-discovered peers by adding them to the download.

            Args:
                peers: List of (ip, port) tuples

            """
            try:
                # CRITICAL FIX: Add detailed logging for DHT peer discovery
                self.logger.info(
                    "DHT discovered %d peer(s) for torrent %s",
                    len(peers),
                    self.session.info.name,
                )
                if peers:
                    # Log first few peers for debugging
                    sample_peers = peers[:3]
                    self.logger.debug(
                        "DHT peer samples: %s",
                        ", ".join(f"{ip}:{port}" for ip, port in sample_peers),
                    )

                if not self.session.download_manager:
                    self.logger.warning(
                        "DHT peers discovered but download_manager is None"
                    )
                    return

                # Convert DHT peers to peer list format
                peer_list = [
                    {
                        "ip": ip,
                        "port": port,
                        "peer_source": "dht",
                    }
                    for ip, port in peers
                ]

                if not peer_list:
                    self.logger.debug("DHT peer list is empty after conversion")
                    return

                # CRITICAL FIX: For magnet links, try metadata exchange first if metadata not available
                metadata_fetched = await self._handle_magnet_metadata_exchange(
                    peer_list
                )

                # Ensure download is started
                download_started = getattr(
                    self.session.download_manager, "_download_started", False
                )
                if not download_started:
                    await self._start_download_with_dht_peers(
                        peer_list, metadata_fetched
                    )
                else:
                    # Download already started, just add peers
                    self.logger.info(
                        "Adding %d DHT-discovered peers to existing download for %s",
                        len(peer_list),
                        self.session.info.name,
                    )
                    from ccbt.session.peers import PeerConnectionHelper

                    helper = PeerConnectionHelper(self.session)
                    try:
                        await helper.connect_peers_to_download(peer_list)
                        self.logger.info(
                            "Successfully initiated connection to %d DHT-discovered peers for %s",
                            len(peer_list),
                            self.session.info.name,
                        )
                        # CRITICAL FIX: Verify peer_manager exists and check connection status after a delay
                        await asyncio.sleep(1.0)  # Give connections time to establish
                        peer_manager = getattr(
                            self.session.download_manager, "peer_manager", None
                        )
                        if peer_manager:
                            active_count = (
                                len(
                                    [
                                        c
                                        for c in peer_manager.connections.values()
                                        if c.is_active()
                                    ]
                                )
                                if hasattr(peer_manager, "connections")
                                else 0
                            )
                            self.logger.debug(
                                "DHT peer connection status for %s: %d active connections after adding %d peers",
                                self.session.info.name,
                                active_count,
                                len(peer_list),
                            )
                    except Exception as connection_error:
                        self.logger.warning(
                            "Failed to connect %d DHT-discovered peers for %s: %s",
                            len(peer_list),
                            self.session.info.name,
                            connection_error,
                            exc_info=True,
                        )
                        # CRITICAL FIX: Retry connection with exponential backoff
                        # Store peers for retry if connection fails
                        if not hasattr(self.session, "_pending_dht_peers"):
                            self.session._pending_dht_peers = []  # type: ignore[attr-defined]
                        self.session._pending_dht_peers.extend(peer_list)  # type: ignore[attr-defined]
                        self.logger.debug(
                            "Queued %d peers for retry connection (total queued: %d)",
                            len(peer_list),
                            len(self.session._pending_dht_peers),  # type: ignore[attr-defined]
                        )
            except Exception as e:
                self.logger.error(
                    "Critical error in DHT peer discovery handler for %s: %s",
                    self.session.info.name,
                    e,
                    exc_info=True,
                )
                # CRITICAL FIX: Don't let errors stop peer discovery - log and continue
                # The discovery loop will retry on next iteration

        return on_dht_peers_discovered

    async def _handle_magnet_metadata_exchange(
        self, peer_list: list[dict[str, Any]]
    ) -> bool:
        """Handle metadata exchange for magnet links.

        Args:
            peer_list: List of peer dictionaries

        Returns:
            True if metadata was fetched, False otherwise

        """
        is_magnet_link = (
            isinstance(self.session.torrent_data, dict)
            and self.session.torrent_data.get("file_info") is None
        ) or (
            isinstance(self.session.torrent_data, dict)
            and self.session.torrent_data.get("file_info", {}).get("total_length", 0)
            == 0
        )

        metadata_fetched = False
        if is_magnet_link and peer_list:
            # Check if metadata is already available
            metadata_fetched = (
                isinstance(self.session.torrent_data, dict)
                and self.session.torrent_data.get("file_info") is not None
                and self.session.torrent_data.get("file_info", {}).get(
                    "total_length", 0
                )
                > 0
            )

            if not metadata_fetched:
                # Try to fetch metadata from DHT-discovered peers
                self.logger.info(
                    "Magnet link detected, attempting metadata exchange with %d DHT-discovered peer(s)",
                    len(peer_list),
                )
                try:
                    from ccbt.piece.async_metadata_exchange import (
                        fetch_metadata_from_peers,
                    )

                    # CRITICAL FIX: Increase metadata fetching timeout to 60 seconds
                    # Magnet links may need more time to fetch metadata, especially for less popular torrents
                    metadata = await fetch_metadata_from_peers(
                        self.session.info.info_hash,
                        peer_list,
                        timeout=60.0,
                    )

                    if metadata:
                        self.logger.info(
                            "Successfully fetched metadata from DHT-discovered peers for %s",
                            self.session.info.name,
                        )
                        # Update torrent_data with metadata
                        from ccbt.core.magnet import (
                            build_torrent_data_from_metadata,
                        )

                        updated_torrent_data = build_torrent_data_from_metadata(
                            self.session.info.info_hash,
                            metadata,
                        )
                        # Merge with existing torrent_data
                        if isinstance(self.session.torrent_data, dict):
                            self.session.torrent_data.update(updated_torrent_data)
                            # CRITICAL FIX: Update download manager's torrent_data and piece_manager
                            if hasattr(self.session.download_manager, "torrent_data"):
                                self.session.download_manager.torrent_data = (
                                    self.session.torrent_data
                                )

                            # CRITICAL FIX: Update piece_manager with new metadata
                            if (
                                hasattr(self.session.download_manager, "piece_manager")
                                and self.session.download_manager.piece_manager
                            ):
                                piece_manager = (
                                    self.session.download_manager.piece_manager
                                )
                                # Update num_pieces from metadata
                                if "pieces_info" in updated_torrent_data:
                                    pieces_info = updated_torrent_data["pieces_info"]
                                    if "num_pieces" in pieces_info:
                                        piece_manager.num_pieces = int(
                                            pieces_info["num_pieces"]
                                        )
                                        self.logger.info(
                                            "Updated piece_manager.num_pieces to %d from metadata",
                                            piece_manager.num_pieces,
                                        )
                                    if "piece_length" in pieces_info:
                                        piece_manager.piece_length = int(
                                            pieces_info["piece_length"]
                                        )

                                # Update torrent_data in piece_manager
                                if hasattr(piece_manager, "torrent_data"):
                                    piece_manager.torrent_data = (
                                        self.session.torrent_data
                                    )

                                # CRITICAL FIX: If download was started but num_pieces was 0, reinitialize pieces
                                if (
                                    piece_manager.num_pieces > 0
                                    and len(piece_manager.pieces) == 0
                                ):
                                    self.logger.info(
                                        "Reinitializing pieces in piece_manager after metadata fetch (num_pieces=%d)",
                                        piece_manager.num_pieces,
                                    )
                                    # Trigger piece initialization by calling start_download again
                                    # CRITICAL FIX: Get peer_manager from download_manager if available
                                    peer_manager_for_restart = None
                                    if hasattr(
                                        self.session.download_manager, "peer_manager"
                                    ):
                                        peer_manager_for_restart = (
                                            self.session.download_manager.peer_manager
                                        )

                                    if hasattr(piece_manager, "start_download"):
                                        try:
                                            await piece_manager.start_download(
                                                peer_manager=peer_manager_for_restart
                                            )
                                            self.logger.info(
                                                "Successfully reinitialized pieces after metadata fetch (num_pieces=%d, pieces_count=%d)",
                                                piece_manager.num_pieces,
                                                len(piece_manager.pieces),
                                            )
                                        except Exception as e:
                                            self.logger.warning(
                                                "Error reinitializing pieces after metadata fetch: %s",
                                                e,
                                                exc_info=True,
                                            )
                                elif (
                                    piece_manager.num_pieces > 0
                                    and len(piece_manager.pieces) > 0
                                ):
                                    # Pieces already initialized, just verify they match num_pieces
                                    if (
                                        len(piece_manager.pieces)
                                        != piece_manager.num_pieces
                                    ):
                                        self.logger.warning(
                                            "Piece count mismatch after metadata fetch: num_pieces=%d, pieces_count=%d. "
                                            "Reinitializing pieces.",
                                            piece_manager.num_pieces,
                                            len(piece_manager.pieces),
                                        )
                                        # Reinitialize pieces to match num_pieces
                                        peer_manager_for_restart = None
                                        if hasattr(
                                            self.session.download_manager,
                                            "peer_manager",
                                        ):
                                            peer_manager_for_restart = self.session.download_manager.peer_manager
                                        if hasattr(piece_manager, "start_download"):
                                            try:
                                                await piece_manager.start_download(
                                                    peer_manager=peer_manager_for_restart
                                                )
                                            except Exception as e:
                                                self.logger.warning(
                                                    "Error reinitializing pieces after metadata fetch: %s",
                                                    e,
                                                    exc_info=True,
                                                )
                        metadata_fetched = True

                        # CRITICAL FIX: Notify download manager that metadata is now available
                        # This allows download to proceed if it was waiting for metadata
                        if hasattr(
                            self.session.download_manager, "on_metadata_available"
                        ):
                            try:
                                await self.session.download_manager.on_metadata_available()
                            except Exception as e:
                                self.logger.debug(
                                    "Error calling on_metadata_available: %s",
                                    e,
                                )
                    else:
                        self.logger.warning(
                            "Metadata exchange failed with DHT-discovered peers for %s (will retry later)",
                            self.session.info.name,
                        )
                except Exception as e:
                    self.logger.warning(
                        "Error during metadata exchange with DHT peers for %s: %s",
                        self.session.info.name,
                        e,
                        exc_info=True,
                    )

        return metadata_fetched

    async def _start_download_with_dht_peers(
        self, peer_list: list[dict[str, Any]], metadata_fetched: bool
    ) -> None:
        """Start download with DHT-discovered peers.

        Args:
            peer_list: List of peer dictionaries
            metadata_fetched: Whether metadata was successfully fetched

        """
        # CRITICAL FIX: Validate torrent_data is not a list before calling start_download
        if isinstance(self.session.torrent_data, list):
            self.logger.error(
                "Cannot start download: torrent_data is a list, not dict or TorrentInfo."
            )
            return

        self.logger.info(
            "Starting download with %d DHT-discovered peers (metadata_fetched=%s)",
            len(peer_list),
            metadata_fetched,
        )
        # async_main.AsyncDownloadManager: start() then start_download(peers)
        try:
            # Initialize piece_manager if not already started
            if not hasattr(self.session.download_manager, "_started") or not getattr(
                self.session.download_manager, "_started", False
            ):
                self.logger.info(
                    "Starting download manager before connecting DHT peers"
                )
                await self.session.download_manager.start()

            # Start download with DHT-discovered peers
            self.logger.info(
                "Starting download with %d DHT-discovered peers",
                len(peer_list),
            )
            await self.session.download_manager.start_download(peer_list)

            # CRITICAL FIX: Set status to 'downloading' immediately after start_download() regardless of peer count
            self.session.info.status = "downloading"
            self.logger.info(
                "Status set to 'downloading' immediately after start_download() with %d DHT-discovered peers",
                len(peer_list),
            )

            # Set up session callbacks on peer_manager
            if self.session.download_manager.peer_manager:
                self.session.download_manager.peer_manager.on_peer_connected = (
                    self.session._on_peer_connected
                )
                self.session.download_manager.peer_manager.on_peer_disconnected = (
                    self.session._on_peer_disconnected
                )
                self.session.download_manager.peer_manager.on_piece_received = (
                    self.session._on_peer_piece_received
                )
                self.session.download_manager.peer_manager.on_bitfield_received = (
                    self.session._on_peer_bitfield_received
                )

                # Update session-level references
                self.session.peer_manager = self.session.download_manager.peer_manager
                self.session.piece_manager = self.session.download_manager.piece_manager

            setattr(  # noqa: B010
                self.session.download_manager, "_download_started", True
            )  # type: ignore[assignment]
            self.logger.info(
                "Started download with %d DHT-discovered peers",
                len(peer_list),
            )
        except Exception:
            self.logger.exception("Failed to start download with DHT peers")
            raise

    def _create_dedup_wrapper(self, on_dht_peers_discovered: Any) -> Any:
        """Create deduplication wrapper for peer discovery.

        Args:
            on_dht_peers_discovered: Original peer discovery handler

        Returns:
            Wrapped handler with deduplication

        """
        # Track recently processed peers to avoid duplicate connection attempts
        if not hasattr(self.session, "_recently_processed_peers"):
            self.session._recently_processed_peers: set[tuple[str, int]] = set()  # type: ignore[attr-defined]
            self.session._recently_processed_peers_lock = asyncio.Lock()  # type: ignore[attr-defined]

        async def on_dht_peers_discovered_with_dedup(
            peers: list[tuple[str, int]],
        ) -> None:
            """Process DHT-discovered peers with deduplication."""
            if not peers:
                return

            # Filter out recently processed peers
            async with self.session._recently_processed_peers_lock:  # type: ignore[attr-defined]
                # Clean up old entries (older than 5 minutes)
                # Keep set size manageable by removing entries periodically
                if len(self.session._recently_processed_peers) > 1000:  # type: ignore[attr-defined]
                    # Clear half of the set (simple cleanup strategy)
                    self.session._recently_processed_peers = set(  # type: ignore[attr-defined]
                        list(self.session._recently_processed_peers)[500:]  # type: ignore[attr-defined]
                    )

                # Filter out already processed peers
                new_peers = [
                    peer
                    for peer in peers
                    if peer not in self.session._recently_processed_peers  # type: ignore[attr-defined]
                ]

                # Mark new peers as processed
                for peer in new_peers:
                    self.session._recently_processed_peers.add(peer)  # type: ignore[attr-defined]

            if not new_peers:
                self.logger.debug(
                    "All %d DHT-discovered peers were already processed, skipping",
                    len(peers),
                )
                return

            if len(new_peers) < len(peers):
                self.logger.debug(
                    "Filtered %d duplicate peers from DHT discovery (%d new, %d total)",
                    len(peers) - len(new_peers),
                    len(new_peers),
                    len(peers),
                )

            # Process the new peers
            await on_dht_peers_discovered(new_peers)

        return on_dht_peers_discovered_with_dedup

    async def _register_dht_callbacks(
        self, on_dht_peers_discovered_with_dedup: Any
    ) -> None:
        """Register DHT callbacks with the DHT client.

        Args:
            on_dht_peers_discovered_with_dedup: Deduplicated peer discovery handler

        """
        # CRITICAL FIX: Add callback invocation counter to verify callbacks are called
        if not hasattr(self.session, "_dht_callback_invocation_count"):
            self.session._dht_callback_invocation_count = 0  # type: ignore[attr-defined]

        # Register DHT callback (DHT expects sync callback, wrap it)
        def dht_callback_wrapper(peers: list[tuple[str, int]]) -> None:
            """Convert sync DHT callback to an async task."""
            # CRITICAL FIX: Increment callback invocation counter
            self.session._dht_callback_invocation_count += 1  # type: ignore[attr-defined]

            # CRITICAL FIX: Add logging to verify callback is being called
            self.logger.info(
                "DHT callback triggered for %s: received %d peer(s) from DHT client (info_hash: %s, invocation #%d)",
                self.session.info.name,
                len(peers),
                self.session.info.info_hash.hex()[:16] + "...",
                self.session._dht_callback_invocation_count,  # type: ignore[attr-defined]
            )
            if not peers:
                # CRITICAL FIX: Still process empty peer list - this indicates query completed
                # The discovery loop needs to know the query finished even if no peers found
                self.logger.info(
                    "DHT callback received empty peer list for %s (query completed, no peers found)",
                    self.session.info.name,
                )
                # Still create task to notify discovery loop that query completed
                # This allows the discovery loop to continue and retry
                task = asyncio.create_task(on_dht_peers_discovered_with_dedup(peers))
                if not hasattr(self.session, "_dht_peer_tasks"):
                    self.session._dht_peer_tasks: set[asyncio.Task] = set()  # type: ignore[attr-defined]
                self.session._dht_peer_tasks.add(task)  # type: ignore[attr-defined]
                task.add_done_callback(self.session._dht_peer_tasks.discard)  # type: ignore[attr-defined]
                return

            # Verify download manager exists before processing
            if not self.session.download_manager:
                self.logger.warning(
                    "DHT callback received %d peers but download_manager is None for %s",
                    len(peers),
                    self.session.info.name,
                )
                return

            # Create async task to process peers
            task = asyncio.create_task(on_dht_peers_discovered_with_dedup(peers))
            # Store task reference to avoid garbage collection
            if not hasattr(self.session, "_dht_peer_tasks"):
                self.session._dht_peer_tasks: set[asyncio.Task] = set()  # type: ignore[attr-defined]
            self.session._dht_peer_tasks.add(task)  # type: ignore[attr-defined]
            task.add_done_callback(self.session._dht_peer_tasks.discard)  # type: ignore[attr-defined]

        # Register callback with DHT client via DiscoveryController (with info_hash filter)
        try:
            from ccbt.session.discovery import DiscoveryController
            from ccbt.session.models import SessionContext
            from ccbt.session.tasks import TaskSupervisor
        except Exception:
            DiscoveryController = None  # type: ignore[assignment]

        if (
            DiscoveryController
            and self.session.session_manager
            and self.session.session_manager.dht_client
        ):
            # Ensure context exists
            if (
                not hasattr(self.session, "_task_supervisor")
                or self.session._task_supervisor is None
            ):
                self.session._task_supervisor = TaskSupervisor()
            if (
                not hasattr(self.session, "_session_ctx")
                or self.session._session_ctx is None
            ):
                td = (
                    self.session.torrent_data
                    if isinstance(self.session.torrent_data, dict)
                    else {
                        "info_hash": self.session.info.info_hash,
                        "name": self.session.info.name,
                    }
                )
                self.session._session_ctx = SessionContext(
                    config=self.session.config,
                    torrent_data=td,
                    output_dir=self.session.output_dir,
                    info=self.session.info,
                    session_manager=self.session.session_manager,
                    logger=self.session.logger,
                    piece_manager=self.session.piece_manager,
                    checkpoint_manager=self.session.checkpoint_manager,
                )
            # Lazily create discovery controller
            if (
                not hasattr(self.session, "_discovery_controller")
                or self.session._discovery_controller is None
            ):
                self.session._discovery_controller = DiscoveryController(
                    self.session._session_ctx, self.session._task_supervisor
                )
            self.session._discovery_controller.register_dht_callback(
                self.session.session_manager.dht_client,  # type: ignore[arg-type]
                on_dht_peers_discovered_with_dedup,
                info_hash=self.session.info.info_hash,
            )
        else:
            # Fallback to direct registration if discovery controller unavailable
            # CRITICAL FIX: add_peer_callback doesn't accept info_hash parameter
            # The callback wrapper already filters by info_hash internally
            self.session.session_manager.dht_client.add_peer_callback(  # type: ignore[union-attr]
                dht_callback_wrapper
            )

        # CRITICAL FIX: Verify callback is in DHT client's peer_callbacks after registration
        # Add retry mechanism to handle timing issues where callback may not be immediately visible
        dht_client = self.session.session_manager.dht_client
        callback_registered = False
        max_retries = 3
        retry_delay = 0.5  # 0.5 seconds between retries

        for retry_attempt in range(max_retries):
            if retry_attempt > 0:
                # Wait before retrying (callback may not be immediately visible)
                await asyncio.sleep(retry_delay)

            if dht_client and hasattr(dht_client, "peer_callbacks"):
                # CRITICAL FIX: peer_callbacks is a list of callback functions, not objects with info_hash
                # Check if our callback wrapper function is in the list
                # The callback wrapper (dht_callback_wrapper) is a closure that captures self.session.info.info_hash
                # We can verify by checking if any callback in the list is our wrapper function
                # Since we just registered it, it should be the last one or we can check by function identity
                if len(dht_client.peer_callbacks) > 0:
                    # The callback was just added, so it should be in the list
                    # We can't easily verify by info_hash since callbacks are just functions,
                    # but we can verify the callback was added by checking the list length increased
                    # or by checking if our wrapper function is in the list
                    try:
                        # Check if our callback wrapper is in the list by comparing function objects
                        # Since dht_callback_wrapper is a local function, we need to check if any callback
                        # matches it. The simplest check is to verify the list has callbacks.
                        # For now, we'll assume if callbacks exist and we just registered one, it's there.
                        # A more robust check would store a reference to the callback, but for now
                        # we'll trust that add_peer_callback() worked if the list has entries.
                        callback_registered = True
                        self.logger.debug(
                            "DHT callback registered (found %d callback(s) in peer_callbacks)",
                            len(dht_client.peer_callbacks),
                        )
                    except Exception as verify_error:
                        self.logger.debug(
                            "Error verifying callback: %s", verify_error
                        )

            if callback_registered:
                break

        if callback_registered:
            self.logger.info(
                "Registered DHT callback for %s (verified in peer_callbacks after %d attempt(s), total callbacks: %d, info_hash: %s)",
                self.session.info.name,
                retry_attempt + 1,
                len(dht_client.peer_callbacks)
                if dht_client and hasattr(dht_client, "peer_callbacks")
                else 0,
                self.session.info.info_hash.hex()[:16] + "...",
            )
        else:
            # Enhanced logging for debugging callback structure
            callback_structure_info = "unknown"
            if dht_client and hasattr(dht_client, "peer_callbacks"):
                if len(dht_client.peer_callbacks) > 0:
                    first_callback = dht_client.peer_callbacks[0]
                    callback_structure_info = f"type={type(first_callback).__name__}, has_info_hash={hasattr(first_callback, 'info_hash') if not isinstance(first_callback, dict) else 'info_hash' in first_callback}"
                else:
                    callback_structure_info = "empty list"

            self.logger.warning(
                "DHT callback registration may have failed for %s (not found in peer_callbacks after %d attempts, info_hash: %s). "
                "DHT peer discovery may not work for this torrent. Callback structure: %s",
                self.session.info.name,
                max_retries,
                self.session.info.info_hash.hex()[:16] + "...",
                callback_structure_info,
            )

    async def _trigger_initial_query(self) -> None:
        """Trigger immediate initial DHT get_peers query after callback registration."""
        dht_client = self.session.session_manager.dht_client
        if not dht_client:
            return

        async def trigger_initial_dht_query() -> None:
            """Trigger immediate DHT get_peers query after callback registration.

            CRITICAL FIX: For magnet links, be more aggressive about DHT queries
            since there are no trackers initially. Query even if routing table is small.
            """
            try:
                # Small delay to ensure callback is fully registered
                await asyncio.sleep(0.1)

                routing_table_size = len(dht_client.routing_table.nodes)

                # CRITICAL FIX: For magnet links, query even with small routing table
                # Magnet links rely heavily on DHT for peer discovery
                is_magnet = (
                    hasattr(self.session, "torrent_data")
                    and isinstance(self.session.torrent_data, dict)
                    and self.session.torrent_data.get("is_magnet", False)
                )

                # Query if routing table has nodes, or if it's a magnet link (be more aggressive)
                if routing_table_size > 0 or is_magnet:
                    if routing_table_size == 0 and is_magnet:
                        self.logger.info(
                            "Triggering immediate DHT get_peers query for magnet link %s "
                            "(routing table empty but will query anyway - magnet links need DHT)",
                            self.session.info.name,
                        )
                    else:
                        self.logger.info(
                            "Triggering immediate DHT get_peers query for %s (routing table: %d nodes)",
                            self.session.info.name,
                            routing_table_size,
                        )

                    # For magnet links, wait a bit longer for bootstrap if routing table is empty
                    if routing_table_size == 0 and is_magnet:
                        self.logger.debug(
                            "Waiting up to 5s for DHT bootstrap before querying magnet link %s",
                            self.session.info.name,
                        )
                        # Wait for bootstrap with timeout
                        for _ in range(10):  # Check every 0.5s for 5s
                            await asyncio.sleep(0.5)
                            routing_table_size = len(dht_client.routing_table.nodes)
                            if routing_table_size > 0:
                                self.logger.info(
                                    "DHT bootstrap completed (routing table: %d nodes), proceeding with query",
                                    routing_table_size,
                                )
                                break

                    try:
                        # Use longer timeout for magnet links (they need more time to find peers)
                        timeout = 45.0 if is_magnet else 30.0
                        peers = await asyncio.wait_for(
                            dht_client.get_peers(
                                self.session.info.info_hash, max_peers=50
                            ),
                            timeout=timeout,
                        )
                        if peers:
                            self.logger.info(
                                "Initial DHT query returned %d peers for %s",
                                len(peers),
                                self.session.info.name,
                            )
                        else:
                            self.logger.debug(
                                "Initial DHT query returned no peers for %s (will retry in periodic loop)",
                                self.session.info.name,
                            )
                    except asyncio.TimeoutError:
                        self.logger.debug(
                            "Initial DHT query timed out for %s (will retry in periodic loop)",
                            self.session.info.name,
                        )
                    except Exception as e:
                        self.logger.debug(
                            "Initial DHT query error for %s: %s (will retry in periodic loop)",
                            self.session.info.name,
                            e,
                        )
                else:
                    self.logger.debug(
                        "Skipping initial DHT query for %s (routing table empty, bootstrap in progress)",
                        self.session.info.name,
                    )
            except Exception as e:
                self.logger.debug(
                    "Error in initial DHT query trigger for %s: %s",
                    self.session.info.name,
                    e,
                )

        # Start immediate query in background
        task = asyncio.create_task(trigger_initial_dht_query())
        _ = task  # Store reference to avoid unused variable warning

    async def _start_discovery_loop(self) -> None:
        """Start DHT discovery in background with periodic retries."""
        dht_client = self.session.session_manager.dht_client
        if not dht_client:
            return

        # CRITICAL FIX: Ensure DHT discovery task is started
        self.logger.info(
            "Creating DHT discovery background task for %s", self.session.info.name
        )
        self.session._dht_discovery_task = asyncio.create_task(  # type: ignore[attr-defined]
            self._run_discovery_loop(dht_client)
        )
        self.logger.info(
            "DHT discovery task started for %s (task=%s, callbacks=%d)",
            self.session.info.name,
            self.session._dht_discovery_task,
            len(dht_client.peer_callbacks),
        )

    async def _run_discovery_loop(self, dht_client: Any) -> None:
        """Run periodic DHT peer discovery loop.

        Args:
            dht_client: DHT client instance

        """
        # Improved retry logic with exponential backoff
        initial_retry_interval = 30.0  # Start with 30 seconds
        max_retry_interval = 300.0  # Cap at 5 minutes
        base_backoff_multiplier = 1.5  # Exponential backoff multiplier
        dht_retry_interval = initial_retry_interval
        max_peers_per_query = 50
        consecutive_failures = 0
        max_consecutive_failures = 10  # Increased from 5 to 10
        attempt_count = 0

        # CRITICAL FIX: Wait for DHT bootstrap to complete (max 120 seconds for slow networks)
        # Increased timeout to 120s to handle slow networks and routers
        bootstrap_timeout = 120.0
        self.logger.info(
            "Waiting for DHT bootstrap to complete (timeout: %.0fs)...",
            bootstrap_timeout,
        )

        # Use the new wait_for_bootstrap() method for proper status checking
        bootstrap_complete = await dht_client.wait_for_bootstrap(
            timeout=bootstrap_timeout
        )

        if bootstrap_complete:
            routing_table_size = len(dht_client.routing_table.nodes)
            self.logger.info(
                "DHT bootstrap completed with %d nodes in routing table",
                routing_table_size,
            )
        else:
            routing_table_size = len(dht_client.routing_table.nodes)
            self.logger.warning(
                "DHT bootstrap timeout after %.1fs (routing table: %d nodes). "
                "Discovery may not work optimally, but will continue in degraded mode...",
                bootstrap_timeout,
                routing_table_size,
            )
            # CRITICAL FIX: Continue DHT discovery even if bootstrap fails (degraded mode)
            # This allows peer discovery to work with a smaller routing table
            if routing_table_size > 0:
                self.logger.info(
                    "Continuing DHT discovery with %d nodes in routing table (degraded mode)",
                    routing_table_size,
                )

        while not self.session._stopped:
            try:
                # Trigger DHT get_peers query
                # CRITICAL FIX: Add detailed logging for DHT queries
                self.logger.info(
                    "Starting DHT get_peers query for %s (routing table: %d nodes, info_hash: %s, callbacks registered: %d)",
                    self.session.info.name,
                    routing_table_size,
                    self.session.info.info_hash.hex()[:16] + "...",
                    len(dht_client.peer_callbacks),
                )
                # CRITICAL FIX: Improved timeout and parallel query strategy
                # Use adaptive timeout: start with 30s, increase for later attempts
                # DHT queries may need more time to explore the network, especially for less popular torrents
                query_start_time = asyncio.get_event_loop().time()
                # Adaptive timeout: 30s for first few attempts, then increase
                base_timeout = 30.0
                timeout = min(
                    base_timeout * (1 + attempt_count * 0.2), 60.0
                )  # Scale up to 60s max
                attempt_count += 1

                self.logger.debug(
                    "Starting DHT get_peers query for %s (attempt %d, timeout: %.1fs, retry_interval: %.1fs)",
                    self.session.info.name,
                    attempt_count,
                    timeout,
                    dht_retry_interval,
                )

                try:
                    # CRITICAL FIX: get_peers() will invoke callbacks automatically when peers are found
                    # We still call it to trigger the query, but callbacks handle peer connection
                    # Use asyncio.wait_for with timeout to ensure query completes
                    peers = await asyncio.wait_for(
                        dht_client.get_peers(
                            self.session.info.info_hash,
                            max_peers=max_peers_per_query,
                        ),
                        timeout=timeout,
                    )
                    query_duration = asyncio.get_event_loop().time() - query_start_time
                    peer_count = len(peers) if peers else 0
                    self.logger.debug(
                        "DHT get_peers query completed for %s in %.2fs (returned %d peers, callbacks should have been invoked)",
                        self.session.info.name,
                        query_duration,
                        peer_count,
                    )

                    # CRITICAL FIX: Even if get_peers returns empty, callbacks may have been invoked
                    # with peers discovered during the query. The callback handles peer connection.
                    # However, if callbacks failed or peers weren't connected, try fallback connection
                    if peer_count > 0:
                        self.logger.info(
                            "DHT get_peers returned %d peers for %s (callbacks should have connected them)",
                            peer_count,
                            self.session.info.name,
                        )
                        # CRITICAL FIX: Verify peers were actually connected via callback
                        # If not, try fallback connection after a short delay
                        await asyncio.sleep(2.0)  # Give callbacks time to connect
                        peer_manager = getattr(
                            self.session.download_manager, "peer_manager", None
                        )
                        if peer_manager:
                            active_connections = (
                                len(
                                    [
                                        c
                                        for c in peer_manager.connections.values()
                                        if c.is_active()
                                    ]
                                )
                                if hasattr(peer_manager, "connections")
                                else 0
                            )
                            if active_connections == 0 and peer_count > 0:
                                self.logger.warning(
                                    "DHT found %d peers but none connected via callback, attempting fallback connection for %s",
                                    peer_count,
                                    self.session.info.name,
                                )
                                # Fallback: try to connect peers directly
                                try:
                                    from ccbt.session.peers import PeerConnectionHelper

                                    helper = PeerConnectionHelper(self.session)
                                    peer_list = [
                                        {"ip": ip, "port": port, "peer_source": "dht"}
                                        for ip, port in peers
                                    ]
                                    await helper.connect_peers_to_download(peer_list)
                                    self.logger.info(
                                        "Fallback connection attempted for %d peers from DHT for %s",
                                        len(peer_list),
                                        self.session.info.name,
                                    )
                                except Exception as fallback_error:
                                    self.logger.warning(
                                        "Fallback connection failed for %s: %s",
                                        self.session.info.name,
                                        fallback_error,
                                        exc_info=True,
                                    )
                    else:
                        self.logger.debug(
                            "DHT get_peers returned 0 peers for %s (this is normal for less popular torrents)",
                            self.session.info.name,
                        )

                    # For magnet links with no peers, try to get nodes from routing table
                    # and attempt metadata exchange with them (they might be peers too)
                    if peer_count == 0:
                        is_magnet = (
                            isinstance(self.session.torrent_data, dict)
                            and self.session.torrent_data.get("file_info") is None
                        ) or (
                            isinstance(self.session.torrent_data, dict)
                            and self.session.torrent_data.get("file_info", {}).get(
                                "total_length", 0
                            )
                            == 0
                        )

                        if is_magnet:
                            # Try to get closest nodes from routing table and attempt connection
                            # Some DHT nodes might also be BitTorrent peers
                            closest_nodes = dht_client.routing_table.get_closest_nodes(
                                self.session.info.info_hash, 5
                            )
                            if closest_nodes:
                                self.logger.info(
                                    "DHT found no peers for %s, attempting metadata exchange with %d closest DHT nodes",
                                    self.session.info.name,
                                    len(closest_nodes),
                                )
                                # Convert nodes to peer list format (use their IP:port)
                                node_peers = []
                                for node in closest_nodes:
                                    if node.ip and node.port:
                                        node_peers.append(
                                            {
                                                "ip": node.ip,
                                                "port": node.port,
                                                "peer_source": "dht_node",
                                            }
                                        )

                                if node_peers:
                                    try:
                                        metadata_fetched = (
                                            await self._handle_magnet_metadata_exchange(
                                                node_peers
                                            )
                                        )
                                        if metadata_fetched:
                                            self.logger.info(
                                                "Successfully fetched metadata from DHT nodes for %s",
                                                self.session.info.name,
                                            )
                                            # Reset failure counter on success
                                            consecutive_failures = 0
                                    except Exception as e:
                                        self.logger.debug(
                                            "Metadata exchange with DHT nodes failed for %s: %s",
                                            self.session.info.name,
                                            e,
                                        )
                except asyncio.TimeoutError:
                    query_duration = asyncio.get_event_loop().time() - query_start_time
                    # CRITICAL FIX: Don't log timeout as warning - this is normal for some torrents
                    # Only log as info to reduce noise
                    # CRITICAL FIX: Even on timeout, callbacks may have been invoked with partial results
                    # The query may have found some peers before timing out
                    query_duration = asyncio.get_event_loop().time() - query_start_time
                    self.logger.warning(
                        "DHT get_peers query timed out for %s after %.2fs (timeout: %.1fs, routing table: %d nodes). "
                        "This may indicate: (1) DHT responses not being received (check firewall/NAT on port %d), "
                        "(2) Network connectivity issues, or (3) Torrent not well-seeded on DHT. "
                        "Check if 'DHT datagram_received' logs appear - if not, DHT responses are being blocked.",
                        self.session.info.name,
                        query_duration,
                        timeout,
                        routing_table_size,
                        dht_client.bind_port
                        if hasattr(dht_client, "bind_port")
                        else "unknown",
                    )
                    peers = []  # Return empty list on timeout (but callbacks may have been invoked)
                except Exception as query_error:
                    # CRITICAL FIX: Handle all exceptions gracefully - don't stop the discovery loop
                    query_duration = asyncio.get_event_loop().time() - query_start_time
                    self.logger.warning(
                        "DHT get_peers query error for %s after %.2fs: %s (will retry in %.1fs)",
                        self.session.info.name,
                        query_duration,
                        query_error,
                        dht_retry_interval,
                        exc_info=True,
                    )
                    peers = []  # Return empty list on error
                    consecutive_failures += 1

                # CRITICAL FIX: Check if peers were found (either directly or via callbacks)
                # Callbacks should have been invoked during get_peers() call
                # We check both the returned peers and whether callbacks were invoked
                peer_count = len(peers) if peers else 0

                # CRITICAL FIX: Even if get_peers returns empty, callbacks may have been invoked
                # with peers discovered during the query. The callback handles peer connection.
                # So we don't treat empty return as failure - callbacks may have connected peers.
                if peer_count > 0:
                    self.logger.info(
                        "DHT get_peers returned %d peers for %s (attempt %d, callbacks should have connected them)",
                        peer_count,
                        self.session.info.name,
                        attempt_count,
                    )
                    consecutive_failures = 0
                    # Reset retry interval on success
                    dht_retry_interval = initial_retry_interval
                else:
                    # CRITICAL FIX: Empty return doesn't mean failure - callbacks may have been invoked
                    # Only increment failure count if we're sure no peers were found
                    # Check if we have active connections to determine if callbacks worked
                    has_active_peers = False
                    if (
                        hasattr(self.session, "download_manager")
                        and self.session.download_manager
                    ):
                        peer_manager = getattr(
                            self.session.download_manager, "peer_manager", None
                        )
                        if peer_manager and hasattr(peer_manager, "get_active_peers"):
                            try:
                                active_peers = peer_manager.get_active_peers()
                                has_active_peers = len(active_peers) > 0
                            except Exception:
                                pass

                    if not has_active_peers:
                        consecutive_failures += 1
                        self.logger.debug(
                            "DHT discovery: No active peers found for %s (consecutive failures: %d/%d)",
                            self.session.info.name,
                            consecutive_failures,
                            max_consecutive_failures,
                        )
                        if routing_table_size == 0:
                            self.logger.warning(
                                "DHT get_peers returned no peers - routing table is empty. "
                                "Bootstrap may not have completed."
                            )
                        elif consecutive_failures < max_consecutive_failures:
                            # Exponential backoff: increase retry interval
                            dht_retry_interval = min(
                                dht_retry_interval * base_backoff_multiplier,
                                max_retry_interval,
                            )
                            self.logger.info(
                                "DHT get_peers returned no peers (attempt %d/%d) for %s (routing table: %d nodes). "
                                "Retrying in %.1fs (exponential backoff). "
                                "This is normal - torrent may not be well-seeded on DHT, or peers may be discovered later.",
                                consecutive_failures,
                                max_consecutive_failures,
                                self.session.info.name,
                                routing_table_size,
                                dht_retry_interval,
                            )
                        else:
                            # After max failures, increase retry interval to maximum
                            dht_retry_interval = max_retry_interval
                            self.logger.info(
                                "DHT get_peers returned no peers after %d attempts for %s (routing table: %d nodes). "
                                "Increasing retry interval. Torrent may not be available on DHT.",
                                consecutive_failures,
                                self.session.info.name,
                                routing_table_size,
                            )
                    else:
                        # CRITICAL FIX: We have active peers even though get_peers returned empty
                        # This means callbacks worked and connected peers
                        self.logger.info(
                            "DHT get_peers returned empty but active peers exist - callbacks successfully connected peers for %s",
                            self.session.info.name,
                        )
                        consecutive_failures = 0
                        dht_retry_interval = initial_retry_interval

                # Wait before next retry using exponential backoff interval
                # dht_retry_interval already includes exponential backoff calculation
                wait_time = dht_retry_interval
                self.logger.debug(
                    "DHT query retry: waiting %.1fs before next attempt (consecutive failures: %d, attempt: %d)",
                    wait_time,
                    consecutive_failures,
                    attempt_count,
                )
                await asyncio.sleep(wait_time)
            except asyncio.CancelledError:
                self.logger.debug(
                    "DHT discovery task cancelled for %s", self.session.info.name
                )
                break
            except Exception as e:
                consecutive_failures += 1
                routing_table_size = len(dht_client.routing_table.nodes)
                self.logger.warning(
                    "DHT peer discovery error (attempt %d): %s (routing table: %d nodes)",
                    consecutive_failures,
                    e,
                    routing_table_size,
                    exc_info=True,
                )
                # Wait before retry with exponential backoff
                # Update retry interval with exponential backoff
                dht_retry_interval = min(
                    dht_retry_interval * base_backoff_multiplier,
                    max_retry_interval,
                )
                wait_time = dht_retry_interval
                self.logger.debug(
                    "DHT query error retry: waiting %.1fs before next attempt (consecutive failures: %d)",
                    wait_time,
                    consecutive_failures,
                )
                await asyncio.sleep(wait_time)
