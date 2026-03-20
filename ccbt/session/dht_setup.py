"""DHT discovery setup and peer discovery orchestration."""

from __future__ import annotations

import asyncio
import contextlib
import time
from typing import Any

from ccbt.monitoring import get_metrics_collector
from ccbt.session.swarm_stability_defaults import PEER_DISCOVERY_DEFAULTS


class DHTDiscoverySetup:
    """Sets up and manages DHT peer discovery for a torrent session."""

    def __init__(self, session: Any) -> None:
        """Initialize DHT discovery setup.

        Args:
            session: AsyncTorrentSession instance

        """
        self.session = session
        self.logger = session.logger
        discovery_defaults = PEER_DISCOVERY_DEFAULTS
        discovery_config = getattr(session, "config", None)
        discovery_settings = getattr(discovery_config, "discovery", None)

        # IMPROVEMENT: Track DHT query metrics
        self._dht_query_metrics = {
            "total_queries": 0,
            "total_peers_found": 0,
            "query_depths": [],
            "nodes_queried": [],
            "query_durations": [],
            "bootstrap_success_count": 0,
            "bootstrap_failure_count": 0,
            "last_bootstrap_reason": "",
            "last_bootstrap_failure_reason": "",
            "last_zero_node_lookup_at": 0.0,
            "last_query": {
                "duration": 0.0,
                "peers_found": 0,
                "depth": 0,
                "nodes_queried": 0,
            },
        }
        self._aggressive_mode = False
        # Note: Track last DHT query time to enforce minimum delay between queries
        # This prevents overwhelming the DHT network and getting blacklisted
        self._last_dht_query_time = 0.0
        self._min_dht_query_interval = (
            15.0  # Minimum 15 seconds between DHT queries (prevents peer blacklisting)
        )
        self._empty_routing_cycles = 0
        self._query_zero_nodes_cycles = 0
        self._health_state = "bootstrapping"
        self._last_rebootstrap_attempt = 0.0
        self._rebootstrap_cooldown = float(
            getattr(
                discovery_settings,
                "bootstrap_retry_memo_ttl_s",
                discovery_defaults["bootstrap_retry_memo_ttl_s"],
            )
        )
        self._low_peer_threshold = int(
            getattr(
                discovery_settings,
                "low_peer_threshold",
                discovery_defaults["low_peer_threshold"],
            )
        )
        self._low_peer_suppression_window_s = float(
            getattr(
                discovery_settings,
                "low_peer_suppression_window_s",
                discovery_defaults["low_peer_suppression_window_s"],
            )
        )
        self._dht_zero_state_reprobe_wait_s = float(
            getattr(
                discovery_settings,
                "dht_zero_state_reprobe_wait_s",
                discovery_defaults["dht_zero_state_reprobe_wait_s"],
            )
        )
        self._dht_bootstrap_memo_ttl_s = float(
            getattr(
                discovery_settings,
                "dht_bootstrap_memo_ttl_s",
                discovery_defaults["dht_bootstrap_memo_ttl_s"],
            )
        )
        self._bootstrap_retry_memo_ttl_s = float(
            getattr(
                discovery_settings,
                "bootstrap_retry_memo_ttl_s",
                discovery_defaults["bootstrap_retry_memo_ttl_s"],
            )
        )
        self._dht_bootstrap_retries_max = int(
            getattr(
                discovery_settings,
                "dht_bootstrap_retries_max",
                discovery_defaults["dht_bootstrap_retries_max"],
            )
        )
        self._dht_empty_state_backoff_factor = float(
            getattr(
                discovery_settings,
                "dht_empty_state_backoff_factor",
                discovery_defaults["dht_empty_state_backoff_factor"],
            )
        )
        self._dht_batch_wait_defer_cycles = int(
            getattr(
                discovery_settings,
                "dht_batch_wait_defer_cycles",
                3,
            )
        )
        self._batch_wait_force_count = 0
        self._bootstrap_retry_attempts: dict[str, int] = {}
        self._bootstrap_retry_last_attempt: dict[str, float] = {}

    def _set_health_state(self, state: str) -> None:
        """Track the current DHT health state for diagnostics and recovery."""
        self._health_state = state

    def _normalize_bootstrap_reason(self, reason: str) -> str:
        """Normalize bootstrap reason for memoized recovery attempts."""
        if reason.startswith("empty_routing_table"):
            return "empty_routing_table"
        if reason.startswith("query_zero_nodes"):
            return "query_zero_nodes"
        return reason

    def _prune_bootstrap_retry_memo(self, now: float) -> None:
        """Remove stale bootstrap retries from dedupe bookkeeping."""
        for reason_key in list(self._bootstrap_retry_last_attempt):
            ttl = (
                self._dht_bootstrap_memo_ttl_s
                if reason_key == "empty_routing_table"
                else self._bootstrap_retry_memo_ttl_s
            )
            if now - self._bootstrap_retry_last_attempt.get(reason_key, 0.0) > ttl:
                self._bootstrap_retry_last_attempt.pop(reason_key, None)
                self._bootstrap_retry_attempts.pop(reason_key, None)

    def _can_attempt_bootstrap_recovery(self, reason: str) -> bool:
        """Apply dedupe caps before attempting rebootstrap."""
        now = time.monotonic()
        self._prune_bootstrap_retry_memo(now)
        reason_key = self._normalize_bootstrap_reason(reason)

        if now - self._last_rebootstrap_attempt < self._rebootstrap_cooldown:
            return False

        attempt_count = self._bootstrap_retry_attempts.get(reason_key, 0)
        if attempt_count >= self._dht_bootstrap_retries_max:
            self.logger.debug(
                "DHT rebootstrap dedupe suppressed due retry limit: reason=%s (attempts=%d)",
                reason_key,
                attempt_count,
            )
            return False

        ttl = (
            self._dht_bootstrap_memo_ttl_s
            if reason_key == "empty_routing_table"
            else self._bootstrap_retry_memo_ttl_s
        )
        last_attempt = self._bootstrap_retry_last_attempt.get(reason_key, 0.0)
        if now - last_attempt < ttl:
            self.logger.debug(
                "DHT rebootstrap dedupe suppressed: reason=%s (last_attempt=%.1fs ago, ttl=%.1fs)",
                reason_key,
                now - last_attempt,
                ttl,
            )
            return False

        self._last_rebootstrap_attempt = now
        self._bootstrap_retry_attempts[reason_key] = attempt_count + 1
        self._bootstrap_retry_last_attempt[reason_key] = now
        return True

    async def _maybe_rebootstrap(self, dht_client: Any, reason: str) -> bool:
        """Attempt a throttled DHT rebootstrap when the routing state is degraded."""
        if not hasattr(dht_client, "rebootstrap"):
            return False
        if not self._can_attempt_bootstrap_recovery(reason):
            return False
        self._set_health_state("recovering")
        self.logger.warning("DHT recovery: rebootstrap triggered (%s)", reason)
        try:
            rebootstrap_result = dht_client.rebootstrap()
            if asyncio.iscoroutine(rebootstrap_result):
                success = await rebootstrap_result
            else:
                success = bool(rebootstrap_result)
        except Exception as exc:
            self._set_health_state("stalled")
            self.logger.warning("DHT rebootstrap failed (%s): %s", reason, exc)
            return False
        self._set_health_state("healthy" if success else "degraded")
        if success:
            reason_key = self._normalize_bootstrap_reason(reason)
            self._bootstrap_retry_attempts.pop(reason_key, None)
        return bool(success)

    async def _ensure_bootstrap_ready(
        self,
        dht_client: Any,
        *,
        reason: str,
        timeout: float,
        min_nodes: int = 1,
    ) -> int:
        """Ensure the DHT has at least a minimal routing table before querying."""
        routing_nodes = getattr(getattr(dht_client, "routing_table", None), "nodes", [])
        routing_table_size = len(routing_nodes)
        if routing_table_size >= min_nodes:
            return routing_table_size

        self.logger.info(
            "DHT bootstrap required for %s (routing table: %d nodes, min required: %d)",
            reason,
            routing_table_size,
            min_nodes,
        )
        bootstrap_succeeded = False
        try:
            if hasattr(dht_client, "rebootstrap"):
                bootstrap_succeeded = await asyncio.wait_for(
                    dht_client.rebootstrap(),
                    timeout=timeout,
                )
            elif hasattr(dht_client, "wait_for_bootstrap"):
                bootstrap_succeeded = await dht_client.wait_for_bootstrap(
                    timeout=timeout
                )
        except asyncio.TimeoutError:
            self.logger.warning(
                "DHT bootstrap timed out for %s after %.1fs",
                reason,
                timeout,
            )
        except Exception as bootstrap_error:
            self.logger.warning(
                "DHT bootstrap failed for %s: %s",
                reason,
                bootstrap_error,
            )

        routing_table_size = len(
            getattr(getattr(dht_client, "routing_table", None), "nodes", [])
        )
        query_metrics = self._dht_query_metrics
        query_metrics["bootstrap_success_count"] = int(
            getattr(dht_client, "bootstrap_success_count", 0) or 0
        )
        query_metrics["bootstrap_failure_count"] = int(
            getattr(dht_client, "bootstrap_failure_count", 0) or 0
        )
        query_metrics["last_bootstrap_reason"] = str(
            getattr(dht_client, "last_bootstrap_reason", "")
        )
        query_metrics["last_bootstrap_failure_reason"] = str(
            getattr(dht_client, "last_bootstrap_failure_reason", "")
        )
        query_metrics["last_zero_node_lookup_at"] = float(
            getattr(dht_client, "last_zero_node_lookup_at", 0.0) or 0.0
        )
        if routing_table_size >= min_nodes:
            self._set_health_state("healthy")
            self.logger.info(
                "DHT bootstrap ready for %s (routing table: %d nodes, success=%s)",
                reason,
                routing_table_size,
                bootstrap_succeeded,
            )
        else:
            self._set_health_state("stalled")
            self.logger.warning(
                "DHT bootstrap did not yield enough routing nodes for %s (routing table: %d nodes, success=%s, failure_reason=%s)",
                reason,
                routing_table_size,
                bootstrap_succeeded,
                getattr(dht_client, "last_bootstrap_failure_reason", "unknown"),
            )
        return routing_table_size

    async def _get_swarm_recovery_state(self) -> dict[str, Any]:
        """Return swarm recovery state, even for lightweight session stubs used in tests."""
        if hasattr(self.session, "get_swarm_recovery_state"):
            return await self.session.get_swarm_recovery_state()

        metadata_incomplete = bool(
            getattr(
                getattr(self.session, "piece_manager", None),
                "_metadata_incomplete",
                False,
            )
        )
        peer_manager = getattr(
            getattr(self.session, "download_manager", None), "peer_manager", None
        )
        active_peers = 0
        if peer_manager and hasattr(peer_manager, "get_active_peers"):
            with contextlib.suppress(Exception):
                active_peers = len(peer_manager.get_active_peers())
        elif peer_manager and hasattr(peer_manager, "connections"):
            with contextlib.suppress(Exception):
                active_peers = len(peer_manager.connections)

        return {
            "metadata_incomplete": metadata_incomplete,
            "active_peers": active_peers,
            "productive_peers": 0,
            "requestable_peers": 0,
            "peers_with_piece_info": 0,
            "active_block_requests": 0,
            "download_rate": 0.0,
        }

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

        # Note: Set up DHT discovery if DHT client exists, even if not fully bootstrapped yet
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

            # Note: Set peer_manager reference on DHT client for adaptive timeout calculation
            # This allows DHT queries to use longer timeouts in desperation mode (few peers)
            dht_client = self.session.session_manager.dht_client
            if dht_client and hasattr(dht_client, "set_peer_manager"):
                # Get peer_manager from download_manager if available
                peer_manager = None
                if self.session.is_ready():
                    peer_manager = getattr(
                        self.session.download_manager, "peer_manager", None
                    )

                if peer_manager:
                    dht_client.set_peer_manager(peer_manager)
                    self.logger.debug(
                        "Set peer_manager on DHT client for adaptive timeout calculation"
                    )
                else:
                    # Peer manager not ready yet, will be set later when available
                    self.logger.debug(
                        "Peer manager not ready yet, DHT client will use default timeouts until peer_manager is available"
                    )
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
                # Note: Add defensive checks for session readiness before processing peers
                # Check if session is stopped/not ready
                if not self.session.is_ready():
                    return
                if self.session.info.status == "stopped":
                    self.logger.debug(
                        "DHT callback received %d peer(s) for %s but session is stopped, ignoring",
                        len(peers),
                        self.session.info.name,
                    )
                    return

                # Note: Add detailed logging for DHT peer discovery
                self.logger.info(
                    "🔍 DHT CALLBACK: Discovered %d peer(s) for torrent %s (info_hash: %s)",
                    len(peers),
                    self.session.info.name,
                    self.session.info.info_hash.hex()[:16],
                )
                if peers:
                    # Log first few peers for debugging
                    sample_peers = peers[:3]
                    self.logger.debug(
                        "DHT peer samples: %s",
                        ", ".join(f"{ip}:{port}" for ip, port in sample_peers),
                    )

                # Note: Check download_manager exists with retry logic
                if not self.session.download_manager:
                    self.logger.warning(
                        "DHT peers discovered but session not ready for %s (session may not be ready yet)",
                        self.session.info.name,
                    )
                    # Retry logic: wait a bit and check again (for timing issues)
                    await asyncio.sleep(0.5)
                    if not self.session.is_ready():
                        self.logger.warning(
                            "DHT peers discovered but download_manager still None after retry for %s, giving up",
                            self.session.info.name,
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
                with contextlib.suppress(Exception):
                    self.session.record_discovered_peers(peer_list)

                if not peer_list:
                    self.logger.debug(
                        "DHT peer list is empty after conversion for %s",
                        self.session.info.name,
                    )
                    return

                # Note: Log peer conversion details
                self.logger.debug(
                    "Converted %d DHT peer(s) to peer_list format for %s",
                    len(peer_list),
                    self.session.info.name,
                )

                # Note: For magnet links, try metadata exchange first if metadata not available
                metadata_fetched = await self._handle_magnet_metadata_exchange(
                    peer_list
                )

                # Ensure download is started
                download_started = getattr(
                    self.session.download_manager, "_download_started", False
                )
                if not download_started:
                    # Note: Check if download is already starting to prevent duplicate calls
                    # This prevents infinite loops when DHT callback is triggered multiple times
                    is_starting = getattr(self.session, "_dht_download_starting", False)
                    if not is_starting:
                        await self._start_download_with_dht_peers(
                            peer_list, metadata_fetched
                        )
                    else:
                        self.logger.debug(
                            "Download start already in progress, skipping duplicate call from DHT callback for %d peers",
                            len(peer_list),
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
                        # Note: Verify session is ready before attempting connection
                        # Add retry logic for timing issues where session may not be ready yet
                        if not self.session.is_ready():
                            self.logger.warning(
                                "Session not ready for %s, waiting up to 2 seconds...",
                                self.session.info.name,
                            )
                            for retry in range(4):  # 4 retries * 0.5s = 2 seconds total
                                await asyncio.sleep(0.5)
                                if self.session.is_ready():
                                    self.logger.info(
                                        "Session ready for %s after %.1fs",
                                        self.session.info.name,
                                        (retry + 1) * 0.5,
                                    )
                                    break
                            if not self.session.is_ready():
                                self.logger.warning(
                                    "peer_manager still not ready for %s after retries, queuing %d peers for generic drain",
                                    self.session.info.name,
                                    len(peer_list),
                                )
                                # Use generic queue so PeerConnectionHelper drains them when ready
                                await helper.connect_peers_to_download(peer_list)
                                return

                        self.logger.info(
                            "🔗 DHT CONNECTION: Attempting to connect %d DHT-discovered peer(s) for %s",
                            len(peer_list),
                            self.session.info.name,
                        )
                        await helper.connect_peers_to_download(peer_list)
                        self.logger.info(
                            "✅ DHT CONNECTION: Successfully initiated connection to %d DHT-discovered peers for %s",
                            len(peer_list),
                            self.session.info.name,
                        )
                        # Note: Verify peer_manager exists and check connection status after a delay
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
                        # Queue to generic _queued_peers so they are drained when peer_manager is ready
                        import time as _time

                        now = _time.time()
                        for peer in peer_list:
                            peer_copy = dict(peer)
                            peer_copy["_queued_at"] = now
                            self.session.add_queued_peer(peer_copy)
                        self.logger.debug(
                            "Queued %d peers for retry via generic queue (total: %d)",
                            len(peer_list),
                            len(self.session.get_queued_peers()),
                        )
            except Exception:
                self.logger.exception(
                    "Critical error in DHT peer discovery handler for %s",
                    self.session.info.name,
                )
                # Note: Don't let errors stop peer discovery - log and continue
                # The discovery loop will retry on next iteration

        return on_dht_peers_discovered

    async def handle_magnet_metadata_exchange(
        self, peer_list: list[dict[str, Any]]
    ) -> bool:
        """Handle metadata exchange for magnet links. Public API for torrent_addition."""
        return await self._handle_magnet_metadata_exchange(peer_list)

    async def _merge_fetched_metadata(
        self, updated_torrent_data: dict[str, Any]
    ) -> None:
        """Merge fetched metadata into session state using the canonical update path."""
        if not isinstance(self.session.torrent_data, dict):
            return

        self.session.torrent_data.update(updated_torrent_data)
        if hasattr(self.session.download_manager, "torrent_data"):
            self.session.download_manager.torrent_data = self.session.torrent_data

        file_assembler = getattr(self.session.download_manager, "file_assembler", None)
        if file_assembler is not None:
            try:
                file_assembler.update_from_metadata(self.session.torrent_data)
                self.logger.info(
                    "Updated file assembler with new metadata for %s",
                    self.session.info.name,
                )
            except Exception as e:
                self.logger.warning(
                    "Failed to update file assembler with metadata: %s",
                    e,
                )

        piece_manager = getattr(self.session.download_manager, "piece_manager", None)
        if piece_manager is None:
            return

        if hasattr(piece_manager, "torrent_data"):
            piece_manager.torrent_data = self.session.torrent_data

        if hasattr(piece_manager, "update_from_metadata"):
            await piece_manager.update_from_metadata(updated_torrent_data)
        elif "pieces_info" in updated_torrent_data:
            pieces_info = updated_torrent_data["pieces_info"]
            if "num_pieces" in pieces_info:
                piece_manager.num_pieces = int(pieces_info["num_pieces"])
            if "piece_length" in pieces_info:
                piece_manager.piece_length = int(pieces_info["piece_length"])

        peer_manager_for_restart = getattr(
            self.session.download_manager, "peer_manager", None
        )
        if hasattr(piece_manager, "start_download"):
            try:
                await piece_manager.start_download(peer_manager_for_restart)
                self.logger.info(
                    "Restarted piece manager after metadata fetch for %s (num_pieces=%d, pieces_count=%d)",
                    self.session.info.name,
                    getattr(piece_manager, "num_pieces", 0),
                    len(getattr(piece_manager, "pieces", [])),
                )
            except Exception as e:
                self.logger.warning(
                    "Error restarting piece manager download after metadata fetch: %s",
                    e,
                    exc_info=True,
                )

        num_pieces = int(getattr(piece_manager, "num_pieces", 0) or 0)
        pieces_count = len(getattr(piece_manager, "pieces", []))
        metadata_incomplete = bool(
            getattr(piece_manager, "_metadata_incomplete", False)
        )
        if num_pieces <= 0 or pieces_count != num_pieces or metadata_incomplete:
            self.logger.warning(
                "Metadata merge invariants not satisfied for %s (num_pieces=%d, pieces_count=%d, metadata_incomplete=%s)",
                self.session.info.name,
                num_pieces,
                pieces_count,
                metadata_incomplete,
            )

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

                    # Note: Increase metadata fetching timeout to 60 seconds
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
                        from typing import cast

                        from ccbt.core.magnet import (
                            build_torrent_data_from_metadata,
                        )

                        # Type cast: metadata is dict[bytes, Any] but function accepts dict[bytes | str, Any]
                        updated_torrent_data = build_torrent_data_from_metadata(
                            self.session.info.info_hash,
                            cast("dict[bytes | str, Any]", metadata),
                        )
                        await self._merge_fetched_metadata(updated_torrent_data)
                        metadata_fetched = True

                        # Note: Notify download manager that metadata is now available
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
                        # Apply BEP 53 file selection from magnet URI (so / x.pe) if present
                        await self._apply_bep53_after_metadata()
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

    async def _apply_bep53_after_metadata(self) -> None:
        """Apply BEP 53 file selection from magnet URI (so / x.pe) after metadata merge."""
        try:
            await self.session.apply_magnet_file_selection_if_needed()
        except Exception as e:
            self.logger.debug(
                "Could not apply magnet file selection after metadata: %s",
                e,
            )

    async def _start_download_with_dht_peers(
        self, peer_list: list[dict[str, Any]], metadata_fetched: bool
    ) -> None:
        """Start download with DHT-discovered peers.

        Args:
            peer_list: List of peer dictionaries
            metadata_fetched: Whether metadata was successfully fetched

        """
        # Note: Prevent duplicate calls to _start_download_with_dht_peers
        # This prevents infinite loops when DHT callback is triggered multiple times
        async with self.session.dht_download_start_lock:
            # Check if download is already started
            download_started = getattr(
                self.session.download_manager, "_download_started", False
            )
            if download_started:
                self.logger.debug(
                    "Download already started, skipping _start_download_with_dht_peers for %d peers",
                    len(peer_list),
                )
                return

            # Check if we're already starting download (prevent concurrent calls)
            if getattr(self.session, "_dht_download_starting", False):  # type: ignore[attr-defined]
                self.logger.debug(
                    "Download start already in progress, skipping duplicate call for %d peers",
                    len(peer_list),
                )
                return

            # Mark as starting to prevent concurrent calls
            self.session.dht_download_starting = True

        # Note: Validate torrent_data is not a list before calling start_download
        if isinstance(self.session.torrent_data, list):
            self.logger.error(
                "Cannot start download: torrent_data is a list, not dict or TorrentInfo."
            )
            # Clear the starting flag before returning
            async with self.session.dht_download_start_lock:
                self.session.dht_download_starting = False
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

            # Note: Set status to 'downloading' immediately after start_download() regardless of peer count
            self.session.info.status = "downloading"
            self.logger.info(
                "Status set to 'downloading' immediately after start_download() with %d DHT-discovered peers",
                len(peer_list),
            )

            # Note: Set peer_manager reference on DHT client for adaptive timeout calculation
            # This allows DHT queries to use longer timeouts in desperation mode (few peers)
            dht_client = self.session.session_manager.dht_client
            if dht_client and hasattr(dht_client, "set_peer_manager"):
                peer_manager = getattr(
                    self.session.download_manager, "peer_manager", None
                )
                if peer_manager:
                    dht_client.set_peer_manager(peer_manager)
                    self.logger.debug(
                        "Set peer_manager on DHT client for adaptive timeout calculation (during download start)"
                    )

            # Set up session callbacks on peer_manager
            if self.session.download_manager.peer_manager:
                # Use download_manager callbacks (they exist there, not on session)
                # Access download_manager callbacks (same pattern as peers.py)
                if hasattr(self.session.download_manager, "_on_peer_connected"):
                    self.session.download_manager.peer_manager.on_peer_connected = (
                        self.session.download_manager._on_peer_connected  # noqa: SLF001
                    )
                if hasattr(self.session.download_manager, "_on_peer_disconnected"):
                    self.session.download_manager.peer_manager.on_peer_disconnected = (
                        self.session.download_manager._on_peer_disconnected  # noqa: SLF001
                    )
                if hasattr(self.session.download_manager, "_on_piece_received"):
                    self.session.download_manager.peer_manager.on_piece_received = (
                        self.session.download_manager._on_piece_received  # noqa: SLF001
                    )
                if hasattr(self.session.download_manager, "_on_bitfield_received"):
                    self.session.download_manager.peer_manager.on_bitfield_received = (
                        self.session.download_manager._on_bitfield_received  # noqa: SLF001
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
        finally:
            # Note: Clear the starting flag even if exception occurs
            # This allows retry if download start fails
            async with self.session.dht_download_start_lock:
                self.session.dht_download_starting = False

    def _create_dedup_wrapper(self, on_dht_peers_discovered: Any) -> Any:
        """Create deduplication wrapper for peer discovery.

        Args:
            on_dht_peers_discovered: Original peer discovery handler

        Returns:
            Wrapped handler with deduplication

        """

        # Track recently processed peers to avoid duplicate connection attempts
        async def on_dht_peers_discovered_with_dedup(
            peers: list[tuple[str, int]],
        ) -> None:
            """Process DHT-discovered peers with deduplication."""
            if not peers:
                return

            # Filter out recently processed peers
            async with self.session.get_recently_processed_peers_lock():
                # Clean up old entries (older than 5 minutes)
                # Keep set size manageable by removing entries periodically
                self.session.cleanup_recently_processed_peers(keep_count=500)

                # Filter out already processed peers
                new_peers = [
                    peer
                    for peer in peers
                    if not self.session.is_peer_recently_processed(peer)
                ]

                # Mark new peers as processed
                for peer in new_peers:
                    self.session.add_recently_processed_peer(peer)

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
        # Note: Add callback invocation counter to verify callbacks are called
        if not hasattr(self.session, "_dht_callback_invocation_count"):
            self.session.dht_callback_invocation_count = 0

        # Register DHT callback (DHT expects sync callback, wrap it)
        def dht_callback_wrapper(peers: list[tuple[str, int]]) -> None:
            """Convert sync DHT callback to an async task."""
            # Note: Increment callback invocation counter
            self.session.increment_dht_callback_count()

            # Note: Add logging to verify callback is being called
            self.logger.info(
                "DHT callback triggered for %s: received %d peer(s) from DHT client (info_hash: %s, invocation #%d)",
                self.session.info.name,
                len(peers),
                self.session.info.info_hash.hex()[:16] + "...",
                self.session.dht_callback_invocation_count,
            )

            # Note: Add error handling for task creation and execution
            def task_done_callback(task: asyncio.Task) -> None:
                """Handle task completion and log errors."""
                try:
                    # Check if task raised an exception
                    if task.exception():
                        self.logger.error(
                            "DHT peer callback task failed for %s (info_hash: %s): %s",
                            self.session.info.name,
                            self.session.info.info_hash.hex()[:16] + "...",
                            task.exception(),
                            exc_info=task.exception(),
                        )
                except Exception:
                    self.logger.exception(
                        "Failed to handle DHT callback task completion for %s",
                        self.session.info.name,
                    )

            if not peers:
                # Note: Still process empty peer list - this indicates query completed
                # The discovery loop needs to know the query finished even if no peers found
                self.logger.info(
                    "DHT callback received empty peer list for %s (query completed, no peers found)",
                    self.session.info.name,
                )
                # Still create task to notify discovery loop that query completed
                # This allows the discovery loop to continue and retry
                try:
                    task = asyncio.create_task(
                        on_dht_peers_discovered_with_dedup(peers)
                    )
                    self.session.add_dht_peer_task(task)
                    task.add_done_callback(self.session.remove_dht_peer_task)
                    task.add_done_callback(task_done_callback)
                except Exception:
                    self.logger.exception(
                        "Failed to create DHT peer callback task for empty peer list for %s",
                        self.session.info.name,
                    )
                return

            # Verify download manager exists before processing
            if not self.session.download_manager:
                self.logger.warning(
                    "DHT callback received %d peers but download_manager is None for %s (session may not be ready yet)",
                    len(peers),
                    self.session.info.name,
                )
                # Note: Log peer addresses for debugging
                if peers:
                    sample_peers = peers[:5]
                    self.logger.debug(
                        "DHT peers that will be lost: %s%s",
                        ", ".join(f"{ip}:{port}" for ip, port in sample_peers),
                        "..." if len(peers) > 5 else "",
                    )
                return

            # Note: Add detailed logging before creating task
            self.logger.debug(
                "Creating async task to process %d DHT-discovered peer(s) for %s",
                len(peers),
                self.session.info.name,
            )

            # Create async task to process peers
            try:
                task = asyncio.create_task(on_dht_peers_discovered_with_dedup(peers))
                # Store task reference to avoid garbage collection
                self.session.add_dht_peer_task(task)
                task.add_done_callback(self.session.remove_dht_peer_task)
                task.add_done_callback(task_done_callback)
                self.logger.debug(
                    "Created async task to process DHT peers for %s (task count: %d)",
                    self.session.info.name,
                    len(self.session.get_dht_peer_tasks()),
                )
            except Exception:
                self.logger.exception(
                    "Failed to create DHT peer callback task for %s",
                    self.session.info.name,
                )

        # Register callback with DHT client via DiscoveryController (with info_hash filter)
        try:
            from ccbt.session.discovery import DiscoveryController
            from ccbt.session.models import SessionContext
            from ccbt.session.tasks import TaskSupervisor

            discovery_controller_cls = DiscoveryController
        except Exception:
            discovery_controller_cls = None  # type: ignore[assignment]

        if (
            discovery_controller_cls
            and self.session.session_manager
            and self.session.session_manager.dht_client
        ):
            # Use session's ctx and task_supervisor if available
            session_ctx = getattr(self.session, "ctx", None)
            task_supervisor = getattr(self.session, "_task_supervisor", None)

            if not session_ctx or not task_supervisor:
                # Fallback: create new ones if session doesn't have them
                if not task_supervisor:
                    task_supervisor = TaskSupervisor()
                if not session_ctx:
                    td = (
                        self.session.torrent_data
                        if isinstance(self.session.torrent_data, dict)
                        else {
                            "info_hash": self.session.info.info_hash,
                            "name": self.session.info.name,
                        }
                    )
                    session_ctx = SessionContext(
                        config=self.session.config,
                        torrent_data=td,
                        output_dir=self.session.output_dir,
                        info=self.session.info,
                        session_manager=self.session.session_manager,
                        logger=self.session.logger,
                        piece_manager=self.session.piece_manager,
                        checkpoint_manager=self.session.checkpoint_manager,
                    )

            # Type guard: session_ctx is guaranteed to be SessionContext here
            if not isinstance(session_ctx, SessionContext):
                msg = "session_ctx should be SessionContext after fallback creation"
                raise TypeError(msg)

            # Lazily create discovery controller
            if self.session.discovery_controller is None:
                self.session.discovery_controller = discovery_controller_cls(
                    session_ctx, task_supervisor
                )
            self.session.discovery_controller.register_dht_callback(
                self.session.session_manager.dht_client,  # type: ignore[arg-type]
                on_dht_peers_discovered_with_dedup,
                info_hash=self.session.info.info_hash,
            )
        else:
            # Fallback to direct registration if discovery controller unavailable
            # Note: Use info_hash parameter for callback filtering
            self.session.session_manager.dht_client.add_peer_callback(  # type: ignore[union-attr]
                dht_callback_wrapper,
                info_hash=self.session.info.info_hash,
            )

        # Note: Verify callback is in DHT client's peer_callbacks_by_hash after registration
        # Since we register with info_hash, the callback should be in peer_callbacks_by_hash, not peer_callbacks
        # Add retry mechanism to handle timing issues where callback may not be immediately visible
        dht_client = self.session.session_manager.dht_client
        callback_registered = False
        max_retries = 3
        retry_delay = 0.5  # 0.5 seconds between retries
        info_hash = self.session.info.info_hash

        for retry_attempt in range(max_retries):
            if retry_attempt > 0:
                # Wait before retrying (callback may not be immediately visible)
                await asyncio.sleep(retry_delay)

            if dht_client and hasattr(dht_client, "peer_callbacks_by_hash"):
                # Note: Check peer_callbacks_by_hash for info_hash-specific callbacks
                # When registered with info_hash, callback should be in peer_callbacks_by_hash[info_hash]
                try:
                    if info_hash in dht_client.peer_callbacks_by_hash:
                        hash_callbacks = dht_client.peer_callbacks_by_hash[info_hash]
                        if len(hash_callbacks) > 0:
                            callback_registered = True
                            self.logger.debug(
                                "DHT callback registered (found %d callback(s) in peer_callbacks_by_hash[%s])",
                                len(hash_callbacks),
                                info_hash.hex()[:16] + "...",
                            )
                            break
                    # Also check global callbacks as fallback (for backward compatibility)
                    if (
                        hasattr(dht_client, "peer_callbacks")
                        and len(dht_client.peer_callbacks) > 0
                    ):
                        # If callback is in global list, it might still work but is less efficient
                        self.logger.debug(
                            "DHT callback found in global peer_callbacks (not info_hash-specific, %d callbacks)",
                            len(dht_client.peer_callbacks),
                        )
                except Exception as verify_error:
                    self.logger.debug(
                        "Error verifying callback in peer_callbacks_by_hash: %s",
                        verify_error,
                    )

            if callback_registered:
                break

        if callback_registered:
            hash_callbacks_count = (
                len(dht_client.peer_callbacks_by_hash.get(info_hash, []))
                if dht_client and hasattr(dht_client, "peer_callbacks_by_hash")
                else 0
            )
            global_callbacks_count = (
                len(dht_client.peer_callbacks)
                if dht_client and hasattr(dht_client, "peer_callbacks")
                else 0
            )
            self.logger.info(
                "Registered DHT callback for %s (verified in peer_callbacks_by_hash after %d attempt(s), "
                "hash_specific=%d, global=%d, info_hash: %s)",
                self.session.info.name,
                retry_attempt + 1,
                hash_callbacks_count,
                global_callbacks_count,
                info_hash.hex()[:16] + "...",
            )
            with contextlib.suppress(Exception):
                metrics = getattr(self.session, "_peer_discovery_metrics", None)
                if isinstance(metrics, dict):
                    metrics["dht_callback_missing"] = False
        else:
            # Enhanced logging for debugging callback structure
            callback_structure_info = "unknown"
            if dht_client:
                if hasattr(dht_client, "peer_callbacks_by_hash"):
                    hash_callbacks = dht_client.peer_callbacks_by_hash.get(
                        info_hash, []
                    )
                    callback_structure_info = f"peer_callbacks_by_hash[{info_hash.hex()[:8]}...]={len(hash_callbacks)} callbacks"
                if hasattr(dht_client, "peer_callbacks"):
                    global_count = len(dht_client.peer_callbacks)
                    callback_structure_info += (
                        f", peer_callbacks={global_count} callbacks"
                    )

            self.logger.warning(
                "DHT callback registration may have failed for %s (not found in peer_callbacks_by_hash after %d attempts, info_hash: %s). "
                "DHT peer discovery may not work for this torrent. Callback structure: %s",
                self.session.info.name,
                max_retries,
                info_hash.hex()[:16] + "...",
                callback_structure_info,
            )
            with contextlib.suppress(Exception):
                metrics = getattr(self.session, "_peer_discovery_metrics", None)
                if isinstance(metrics, dict):
                    metrics["dht_callback_missing"] = True

    async def _trigger_initial_query(self) -> None:
        """Trigger immediate initial DHT get_peers query after callback registration."""
        dht_client = self.session.session_manager.dht_client
        if not dht_client:
            return

        async def trigger_initial_dht_query() -> None:
            """Trigger immediate DHT get_peers query after callback registration.

            Note: For magnet links, be more aggressive about DHT queries
            since there are no trackers initially. Query even if routing table is small.
            """
            try:
                # Small delay to ensure callback is fully registered
                await asyncio.sleep(0.1)

                routing_table_size = len(dht_client.routing_table.nodes)

                # Note: For magnet links, query even with small routing table
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
                            "(routing table empty - attempting public rebootstrap first)",
                            self.session.info.name,
                        )
                        routing_table_size = await self._ensure_bootstrap_ready(
                            dht_client,
                            reason=f"initial_query:{self.session.info.name}",
                            timeout=10.0,
                            min_nodes=1,
                        )
                        if routing_table_size <= 0:
                            self.logger.warning(
                                "Skipping initial DHT get_peers for %s because bootstrap still has no routing nodes",
                                self.session.info.name,
                            )
                            return
                    else:
                        self.logger.info(
                            "Triggering immediate DHT get_peers query for %s (routing table: %d nodes)",
                            self.session.info.name,
                            routing_table_size,
                        )

                    try:
                        # Use longer timeout for magnet links (they need more time to find peers)
                        timeout = 45.0 if is_magnet else 30.0
                        # Use normal configuration parameters for initial query (will be more aggressive if needed)
                        peers = await asyncio.wait_for(
                            dht_client.get_peers(
                                self.session.info.info_hash,
                                max_peers=50,
                                alpha=self.session.config.discovery.dht_normal_alpha,
                                k=self.session.config.discovery.dht_normal_k,
                                max_depth=self.session.config.discovery.dht_normal_max_depth,
                            ),
                            timeout=timeout,
                        )
                        if peers:
                            self.logger.info(
                                "Initial DHT query returned %d peers for %s",
                                len(peers),
                                self.session.info.name,
                            )
                            # Note: Trigger metadata exchange immediately when DHT peers are found
                            # Don't wait for tracker peers - use DHT peers for metadata exchange
                            if is_magnet:
                                self.logger.info(
                                    "Triggering immediate metadata exchange with %d DHT-discovered peers for %s",
                                    len(peers),
                                    self.session.info.name,
                                )
                                peer_list = [
                                    {"ip": ip, "port": port, "peer_source": "dht"}
                                    for ip, port in peers
                                ]
                                # Trigger metadata exchange in background task
                                metadata_task = asyncio.create_task(
                                    self._handle_magnet_metadata_exchange(peer_list)
                                )
                                # Store task reference
                                self.session.add_metadata_task(metadata_task)
                                metadata_task.add_done_callback(
                                    self.session.remove_metadata_task
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

        # Note: Ensure DHT discovery task is started
        self.logger.info(
            "🔍 DHT DISCOVERY: Creating discovery background task for %s",
            self.session.info.name,
        )
        self.session.dht_discovery_task = asyncio.create_task(
            self._run_discovery_loop(dht_client)
        )
        self.logger.info(
            "✅ DHT DISCOVERY: Discovery task started for %s (task=%s, callbacks=%d, initial interval: 15s, aggressive mode: enabled when peers < 5 or < 50%% of max)",
            self.session.info.name,
            self.session.dht_discovery_task,
            len(dht_client.peer_callbacks),
        )

    async def _run_discovery_loop(self, dht_client: Any) -> None:
        """Run periodic DHT peer discovery loop.

        Args:
            dht_client: DHT client instance

        """
        # IMPROVEMENT: Aggressive peer discovery for popular torrents
        # Adaptive retry logic based on torrent popularity and download activity
        # Standard exponential backoff: 60s → 120s → 240s → 480s → 960s → 1920s (32min max)
        initial_retry_interval = 30.0
        max_retry_interval = (
            1920.0  # Cap at 32 minutes (standard exponential backoff maximum)
        )
        base_backoff_multiplier = (
            2.0  # Standard exponential backoff multiplier (doubles each time)
        )
        dht_retry_interval = initial_retry_interval
        max_peers_per_query = 50
        consecutive_failures = 0
        max_consecutive_failures = 10  # Increased from 5 to 10
        attempt_count = 0

        # Track torrent popularity and activity
        aggressive_mode = False

        # Note: Wait for DHT bootstrap to complete (max 120 seconds for slow networks)
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
            self._set_health_state("healthy")
            self.logger.info(
                "DHT bootstrap completed with %d nodes in routing table",
                routing_table_size,
            )
        else:
            routing_table_size = len(dht_client.routing_table.nodes)
            self._set_health_state("degraded" if routing_table_size > 0 else "stalled")
            self.logger.warning(
                "DHT bootstrap timeout after %.1fs (routing table: %d nodes). "
                "Discovery may not work optimally, but will continue in degraded mode...",
                bootstrap_timeout,
                routing_table_size,
            )
            # Note: Continue DHT discovery even if bootstrap fails (degraded mode)
            # This allows peer discovery to work with a smaller routing table
            if routing_table_size > 0:
                self.logger.info(
                    "Continuing DHT discovery with %d nodes in routing table (degraded mode)",
                    routing_table_size,
                )

        # Use configurable minimum; DHT can start earlier as fallback with conservative intervals
        min_peers_before_dht = getattr(
            self.session.config.discovery,
            "min_peers_before_dht",
            10,
        )
        enable_fail_fast = getattr(
            self.session.config.network,
            "enable_fail_fast_dht",
            True,
        )
        fail_fast_timeout = getattr(
            self.session.config.network,
            "fail_fast_dht_timeout",
            30.0,
        )
        dht_started = False

        while not self.session.stopped:
            try:
                # Note: Wait for connection batches to complete before starting DHT
                # User requirement: "peer count low checks should only start basically after the first batches of connections are exhausted"
                # Check if connection batches are currently in progress
                if self.session.download_manager and hasattr(
                    self.session.download_manager, "peer_manager"
                ):
                    peer_manager = self.session.download_manager.peer_manager
                    if peer_manager:
                        connection_batches_in_progress = getattr(
                            peer_manager, "_connection_batches_in_progress", False
                        )
                        if connection_batches_in_progress:
                            self.logger.info(
                                "⏸️ DHT DISCOVERY: Connection batches are in progress. Waiting for batches to complete before starting DHT query..."
                            )
                            swarm_state = await self._get_swarm_recovery_state()
                            recovery_wait_budget = getattr(
                                self.session,
                                "recovery_wait_budget",
                                lambda *_args, **kwargs: kwargs.get("fast_wait", 2.0),
                            )
                            max_wait = recovery_wait_budget(
                                swarm_state,
                                base_wait=15.0,
                                fast_wait=2.0,
                            )
                            check_interval = 1.0  # Check every 1 second
                            waited = 0.0
                            while waited < max_wait:
                                await asyncio.sleep(check_interval)
                                waited += check_interval
                                connection_batches_in_progress = getattr(
                                    peer_manager,
                                    "_connection_batches_in_progress",
                                    False,
                                )
                                active_peer_count_during_wait = 0
                                if hasattr(peer_manager, "get_active_peers"):
                                    with contextlib.suppress(Exception):
                                        active_peer_count_during_wait = len(
                                            peer_manager.get_active_peers()
                                        )
                                swarm_state = await self._get_swarm_recovery_state()
                                fast_recovery_fn = getattr(
                                    self.session,
                                    "swarm_requires_fast_recovery",
                                    lambda state: bool(
                                        state.get("metadata_incomplete", False)
                                    )
                                    or bool(state.get("degraded_swarm", False))
                                    or not bool(
                                        state.get("has_usable_download_path", False)
                                    )
                                    or int(state.get("active_peers", 0) or 0) == 0,
                                )
                                if connection_batches_in_progress and fast_recovery_fn(
                                    swarm_state
                                ):
                                    self.logger.warning(
                                        "⏸️ DHT DISCOVERY: Connection batches remain active after %.1fs but swarm is degraded (active=%d, productive=%d, requestable=%d, piece_info=%d). Proceeding with DHT evaluation now.",
                                        waited,
                                        int(swarm_state.get("active_peers", 0)),
                                        int(swarm_state.get("productive_peers", 0)),
                                        int(swarm_state.get("requestable_peers", 0)),
                                        int(
                                            swarm_state.get("peers_with_piece_info", 0)
                                        ),
                                    )
                                    self._batch_wait_force_count = 0
                                    break
                                if (
                                    connection_batches_in_progress
                                    and active_peer_count_during_wait == 0
                                ):
                                    self.logger.warning(
                                        "⏸️ DHT DISCOVERY: Connection batches are still marked in progress after %.1fs but no active peers remain. Proceeding with DHT evaluation immediately.",
                                        waited,
                                    )
                                    self._batch_wait_force_count = 0
                                    break
                                if not connection_batches_in_progress:
                                    self.logger.info(
                                        "✅ DHT DISCOVERY: Connection batches completed after %.1fs. Checking peer count before starting DHT...",
                                        waited,
                                    )
                                    self._batch_wait_force_count = 0
                                    break
                            else:
                                active_peer_count_during_wait = 0
                                if hasattr(peer_manager, "get_active_peers"):
                                    with contextlib.suppress(Exception):
                                        active_peer_count_during_wait = len(
                                            peer_manager.get_active_peers()
                                        )
                                self.logger.warning(
                                    "⏸️ DHT DISCOVERY: Connection batches still in progress after %.1fs wait. Waiting longer...",
                                    max_wait,
                                )
                                if active_peer_count_during_wait == 0:
                                    self.logger.warning(
                                        "⏸️ DHT DISCOVERY: No active peers remain while batches are still marked in progress. Proceeding with DHT evaluation anyway.",
                                    )
                                    self._batch_wait_force_count = 0
                                    break
                                self._batch_wait_force_count += 1
                                if (
                                    self._batch_wait_force_count
                                    >= self._dht_batch_wait_defer_cycles
                                ):
                                    self.logger.warning(
                                        "⏸️ DHT DISCOVERY: Connection-batch defer reached hard cap (%d/%d). Proceeding with DHT evaluation to avoid deadlock.",
                                        self._batch_wait_force_count,
                                        self._dht_batch_wait_defer_cycles,
                                    )
                                    self._batch_wait_force_count = 0
                                    break

                                # Continue waiting - don't proceed until batches complete
                                continue
                    else:
                        self._batch_wait_force_count = 0

                # Note: Also check tracker peer connection timestamp (secondary check)
                # This ensures we wait for tracker responses to be processed
                import time as time_module

                tracker_peers_connecting_until = getattr(
                    self.session, "_tracker_peers_connecting_until", None
                )
                if (
                    tracker_peers_connecting_until
                    and time_module.time() < tracker_peers_connecting_until
                ):
                    wait_time = tracker_peers_connecting_until - time_module.time()
                    swarm_state = await self._get_swarm_recovery_state()
                    fast_recovery_fn = getattr(
                        self.session,
                        "swarm_requires_fast_recovery",
                        lambda state: bool(state.get("metadata_incomplete", False))
                        or bool(state.get("degraded_swarm", False))
                        or not bool(state.get("has_usable_download_path", False))
                        or int(state.get("active_peers", 0) or 0) == 0,
                    )
                    capped_wait = (
                        min(wait_time, 1.0)
                        if fast_recovery_fn(swarm_state)
                        else min(wait_time, 5.0)
                    )
                    self.logger.info(
                        "⏸️ DHT DISCOVERY: Tracker peers are currently being connected. Waiting %.1fs before starting DHT query to allow tracker connections to complete...",
                        capped_wait,
                    )
                    await asyncio.sleep(capped_wait)

                # Note: Wait until we have minimum peers before starting DHT
                # This prevents aggressive DHT queries that can cause blacklisting
                current_peer_count = 0
                current_download_rate = 0.0
                routing_table_size = len(getattr(dht_client.routing_table, "nodes", []))
                if routing_table_size == 0:
                    self._empty_routing_cycles += 1
                    self._set_health_state("stalled")
                    self.logger.warning(
                        "DHT recovery state=bootstrap_empty cycle=%d for %s (routing table has 0 nodes)",
                        self._empty_routing_cycles,
                        self.session.info.name,
                    )
                    if self._empty_routing_cycles >= 2:
                        did_rebootstrap = await self._maybe_rebootstrap(
                            dht_client,
                            reason=(
                                f"empty_routing_table cycle={self._empty_routing_cycles}"
                            ),
                        )
                        if not did_rebootstrap:
                            backoff_wait = (
                                self._dht_zero_state_reprobe_wait_s
                                * self._dht_empty_state_backoff_factor
                            )
                            self.logger.debug(
                                "DHT recovery state=bootstrap_empty_recovery_backoff for %s (%d empty cycles): waiting %.1fs before next bootstrap attempt",
                                self.session.info.name,
                                self._empty_routing_cycles,
                                backoff_wait,
                            )
                            await asyncio.sleep(backoff_wait)
                else:
                    if self._empty_routing_cycles > 0:
                        self.logger.info(
                            "DHT recovery state=bootstrap_recovered for %s after %d empty cycle(s) (routing table: %d nodes)",
                            self.session.info.name,
                            self._empty_routing_cycles,
                            routing_table_size,
                        )
                    self._empty_routing_cycles = 0
                    self._set_health_state("healthy")

                swarm_state = await self._get_swarm_recovery_state()
                current_peer_count = int(swarm_state["active_peers"])
                current_requestable_peers = int(swarm_state["requestable_peers"])
                current_productive_peers = int(swarm_state["productive_peers"])
                peers_with_piece_info = int(swarm_state["peers_with_piece_info"])
                active_block_requests = int(swarm_state["active_block_requests"])
                current_download_rate = float(swarm_state["download_rate"])

                # Allow magnet metadata bootstrap to use DHT immediately when tracker peers
                # have not produced any active connections yet.
                is_magnet_bootstrap = (
                    isinstance(self.session.torrent_data, dict)
                    and self.session.torrent_data.get("file_info", {}).get(
                        "total_length", 0
                    )
                    == 0
                )
                metadata_incomplete = (
                    bool(swarm_state["metadata_incomplete"]) or is_magnet_bootstrap
                )
                fail_fast_low_peers = False
                if current_peer_count == 0 and not metadata_incomplete:
                    fail_fast_low_peers = True
                    self.logger.warning(
                        "🧭 DHT DISCOVERY: No active peers remain. Bypassing low-peer grace period and starting DHT recovery immediately."
                    )
                elif (
                    not metadata_incomplete
                    and peers_with_piece_info == 0
                    and active_block_requests == 0
                ):
                    fail_fast_low_peers = True
                    self.logger.warning(
                        "🧭 DHT DISCOVERY: Connected peers are not payload-capable (active=%d, productive=%d, requestable=%d, piece_info=%d). Starting DHT recovery immediately.",
                        current_peer_count,
                        current_productive_peers,
                        current_requestable_peers,
                        peers_with_piece_info,
                    )
                low_peers_since = getattr(self.session, "_low_peers_since", None)
                if (
                    enable_fail_fast
                    and not metadata_incomplete
                    and current_peer_count < min_peers_before_dht
                    and low_peers_since is not None
                ):
                    time_at_low = time.monotonic() - low_peers_since
                    if time_at_low >= fail_fast_timeout:
                        fail_fast_low_peers = True
                        self.logger.warning(
                            "🧭 DHT DISCOVERY: Active peers (%d) below minimum (%d) for %.1fs. Starting DHT to recover swarm health.",
                            current_peer_count,
                            min_peers_before_dht,
                            time_at_low,
                        )

                # Allow DHT to start when we have at least min_peers_before_dht (configurable, default 10)
                if (
                    not dht_started
                    and current_peer_count < min_peers_before_dht
                    and not metadata_incomplete
                    and not fail_fast_low_peers
                ):
                    if (
                        current_peer_count <= self._low_peer_threshold
                        and current_requestable_peers == 0
                    ):
                        self.logger.warning(
                            "🧭 DHT DISCOVERY: Active peer count is severely low (%d <= %d) with 0 requestable peers. Running short-path bootstrap recheck.",
                            current_peer_count,
                            self._low_peer_threshold,
                        )
                        routing_table_size = await self._ensure_bootstrap_ready(
                            dht_client,
                            reason=(f"short_path_recovery:{self.session.info.name}"),
                            timeout=10.0,
                            min_nodes=1,
                        )
                        dht_started = routing_table_size >= 1
                        if dht_started:
                            continue

                    low_peer_wait_s = (
                        self._low_peer_suppression_window_s
                        if current_peer_count <= self._low_peer_threshold
                        and self._low_peer_suppression_window_s > 0.0
                        else 30.0
                    )
                    self.logger.info(
                        "⏸️ DHT DISCOVERY: Waiting for minimum peers (%d/%d) with usable swarm state (productive=%d, requestable=%d, piece_info=%d). Sleeping %.1fs before recheck...",
                        current_peer_count,
                        min_peers_before_dht,
                        current_productive_peers,
                        current_requestable_peers,
                        peers_with_piece_info,
                        low_peer_wait_s,
                    )
                    await asyncio.sleep(low_peer_wait_s)
                    continue

                if (
                    not dht_started
                    and metadata_incomplete
                    and current_peer_count < min_peers_before_dht
                ):
                    self.logger.info(
                        "🧲 DHT DISCOVERY: Metadata is still incomplete with only %d peer(s). Starting DHT discovery immediately.",
                        current_peer_count,
                    )

                if not dht_started and current_peer_count >= min_peers_before_dht:
                    dht_started = True
                    self.logger.info(
                        "✅ DHT DISCOVERY: Minimum peer count reached (%d >= %d). Starting DHT discovery.",
                        current_peer_count,
                        min_peers_before_dht,
                    )
                elif (
                    not dht_started
                    and metadata_incomplete
                    and current_peer_count < min_peers_before_dht
                ) or (not dht_started and fail_fast_low_peers):
                    dht_started = True

                # Note: Use conservative DHT settings to avoid blacklisting
                # Reduced query frequency and parameters
                max_peers_per_torrent = (
                    self.session.config.network.max_peers_per_torrent
                )
                peer_count_ratio = (
                    current_peer_count / max_peers_per_torrent
                    if max_peers_per_torrent > 0
                    else 0.0
                )

                # Determine if torrent is popular (many peers) or active (downloading)
                is_popular = current_peer_count >= 50  # 50+ peers = popular
                is_active = current_download_rate > 1024  # >1KB/s = active
                is_below_limit = peer_count_ratio < 0.7  # <70% of max = below limit
                is_critically_low = (
                    current_peer_count < max_peers_per_torrent * 0.2
                    if max_peers_per_torrent > 0
                    else current_peer_count < 5
                )  # <20% of max or <5 peers = critically low
                is_ultra_low = (
                    current_peer_count < max_peers_per_torrent * 0.1
                    if max_peers_per_torrent > 0
                    else current_peer_count < 3
                )  # <10% of max or <3 peers = ultra low

                # Note: Use conservative aggressive mode - only for popular/active torrents
                # Don't enable aggressive mode for low peer counts to avoid blacklisting
                new_aggressive_mode = (is_popular or is_active) and is_below_limit

                # Note: Use conservative DHT query intervals to avoid blacklisting
                # Minimum 60 seconds between queries (standard DHT interval)
                dht_retry_interval = max(
                    60.0, initial_retry_interval
                )  # Minimum 60 seconds
                max_peers_per_query = 50  # Reduced from 100 to avoid overwhelming

                if new_aggressive_mode != aggressive_mode:
                    aggressive_mode = new_aggressive_mode
                    self._aggressive_mode = aggressive_mode  # Store for metrics

                    if aggressive_mode:
                        self.logger.info(
                            "🔍 DHT DISCOVERY: Conservative aggressive mode enabled for %s (peer_count: %d, download_rate: %.1f KB/s). "
                            "Using interval: %.1fs, max_peers: %d (conservative to avoid blacklisting)",
                            self.session.info.name,
                            current_peer_count,
                            current_download_rate / 1024.0,
                            dht_retry_interval,
                            max_peers_per_query,
                        )
                    else:
                        self.logger.info(
                            "🔍 DHT DISCOVERY: Normal mode for %s (peer_count: %d). Using interval: %.1fs, max_peers: %d (conservative to avoid blacklisting)",
                            self.session.info.name,
                            current_peer_count,
                            dht_retry_interval,
                            max_peers_per_query,
                        )
                if new_aggressive_mode != aggressive_mode:
                    aggressive_mode = new_aggressive_mode
                    self._aggressive_mode = aggressive_mode  # Store for metrics

                    # IMPROVEMENT: Emit event for aggressive mode change
                    try:
                        from ccbt.utils.events import Event, EventType, emit_event

                        reason = (
                            "popular"
                            if is_popular
                            else ("active" if is_active else "normal")
                        )
                        if aggressive_mode:
                            await emit_event(
                                Event(
                                    event_type=EventType.DHT_AGGRESSIVE_MODE_ENABLED.value,
                                    data={
                                        "info_hash": self.session.info.info_hash.hex(),
                                        "torrent_name": self.session.info.name,
                                        "reason": reason,
                                        "peer_count": current_peer_count,
                                        "download_rate_kib": current_download_rate
                                        / 1024.0,
                                    },
                                )
                            )
                        else:
                            await emit_event(
                                Event(
                                    event_type=EventType.DHT_AGGRESSIVE_MODE_DISABLED.value,
                                    data={
                                        "info_hash": self.session.info.info_hash.hex(),
                                        "torrent_name": self.session.info.name,
                                        "reason": reason,
                                        "peer_count": current_peer_count,
                                        "download_rate_kib": current_download_rate
                                        / 1024.0,
                                    },
                                )
                            )
                    except Exception as e:
                        self.logger.debug("Failed to emit aggressive mode event: %s", e)

                    if aggressive_mode:
                        self.logger.info(
                            "Enabling aggressive DHT discovery for %s (peers: %d, download: %.1f KB/s)",
                            self.session.info.name,
                            current_peer_count,
                            current_download_rate / 1024.0,
                        )
                    else:
                        self.logger.debug(
                            "Disabling aggressive DHT discovery for %s (peers: %d, download: %.1f KB/s)",
                            self.session.info.name,
                            current_peer_count,
                            current_download_rate / 1024.0,
                        )

                # Adjust retry interval based on mode
                if aggressive_mode:
                    # More frequent queries for popular/active torrents (but still reasonable to prevent blacklisting)
                    if is_critically_low:
                        # CRITICAL: Reasonable interval for low peer count (30s minimum to prevent blacklisting)
                        base_interval = 30.0  # 30 seconds for critically low peer count (was 3s - too aggressive)
                        max_peers_per_query = 100  # Reasonable peer query limit
                        self.logger.info(
                            "Critically low peer count (%d/%d): using aggressive DHT discovery (interval: %.1fs, max_peers: %d)",
                            current_peer_count,
                            max_peers_per_torrent,
                            base_interval,
                            max_peers_per_query,
                        )
                    elif is_below_limit:
                        # Note: Aggressive discovery when below connection limit
                        # Scale interval based on how far we are from the limit
                        # All intervals use 30s minimum to prevent peer blacklisting
                        if (
                            peer_count_ratio < 0.1 or peer_count_ratio < 0.25
                        ):  # <10% of limit
                            base_interval = 30.0  # Minimum 30s to prevent blacklisting
                            max_peers_per_query = 100
                        else:  # 25-50% of limit
                            base_interval = 60.0  # 60s for moderate cases
                            max_peers_per_query = 100
                        self.logger.info(
                            "Below connection limit (%d/%d, %.1f%%): using aggressive DHT discovery (interval: %.1fs, max_peers: %d)",
                            current_peer_count,
                            max_peers_per_torrent,
                            peer_count_ratio * 100,
                            base_interval,
                            max_peers_per_query,
                        )
                    elif is_active:
                        # Reasonable interval if actively downloading (30s minimum)
                        base_interval = 30.0  # 30 seconds minimum
                        max_peers_per_query = 100  # Query more peers
                    else:
                        base_interval = 60.0  # 60 seconds for popular torrents
                        max_peers_per_query = 100  # Query more peers
                    dht_retry_interval = min(
                        base_interval, dht_retry_interval
                    )  # Don't increase if already low
                # Normal mode - use exponential backoff: 60s → 120s → 240s → 480s → 960s → 1920s
                elif consecutive_failures == 0:
                    dht_retry_interval = initial_retry_interval  # Start at 60s
                else:
                    # Exponential backoff: multiply by 2.0 for each consecutive failure
                    calculated_interval = initial_retry_interval * (
                        base_backoff_multiplier**consecutive_failures
                    )
                    dht_retry_interval = min(calculated_interval, max_retry_interval)
                    self.logger.debug(
                        "DHT exponential backoff: interval=%.1fs (failures=%d, multiplier=%.1f, calculated=%.1fs)",
                        dht_retry_interval,
                        consecutive_failures,
                        base_backoff_multiplier,
                        calculated_interval,
                    )

                # Trigger DHT get_peers query
                # Note: Add detailed logging for DHT queries
                mode_str = "AGGRESSIVE" if aggressive_mode else "NORMAL"
                self.logger.info(
                    "🔍 DHT DISCOVERY: Starting get_peers query for %s [%s] (routing table: %d nodes, info_hash: %s, callbacks: %d, current peers: %d/%d, download: %.1f KB/s, next retry: %.1fs)",
                    self.session.info.name,
                    mode_str,
                    routing_table_size,
                    self.session.info.info_hash.hex()[:16] + "...",
                    len(dht_client.peer_callbacks),
                    current_peer_count,
                    max_peers_per_torrent,
                    current_download_rate / 1024.0,
                    dht_retry_interval,
                )
                # Note: Improved timeout and parallel query strategy
                # Use adaptive timeout: start with 30s, increase for later attempts
                # DHT queries may need more time to explore the network, especially for less popular torrents
                query_start_time = asyncio.get_event_loop().time()
                # Note: Increased DHT timeout to handle slow DHT nodes and network latency
                # Many DHT nodes are slow to respond, especially for less popular torrents
                # Start with 45s base timeout and scale up to 90s max for better discovery success
                base_timeout = 45.0  # Increased from 30s to 45s
                max_timeout = 90.0  # Increased from 60s to 90s
                timeout = min(
                    base_timeout * (1 + attempt_count * 0.15), max_timeout
                )  # Scale up to 90s max (reduced scaling factor from 0.2 to 0.15 for smoother progression)
                attempt_count += 1

                self.logger.debug(
                    "Starting DHT get_peers query for %s (attempt %d, timeout: %.1fs, retry_interval: %.1fs)",
                    self.session.info.name,
                    attempt_count,
                    timeout,
                    dht_retry_interval,
                )

                try:
                    # Note: Enforce minimum delay between DHT queries to prevent overwhelming the network
                    # This prevents peers from blacklisting us due to too frequent queries
                    import time as time_module

                    current_time = time_module.time()
                    time_since_last_query = current_time - self._last_dht_query_time
                    effective_min_interval = self._min_dht_query_interval
                    if metadata_incomplete and current_peer_count == 0:
                        # Magnet metadata starvation path: allow quicker retries.
                        effective_min_interval = min(effective_min_interval, 5.0)
                    if time_since_last_query < effective_min_interval:
                        wait_time = effective_min_interval - time_since_last_query
                        self.logger.info(
                            "⏸️ DHT RATE LIMIT: Waiting %.1fs before query (last query: %.1fs ago, min interval: %.1fs) to prevent peer blacklisting",
                            wait_time,
                            time_since_last_query,
                            effective_min_interval,
                        )
                        # Note: Use interruptible sleep that checks _stopped frequently
                        # This ensures the loop exits quickly when shutdown is requested
                        sleep_interval = min(
                            wait_time, 1.0
                        )  # Check at least every second
                        elapsed = 0.0
                        while elapsed < wait_time and not self.session.stopped:
                            await asyncio.sleep(sleep_interval)
                            elapsed += sleep_interval

                        # Check _stopped after sleep
                        if self.session.stopped:
                            break
                    self._last_dht_query_time = time_module.time()

                    # IMPROVEMENT: Adaptive DHT query parameters for better discovery
                    # Use configuration values instead of hardcoded values
                    if aggressive_mode:
                        # Aggressive mode: use aggressive configuration values
                        if is_ultra_low:
                            # Note: Use reasonable parameters even for ultra-low peer count
                            # Ultra-aggressive parameters (alpha=16, k=64, max_depth=20) were causing peers to blacklist us
                            # Use BEP 5 compliant values: alpha=4, k=8, max_depth=10 for better peer acceptance
                            # Slightly increase from normal but stay within reasonable bounds
                            alpha = min(
                                self.session.config.discovery.dht_aggressive_alpha, 6
                            )  # Max 6 parallel queries (was 20)
                            k = min(
                                self.session.config.discovery.dht_aggressive_k, 16
                            )  # Max 16 bucket size (was 64)
                            max_depth_override = min(
                                self.session.config.discovery.dht_aggressive_max_depth,
                                12,
                            )  # Max 12 depth (was 25)
                            self.logger.info(
                                "🔍 DHT DISCOVERY: Ultra-low peer count mode for %s: alpha=%d, k=%d, max_depth=%d (reduced from ultra-aggressive to prevent peer blacklisting)",
                                self.session.info.name,
                                alpha,
                                k,
                                max_depth_override,
                            )
                        else:
                            alpha = self.session.config.discovery.dht_aggressive_alpha
                            k = self.session.config.discovery.dht_aggressive_k
                            max_depth_override = (
                                self.session.config.discovery.dht_aggressive_max_depth
                            )
                    else:
                        # Normal mode: use normal configuration values
                        alpha = self.session.config.discovery.dht_normal_alpha
                        k = self.session.config.discovery.dht_normal_k
                        max_depth_override = (
                            self.session.config.discovery.dht_normal_max_depth
                        )

                    # Note: get_peers() will invoke callbacks automatically when peers are found
                    # We still call it to trigger the query, but callbacks handle peer connection
                    # Use asyncio.wait_for with timeout to ensure query completes
                    peers = await asyncio.wait_for(
                        dht_client.get_peers(
                            self.session.info.info_hash,
                            max_peers=max_peers_per_query,
                            alpha=alpha,
                            k=k,
                            max_depth=max_depth_override,
                        ),
                        timeout=timeout,
                    )
                    query_duration = asyncio.get_event_loop().time() - query_start_time
                    peer_count = len(peers) if peers else 0

                    # IMPROVEMENT: Track DHT query metrics
                    # Type assertions for metrics dict access
                    from typing import cast

                    query_metrics = cast("dict[str, Any]", self._dht_query_metrics)
                    query_metrics["total_queries"] = (
                        int(query_metrics.get("total_queries", 0) or 0) + 1
                    )
                    query_metrics["total_peers_found"] = (
                        int(query_metrics.get("total_peers_found", 0) or 0) + peer_count
                    )
                    query_metrics["bootstrap_success_count"] = int(
                        getattr(dht_client, "bootstrap_success_count", 0) or 0
                    )
                    query_metrics["bootstrap_failure_count"] = int(
                        getattr(dht_client, "bootstrap_failure_count", 0) or 0
                    )
                    query_metrics["last_bootstrap_reason"] = str(
                        getattr(dht_client, "last_bootstrap_reason", "")
                    )
                    query_metrics["last_bootstrap_failure_reason"] = str(
                        getattr(dht_client, "last_bootstrap_failure_reason", "")
                    )
                    query_metrics["last_zero_node_lookup_at"] = float(
                        getattr(dht_client, "last_zero_node_lookup_at", 0.0) or 0.0
                    )
                    query_durations = cast(
                        "list[float]", query_metrics.get("query_durations", [])
                    )
                    query_durations.append(query_duration)
                    if len(query_durations) > 100:  # type: ignore[arg-type]
                        # Keep only last 100 queries
                        query_metrics["query_durations"] = query_durations[-100:]

                    # Get query depth and nodes queried from DHT client if available
                    query_depth = 0
                    nodes_queried = 0
                    last_metrics = getattr(dht_client, "_last_query_metrics", None)
                    lookup_state = (
                        last_metrics.get("lookup_state", "") if last_metrics else ""
                    )
                    if last_metrics:
                        query_depth = last_metrics.get("depth", 0)
                        nodes_queried = last_metrics.get("nodes_queried", 0)
                        query_depths_list = cast(
                            "list[int]", query_metrics.get("query_depths", [])
                        )
                        nodes_queried_list = cast(
                            "list[int]", query_metrics.get("nodes_queried", [])
                        )
                        query_depths_list.append(query_depth)
                        nodes_queried_list.append(nodes_queried)
                        if len(query_depths_list) > 100:  # type: ignore[arg-type]
                            query_metrics["query_depths"] = query_depths_list[-100:]
                        if len(nodes_queried_list) > 100:  # type: ignore[arg-type]
                            query_metrics["nodes_queried"] = nodes_queried_list[-100:]
                    if nodes_queried == 0 and lookup_state == "empty_routing_table":
                        self._set_health_state("stalled")
                        self.logger.warning(
                            "DHT recovery state=empty_routing_table for %s; query could not start because routing table was empty.",
                            self.session.info.name,
                        )
                    elif nodes_queried == 0:
                        self._query_zero_nodes_cycles += 1
                        with contextlib.suppress(Exception):
                            get_metrics_collector().increment_counter(
                                "bootstrap_zero_state_count"
                            )
                        self._set_health_state("degraded")
                        self.logger.warning(
                            "DHT recovery state=query_zero_nodes cycle=%d for %s (routing table: %d nodes, depth=%d)",
                            self._query_zero_nodes_cycles,
                            self.session.info.name,
                            routing_table_size,
                            query_depth,
                        )
                        if self._query_zero_nodes_cycles >= 2:
                            await self._maybe_rebootstrap(
                                dht_client,
                                reason=(
                                    "query_zero_nodes "
                                    f"cycle={self._query_zero_nodes_cycles}"
                                ),
                            )
                    else:
                        if self._query_zero_nodes_cycles > 0:
                            self.logger.info(
                                "DHT recovery state=query_nodes_recovered for %s after %d zero-node cycle(s) (nodes_queried=%d)",
                                self.session.info.name,
                                self._query_zero_nodes_cycles,
                                nodes_queried,
                            )
                        self._query_zero_nodes_cycles = 0
                        if routing_table_size > 0:
                            self._set_health_state("healthy")

                    # Update last query metrics
                    self._dht_query_metrics["last_query"] = {
                        "duration": query_duration,
                        "peers_found": peer_count,
                        "depth": query_depth,
                        "nodes_queried": nodes_queried,
                        "lookup_state": lookup_state,
                        "bootstrap_state": str(
                            getattr(dht_client, "last_bootstrap_state", "")
                        ),
                    }

                    # IMPROVEMENT: Emit event for iterative lookup completion
                    try:
                        from ccbt.utils.events import Event, EventType, emit_event

                        await emit_event(
                            Event(
                                event_type=EventType.DHT_ITERATIVE_LOOKUP_COMPLETE.value,
                                data={
                                    "info_hash": self.session.info.info_hash.hex(),
                                    "torrent_name": self.session.info.name,
                                    "peers_found": peer_count,
                                    "query_duration": query_duration,
                                    "query_depth": query_depth,
                                    "nodes_queried": nodes_queried,
                                    "lookup_state": lookup_state,
                                    "bootstrap_state": str(
                                        getattr(dht_client, "last_bootstrap_state", "")
                                    ),
                                    "aggressive_mode": aggressive_mode,
                                },
                            )
                        )
                    except Exception as e:
                        self.logger.debug(
                            "Failed to emit DHT query complete event: %s", e
                        )

                    self.logger.debug(
                        "DHT get_peers query completed for %s in %.2fs (returned %d peers, callbacks should have been invoked)",
                        self.session.info.name,
                        query_duration,
                        peer_count,
                    )

                    # Note: Even if get_peers returns empty, callbacks may have been invoked
                    # with peers discovered during the query. The callback handles peer connection.
                    # This is normal DHT behavior - peers are connected via callbacks, not return value
                    if peer_count > 0:
                        self.logger.info(
                            "✅ DHT DISCOVERY: get_peers returned %d peers for %s (callbacks should have connected them, query took %.2fs)",
                            peer_count,
                            self.session.info.name,
                            query_duration,
                        )
                    else:
                        # Empty result is normal - callbacks handle peer discovery
                        self.logger.debug(
                            "DHT get_peers returned empty for %s (this is normal - callbacks handle peer discovery)",
                            self.session.info.name,
                        )
                        # Note: Verify peers were actually connected via callback
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
                                node_peers = [
                                    {
                                        "ip": node.ip,
                                        "port": node.port,
                                        "peer_source": "dht_node",
                                    }
                                    for node in closest_nodes
                                    if node.ip and node.port
                                ]

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
                    # Note: Even on timeout, callbacks may have been invoked with partial results
                    # The query may have found some peers before timing out
                    query_duration = asyncio.get_event_loop().time() - query_start_time
                    with contextlib.suppress(Exception):
                        dht_client.last_lookup_state = "query_timeout"

                    # Note: Progressive timeout increase for retries
                    # Timeout already increases with attempt_count, but log the progression
                    timeout_progression = f"{base_timeout:.1f}s → {timeout:.1f}s (attempt {attempt_count})"

                    self.logger.warning(
                        "DHT get_peers query timed out for %s after %.2fs (timeout: %.1fs, progression: %s, routing table: %d nodes). "
                        "This may indicate: (1) DHT responses not being received (check firewall/NAT on port %d), "
                        "(2) Network connectivity issues, or (3) Torrent not well-seeded on DHT. "
                        "Check if 'DHT datagram_received' logs appear - if not, DHT responses are being blocked. "
                        "Next query will use longer timeout (progressive timeout increase).",
                        self.session.info.name,
                        query_duration,
                        timeout,
                        timeout_progression,
                        routing_table_size,
                        dht_client.bind_port
                        if hasattr(dht_client, "bind_port")
                        else "unknown",
                    )
                    peers = []  # Return empty list on timeout (but callbacks may have been invoked)
                except Exception as query_error:
                    # Note: Handle all exceptions gracefully - don't stop the discovery loop
                    query_duration = asyncio.get_event_loop().time() - query_start_time
                    with contextlib.suppress(Exception):
                        dht_client.last_lookup_state = "query_error"
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

                # Note: Check if peers were found (either directly or via callbacks)
                # Callbacks should have been invoked during get_peers() call
                # We check both the returned peers and whether callbacks were invoked
                peer_count = len(peers) if peers else 0

                # Note: Even if get_peers returns empty, callbacks may have been invoked
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
                    # Note: Empty return doesn't mean failure - callbacks may have been invoked
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
                            # Note: Improved exponential backoff with jitter to prevent thundering herd
                            # For first few failures, use reasonable retry (30s minimum to prevent blacklisting)
                            import random

                            if consecutive_failures <= 3:
                                # Reasonable interval for first 3 failures (30s minimum)
                                base_interval = 30.0
                            else:
                                # Exponential backoff: increase retry interval with jitter
                                # Formula: base_interval * (2^failures) + random_jitter
                                exponential_interval = (
                                    dht_retry_interval * base_backoff_multiplier
                                )
                                jitter = random.uniform(
                                    0, exponential_interval * 0.1
                                )  # 0-10% jitter
                                base_interval = exponential_interval + jitter

                            dht_retry_interval = min(base_interval, max_retry_interval)

                            self.logger.info(
                                "DHT get_peers returned no peers (attempt %d/%d) for %s (routing table: %d nodes). "
                                "Retrying in %.1fs (exponential backoff with jitter). "
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
                        # Note: We have active peers even though get_peers returned empty
                        # This can happen if:
                        # 1. Peers were connected from a previous query (callbacks invoked earlier)
                        # 2. Peers were connected via trackers or PEX
                        # 3. The current query didn't find new peers but existing connections are active
                        # This is normal behavior - the query completed, we just didn't find new peers this time
                        self.logger.debug(
                            "DHT get_peers returned empty for %s but active peers exist (likely from previous queries or other sources). "
                            "This is normal - iterative lookup completed, no new peers found in this query.",
                            self.session.info.name,
                        )
                        consecutive_failures = 0

                        # IMPROVEMENT: In aggressive mode, keep retry interval low even after success
                        if aggressive_mode:
                            dht_retry_interval = min(
                                initial_retry_interval, dht_retry_interval
                            )  # Keep low for aggressive mode
                        else:
                            dht_retry_interval = initial_retry_interval

                # Note: Make discovery more aggressive when peer count is low
                # Check current peer count and adjust wait time accordingly
                current_peer_count = 0
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
                            current_peer_count = (
                                len(active_peers) if active_peers else 0
                            )
                        except Exception:
                            pass

                max_peers_per_torrent = (
                    self.session.config.network.max_peers_per_torrent
                )
                peer_count_ratio = (
                    current_peer_count / max_peers_per_torrent
                    if max_peers_per_torrent > 0
                    else 0.0
                )

                # Note: Use reasonable wait time when peer count is low
                # Respect minimum query interval (30s) to prevent peer blacklisting
                if current_peer_count < 5:
                    # Critically low: use minimum interval (30s) to prevent blacklisting
                    wait_time = max(30.0, dht_retry_interval)
                    self.logger.info(
                        "DHT discovery: Critically low peer count (%d/%d), using interval: %.1fs (minimum 30s to prevent blacklisting)",
                        current_peer_count,
                        max_peers_per_torrent,
                        wait_time,
                    )
                elif peer_count_ratio < 0.3:
                    # Below 30% of max: use minimum interval (30s)
                    wait_time = max(30.0, dht_retry_interval)
                    self.logger.debug(
                        "DHT discovery: Low peer count (%d/%d, %.1f%%), using shorter interval: %.1fs",
                        current_peer_count,
                        max_peers_per_torrent,
                        peer_count_ratio * 100,
                        wait_time,
                    )
                elif peer_count_ratio < 0.5:
                    # Below 50% of max: wait up to 15 seconds
                    wait_time = min(15.0, dht_retry_interval)
                else:
                    # Normal wait time
                    wait_time = dht_retry_interval

                self.logger.debug(
                    "DHT query retry: waiting %.1fs before next attempt (peers: %d/%d, consecutive failures: %d, attempt: %d)",
                    wait_time,
                    current_peer_count,
                    max_peers_per_torrent,
                    consecutive_failures,
                    attempt_count,
                )
                # Note: Use interruptible sleep that checks _stopped frequently
                # This ensures the loop exits quickly when shutdown is requested
                sleep_interval = min(wait_time, 1.0)  # Check at least every second
                elapsed = 0.0
                while elapsed < wait_time and not self.session.stopped:
                    await asyncio.sleep(sleep_interval)
                    elapsed += sleep_interval

                # Check _stopped after sleep
                if self.session.stopped:
                    break
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
                # Note: Use interruptible sleep that checks _stopped frequently
                # This ensures the loop exits quickly when shutdown is requested
                sleep_interval = min(wait_time, 1.0)  # Check at least every second
                elapsed = 0.0
                while elapsed < wait_time and not self.session.stopped:
                    await asyncio.sleep(sleep_interval)
                    elapsed += sleep_interval

                # Check _stopped after sleep
                if self.session.stopped:
                    break
