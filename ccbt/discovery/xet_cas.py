"""Peer-to-peer Content Addressable Storage client for Xet protocol.

This module provides P2P CAS functionality using existing DHT and tracker
infrastructure, eliminating the need for HuggingFace's centralized CAS service.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import time
from typing import TYPE_CHECKING, Any, Optional

from ccbt.models import PeerInfo
from ccbt.peer.peer import Handshake
from ccbt.utils.exceptions import HandshakeError

if TYPE_CHECKING:
    from ccbt.security.encrypted_stream import (
        EncryptedStreamReader,  # noqa: F401
        EncryptedStreamWriter,  # noqa: F401
    )

from ccbt.peer.async_peer_connection import AsyncPeerConnection, ConnectionState

# Note: AsyncPeerConnection uses EncryptedStreamReader/Writer in its type annotations,
# which are only imported under TYPE_CHECKING in async_peer_connection.py. This causes
# the type checker to sometimes resolve AsyncPeerConnection to Never. The class is
# properly defined and works at runtime - this is a type checker limitation.

logger = logging.getLogger(__name__)


class P2PCASClient:
    """Peer-to-peer Content Addressable Storage client.

    Uses DHT and trackers for chunk discovery instead of HuggingFace CAS.
    This enables distributed chunk storage and retrieval without external
    dependencies.

    Attributes:
        dht: DHT client instance
        tracker: Optional tracker client instance
        local_chunks: Dictionary mapping chunk hash to local storage path

    """

    def __init__(
        self,
        dht_client: Optional[Any] = None,  # type: ignore[assignment]
        tracker_client: Optional[Any] = None,  # type: ignore[assignment]
        key_manager: Any = None,  # Ed25519KeyManager
        bloom_filter: Optional[Any] = None,  # XetChunkBloomFilter
        catalog: Optional[Any] = None,  # XetChunkCatalog
        extension_manager: Optional[Any] = None,  # ExtensionManager
    ):
        """Initialize P2P CAS with DHT and tracker clients.

        Args:
            dht_client: DHT client instance (will be obtained from session if None)
            tracker_client: Optional tracker client instance
            key_manager: Optional Ed25519KeyManager for signing chunks
            bloom_filter: Optional bloom filter for chunk availability
            catalog: Optional chunk catalog for bulk queries
            extension_manager: Optional ExtensionManager (preferred over get_extension_manager())

        """
        self.dht = dht_client
        self.tracker = tracker_client
        self.key_manager = key_manager
        self.bloom_filter = bloom_filter
        self.catalog = catalog
        self.extension_manager = extension_manager
        self.pex_manager: Optional[Any] = None
        self.peer_authorizer: Optional[Any] = None
        self.discovery_backend_success_notifier: Optional[Any] = None
        self.local_chunks: dict[bytes, str] = {}  # hash -> local path
        # Discovery result cache: chunk_hash -> (peers, timestamp)
        self._discovery_cache: dict[bytes, tuple[list[PeerInfo], float]] = {}
        self._cache_ttl = 60.0  # Default 60 seconds, configurable
        self.logger = logging.getLogger(__name__)

    def _verify_signed_chunk_metadata(self, metadata: dict[str, Any]) -> bool:
        """Verify signed DHT metadata when signature fields are present."""
        public_key_hex = metadata.get("ed25519_public_key")
        signature_hex = metadata.get("ed25519_signature")
        if public_key_hex is None and signature_hex is None:
            return True
        if not isinstance(public_key_hex, str) or not isinstance(signature_hex, str):
            return False
        try:
            from ccbt.security.key_manager import Ed25519KeyManager

            public_key = bytes.fromhex(public_key_hex)
            signature = bytes.fromhex(signature_hex)
            signed_payload = json.dumps(
                {
                    "available": bool(metadata.get("available")),
                    "type": metadata.get("type"),
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            return Ed25519KeyManager.verify_signature(
                signed_payload,
                signature,
                public_key,
            )
        except Exception:
            self.logger.debug("Invalid signed chunk metadata", exc_info=True)
            return False

    def record_chunk_peer(
        self, chunk_hash: bytes, peer_ip: str, peer_port: int
    ) -> None:
        """Record that a peer has a chunk (for multicast/gossip/LPD inbound).

        Async-safe: schedules catalog.add_chunk on the running event loop.
        Callable from sync callbacks (e.g. multicast chunk_callback).

        Args:
            chunk_hash: 32-byte chunk hash
            peer_ip: Peer IP address
            peer_port: Peer port

        """
        if len(chunk_hash) != 32 or not self.catalog:
            return
        catalog = self.catalog
        add_chunk = getattr(catalog, "add_chunk", None)
        if not callable(add_chunk):
            return

        peer_info: tuple[str, int] = (peer_ip, peer_port)

        async def _add() -> None:
            try:
                await add_chunk(chunk_hash, peer_info)
            except Exception as e:
                self.logger.warning("Error recording chunk peer from inbound: %s", e)

        try:
            loop = asyncio.get_running_loop()
            task = loop.create_task(_add())
            task.add_done_callback(lambda _finished: None)
        except RuntimeError:
            pass

    async def announce_chunk(
        self,
        chunk_hash: bytes,
        peer_info: Optional[PeerInfo] = None,
        workspace_id_hex: Optional[str] = None,
    ) -> None:
        """Announce chunk availability to DHT/trackers.

        Stores chunk metadata in DHT (BEP 44) and announces to tracker
        if configured. Other peers can discover this chunk via hash lookup.

        Args:
            chunk_hash: 32-byte chunk hash
            peer_info: Optional peer descriptor for catalog/tracker updates
            workspace_id_hex: Optional workspace scope for tracker registration

        """
        if len(chunk_hash) != 32:
            msg = f"Chunk hash must be 32 bytes, got {len(chunk_hash)}"
            raise ValueError(msg)

        # Store chunk hash in DHT (BEP 44: storing arbitrary data)
        if self.dht:
            try:
                # Store chunk metadata in DHT
                # Format: {"type": "xet_chunk", "peer_id": ..., "available": True}
                metadata = {
                    "type": "xet_chunk",
                    "available": True,
                }
                if peer_info is not None:
                    metadata["ip"] = peer_info.ip
                    metadata["port"] = peer_info.port

                # Sign chunk metadata with Ed25519 if key_manager available
                if self.key_manager:
                    try:
                        # Create metadata bytes for signing
                        import json

                        metadata_bytes = json.dumps(metadata, sort_keys=True).encode()
                        signature = self.key_manager.sign_message(metadata_bytes)
                        public_key = self.key_manager.get_public_key_bytes()

                        metadata["ed25519_public_key"] = public_key.hex()
                        metadata["ed25519_signature"] = signature.hex()
                        self.logger.debug(
                            "Signed chunk announcement with Ed25519: %s",
                            chunk_hash.hex()[:16],
                        )
                    except Exception as e:
                        self.logger.warning("Failed to sign chunk announcement: %s", e)

                # Use DHT store method if available
                if hasattr(self.dht, "store_chunk_hash"):
                    await self.dht.store_chunk_hash(chunk_hash, metadata)
                elif hasattr(self.dht, "store"):
                    await self.dht.store(chunk_hash, metadata)
                else:
                    self.logger.warning(
                        "DHT client does not support chunk storage",
                    )  # pragma: no cover - DHT client without storage methods, defensive warning path

                self.logger.debug(
                    "Announced chunk %s to DHT",
                    chunk_hash.hex()[:16],
                )
                if callable(self.discovery_backend_success_notifier):
                    self.discovery_backend_success_notifier("dht")
            except Exception as e:
                self.logger.warning("Failed to announce chunk to DHT: %s", e)

        # Update bloom filter if available
        if self.bloom_filter:
            try:
                self.bloom_filter.add_chunk(chunk_hash)
                self.logger.debug(
                    "Added chunk %s to bloom filter",
                    chunk_hash.hex()[:16],
                )
            except Exception as e:
                self.logger.warning("Failed to update bloom filter: %s", e)

        # Update catalog if available
        if self.catalog:
            try:
                # Get our peer info if available
                catalog_peer = None
                if peer_info is not None:
                    catalog_peer = (peer_info.ip, peer_info.port)
                elif hasattr(self, "peer_info"):
                    catalog_peer = (self.peer_info.ip, self.peer_info.port)  # type: ignore[attr-defined]
                await self.catalog.add_chunk(chunk_hash, catalog_peer)
                self.logger.debug(
                    "Added chunk %s to catalog",
                    chunk_hash.hex()[:16],
                )
            except Exception as e:
                self.logger.warning("Failed to update catalog: %s", e)

        # Also announce to tracker if configured
        if self.tracker:
            try:
                if hasattr(self.tracker, "announce_chunk"):
                    if peer_info is None:
                        await self.tracker.announce_chunk(
                            chunk_hash,
                            workspace_id_hex=workspace_id_hex,
                        )
                    else:
                        await self.tracker.announce_chunk(
                            chunk_hash,
                            peer_info=peer_info,
                            workspace_id_hex=workspace_id_hex,
                        )
                self.logger.debug(
                    "Announced chunk %s to tracker",
                    chunk_hash.hex()[:16],
                )
                if callable(self.discovery_backend_success_notifier):
                    self.discovery_backend_success_notifier("tracker")
            except Exception as e:
                self.logger.warning(
                    "Failed to announce chunk to tracker: %s",
                    e,
                )

    async def find_chunk_peers(
        self, chunk_hash: bytes, workspace_id_hex: Optional[str] = None
    ) -> list[PeerInfo]:
        """Find peers that have a specific chunk.

        Queries DHT and tracker (if configured) to find peers that can
        provide the requested chunk. Uses bloom filter for pre-filtering
        if available.

        Args:
            chunk_hash: 32-byte chunk hash
            workspace_id_hex: Optional workspace scope for tracker lookup

        Returns:
            List of peers that can provide this chunk

        """
        if len(chunk_hash) != 32:
            msg = f"Chunk hash must be 32 bytes, got {len(chunk_hash)}"
            raise ValueError(msg)

        # Check cache first
        current_time = time.time()
        if chunk_hash in self._discovery_cache:
            cached_peers, cached_time = self._discovery_cache[chunk_hash]
            if current_time - cached_time < self._cache_ttl:
                self.logger.debug(
                    "Using cached discovery result for chunk %s",
                    chunk_hash.hex()[:16],
                )
                return cached_peers.copy()
            # Cache expired, remove it
            del self._discovery_cache[chunk_hash]

        # Pre-filter using bloom filter if available
        # Note: Bloom filter can have false positives, so we still query
        # but we can skip peers that definitely don't have the chunk
        if self.bloom_filter and not self.bloom_filter.has_chunk(chunk_hash):
            self.logger.debug(
                "Chunk %s not in bloom filter, skipping discovery",
                chunk_hash.hex()[:16],
            )
            return []  # Definitely not available (no false negatives)

        # Check catalog first for fast lookup
        peers = []
        if self.catalog:
            try:
                catalog_results = await self.catalog.get_peers_by_chunks([chunk_hash])
                if chunk_hash in catalog_results:
                    catalog_peers = catalog_results[chunk_hash]
                    # Convert to PeerInfo objects
                    for ip, port in catalog_peers:
                        peers.append(PeerInfo(ip=ip, port=port))
                    self.logger.debug(
                        "Found %d peers for chunk %s in catalog",
                        len(peers),
                        chunk_hash.hex()[:16],
                    )
            except Exception as e:
                self.logger.warning("Error querying catalog: %s", e)

        # Query DHT for chunk
        if self.dht:
            try:
                dht_results = []

                # Try different DHT methods
                if hasattr(self.dht, "get_chunk_peers"):
                    dht_results = await self.dht.get_chunk_peers(chunk_hash)
                elif hasattr(
                    self.dht, "get_peers"
                ):  # pragma: no cover - Standard DHT get_peers method path (less common than get_chunk_peers)
                    # Standard DHT get_peers method
                    dht_results = await self.dht.get_peers(
                        chunk_hash
                    )  # pragma: no cover - Same context
                elif hasattr(
                    self.dht, "find_value"
                ):  # pragma: no cover - Alternative DHT method path, less common
                    # BEP 44 find_value method
                    value = await self.dht.find_value(
                        chunk_hash
                    )  # pragma: no cover - Same context
                    if value:  # pragma: no cover - Same context
                        # Extract peer info from value
                        peer_info = self._extract_peer_from_dht_value(
                            value
                        )  # pragma: no cover - Same context
                        if peer_info:  # pragma: no cover - Same context
                            dht_results = [peer_info]  # pragma: no cover - Same context

                # Extract peer info from DHT results
                for result in dht_results:
                    if isinstance(result, PeerInfo):
                        peers.append(result)
                    else:  # pragma: no cover - DHT result format conversion path
                        peer_info = self._extract_peer_from_dht(
                            result
                        )  # pragma: no cover - Same context
                        if peer_info:  # pragma: no cover - Same context
                            peers.append(peer_info)  # pragma: no cover - Same context

                self.logger.debug(
                    "Found %d peers for chunk %s via DHT",
                    len(peers),
                    chunk_hash.hex()[:16],
                )
                if callable(self.discovery_backend_success_notifier) and dht_results:
                    self.discovery_backend_success_notifier("dht")
            except Exception as e:
                self.logger.warning(
                    "Failed to query DHT for chunk: %s",
                    e,
                )

        # Query tracker if available
        if self.tracker:
            try:
                tracker_peers: list[PeerInfo] = []
                if hasattr(self.tracker, "get_chunk_peers"):
                    tracker_peers = await self.tracker.get_chunk_peers(
                        chunk_hash, workspace_id_hex=workspace_id_hex
                    )
                    peers.extend(tracker_peers)

                self.logger.debug(
                    "Found %d peers for chunk %s via tracker",
                    len(peers),
                    chunk_hash.hex()[:16],
                )
                if callable(self.discovery_backend_success_notifier) and tracker_peers:
                    self.discovery_backend_success_notifier("tracker")
            except Exception as e:
                self.logger.warning(
                    "Failed to query tracker for chunk: %s",
                    e,
                )

        # Query PEX if available (sync, returns peers known to have chunk)
        if self.pex_manager and hasattr(self.pex_manager, "get_peers_with_chunks"):
            try:
                pex_result = self.pex_manager.get_peers_with_chunks([chunk_hash])
                if chunk_hash in pex_result:
                    peers.extend(pex_result[chunk_hash])
                self.logger.debug(
                    "Found %d peers for chunk %s via PEX",
                    len(pex_result.get(chunk_hash, [])),
                    chunk_hash.hex()[:16],
                )
            except Exception as e:
                self.logger.warning("Failed to query PEX for chunk: %s", e)

        # Remove duplicates
        deduplicated_peers = self._deduplicate_peers(peers)

        # Optional strict-workspace filtering using session-provided peer authorizer.
        # Peer key format follows existing connection id convention: "ip:port".
        if callable(self.peer_authorizer):
            filtered: list[PeerInfo] = []
            for peer in deduplicated_peers:
                peer_key = f"{peer.ip}:{peer.port}"
                with contextlib.suppress(Exception):
                    if self.peer_authorizer(peer_key, None):
                        filtered.append(peer)
            deduplicated_peers = filtered

        # Cache result
        self._discovery_cache[chunk_hash] = (deduplicated_peers, time.time())

        return deduplicated_peers

    async def find_chunks_peers_batch(
        self, chunk_hashes: list[bytes]
    ) -> dict[bytes, list[PeerInfo]]:
        """Find peers for multiple chunks in parallel.

        Queries DHT and tracker (if configured) for multiple chunks concurrently.

        Args:
            chunk_hashes: List of 32-byte chunk hashes

        Returns:
            Dictionary mapping chunk_hash -> list of peers

        """
        # Validate all chunk hashes
        for chunk_hash in chunk_hashes:
            if len(chunk_hash) != 32:
                msg = f"Chunk hash must be 32 bytes, got {len(chunk_hash)}"
                raise ValueError(msg)

        # Pre-filter using bloom filter if available
        filtered_hashes = chunk_hashes
        if self.bloom_filter:
            filtered_hashes = [
                h for h in chunk_hashes if self.bloom_filter.has_chunk(h)
            ]
            if not filtered_hashes:
                self.logger.debug(
                    "All %d chunks filtered out by bloom filter",
                    len(chunk_hashes),
                )
                return {h: [] for h in chunk_hashes}

        # Use semaphore to limit concurrent queries
        from asyncio import Semaphore

        semaphore = Semaphore(50)  # Max 50 concurrent queries
        results: dict[bytes, list[PeerInfo]] = {}

        async def query_chunk(chunk_hash: bytes) -> tuple[bytes, list[PeerInfo]]:
            async with semaphore:
                peers = await self.find_chunk_peers(chunk_hash)
                return (chunk_hash, peers)

        # Query all chunks in parallel
        tasks = [query_chunk(chunk_hash) for chunk_hash in filtered_hashes]
        query_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        for result in query_results:
            if isinstance(result, tuple) and len(result) == 2:
                chunk_hash, chunk_peers = result
                results[chunk_hash] = chunk_peers
            elif isinstance(result, Exception):
                self.logger.warning("Error in batch chunk query: %s", result)

        # Add empty results for filtered-out chunks
        for chunk_hash in chunk_hashes:
            if chunk_hash not in results:
                results[chunk_hash] = []

        self.logger.debug(
            "Batch query for %d chunks: found peers for %d chunks",
            len(chunk_hashes),
            sum(1 for peers in results.values() if peers),
        )

        return results

    def set_peer_authorizer(self, authorizer: Any) -> None:
        """Set callback used to filter discovered peers by workspace auth policy."""
        self.peer_authorizer = authorizer

    def set_discovery_backend_success_notifier(self, notifier: Any) -> None:
        """Set callback used to mark backend last_success timestamps."""
        self.discovery_backend_success_notifier = notifier

    def register_pex_manager(self, pex_manager: Any) -> None:
        """Register PEX manager for chunk exchange.

        Args:
            pex_manager: AsyncPexManager instance

        """
        self.pex_manager = pex_manager

        # Register callback for PEX chunks (signature: chunk_hashes, optional peer_ip, optional peer_port)
        def on_pex_chunks(
            chunk_hashes: list[bytes],
            peer_ip: Optional[str] = None,
            peer_port: Optional[int] = None,
        ) -> None:
            """Handle chunks received via PEX; update catalog with peer when available."""
            peer_info = (
                (peer_ip, peer_port)
                if peer_ip is not None and peer_port is not None
                else None
            )

            async def _add_to_catalog() -> None:
                for chunk_hash in chunk_hashes:
                    if len(chunk_hash) != 32 or not self.catalog:
                        continue
                    try:
                        await self.catalog.add_chunk(chunk_hash, peer_info)
                    except Exception as e:
                        self.logger.warning("Error updating catalog from PEX: %s", e)

            try:
                loop = asyncio.get_running_loop()
                task = loop.create_task(_add_to_catalog())
                task.add_done_callback(lambda _finished: None)
            except RuntimeError:
                pass

        # Add callback to PEX manager (sync callback)
        if hasattr(pex_manager, "chunk_callbacks"):
            pex_manager.chunk_callbacks.append(on_pex_chunks)

    async def download_chunk(
        self,
        chunk_hash: bytes,
        peer: PeerInfo,
        torrent_data: Optional[dict[str, Any]] = None,
        connection_manager: Optional[Any] = None,  # type: ignore[assignment]
    ) -> bytes:
        """Download chunk from peer using BitTorrent protocol extension.

        Uses BEP 10 extension protocol with Xet extension for chunk requests.

        Args:
            chunk_hash: 32-byte chunk hash
            peer: Peer that has the chunk
            torrent_data: Torrent data for connection (required)
            connection_manager: AsyncPeerConnectionManager instance (optional)

        Returns:
            Chunk data bytes

        Raises:
            ValueError: If download fails
            NotImplementedError: If extension protocol not available

        """
        if len(chunk_hash) != 32:
            msg = f"Chunk hash must be 32 bytes, got {len(chunk_hash)}"
            raise ValueError(msg)

        # Get extension manager and Xet extension (prefer injected manager)
        if self.extension_manager is None:
            error_msg = "XetCAS download requires an injected extension_manager"
            self.logger.debug(error_msg)
            raise NotImplementedError(error_msg)
        extension_manager = self.extension_manager
        extension_protocol = extension_manager.get_extension("protocol")
        xet_ext = extension_manager.get_extension("xet")

        if not extension_protocol:  # pragma: no cover - Extension protocol unavailable path, tested in integration tests
            msg = "Extension protocol not available"
            raise NotImplementedError(msg)  # pragma: no cover - Same context

        if not xet_ext:  # pragma: no cover - Xet extension not registered path, tested in integration tests
            msg = "Xet extension not registered"
            raise NotImplementedError(msg)  # pragma: no cover - Same context

        # Get or create connection to peer
        connection = None
        connection_created = False  # Track if we created the connection
        try:
            # Try to get existing connection from connection manager first
            if connection_manager:
                peer_key = str(peer)
                async with connection_manager.connection_lock:
                    connection = connection_manager.connections.get(peer_key)

            # If no connection, establish one with handshake
            if not connection:  # pragma: no cover - New connection establishment path, tested in integration tests
                if not torrent_data or "info_hash" not in torrent_data:
                    msg = (
                        "torrent_data with info_hash is required when no existing "
                        "connection is available for chunk download"
                    )
                    raise ValueError(msg)
                self.logger.debug(
                    "No existing connection to peer %s, establishing new connection",
                    peer,
                )  # pragma: no cover - Same context
                connection = await self._establish_peer_connection(
                    peer, torrent_data
                )  # pragma: no cover - Same context
                connection_created = True  # pragma: no cover - Same context

            # Check if peer supports Xet extension
            # Note: For newly created connections, extension handshake may not have
            # completed yet. We'll try the request anyway and handle errors.
            peer_id = str(peer)
            peer_supports_xet = extension_protocol.peer_supports_extension(
                peer_id, "xet"
            )

            if not peer_supports_xet:
                # For new connections, extension handshake may not be complete
                # Try sending request anyway - if peer doesn't support it, we'll get an error
                if (
                    connection_created
                ):  # pragma: no cover - New connection extension handshake timing path
                    self.logger.debug(
                        "Extension handshake may not be complete for new connection to %s, "
                        "attempting chunk request anyway",
                        peer,
                    )  # pragma: no cover - Same context
                else:
                    msg = f"Peer {peer} does not support Xet extension"
                    raise ValueError(msg)

            xet_message_id = extension_protocol.get_peer_message_id(peer_id, "xet")
            if xet_message_id is None:
                msg = f"Peer {peer} has not advertised an Xet extension ID"
                raise ValueError(msg)

            # Encode chunk request
            request_payload = xet_ext.encode_chunk_request(chunk_hash)

            # Send extension message
            if (
                not connection or not connection.writer
            ):  # pragma: no cover - Connection state validation, defensive check
                msg = f"Connection to peer {peer} not available"
                raise ValueError(msg)  # pragma: no cover - Same context

            # Send message: <length><message_id_20><extension_id><payload>
            from ccbt.protocols.bittorrent_v2 import _send_extension_message

            sent = await _send_extension_message(
                connection, xet_message_id, request_payload
            )

            if (
                not sent
            ):  # pragma: no cover - Message send failure path, defensive error handling
                msg = f"Failed to send chunk request to peer {peer}"
                raise ValueError(msg)  # pragma: no cover - Same context

            self.logger.debug(
                "Sent chunk request for %s to peer %s",
                chunk_hash.hex()[:16],
                peer,
            )

            # Receive response
            from ccbt.protocols.bittorrent_v2 import _receive_extension_message

            response = await _receive_extension_message(connection, timeout=30.0)

            if not response:  # pragma: no cover - No response timeout path, tested in integration tests
                msg = f"No response from peer {peer} for chunk request"
                raise ValueError(msg)  # pragma: no cover - Same context

            extension_id, response_payload = response

            # Verify it's from Xet extension
            if (
                extension_id != xet_message_id
            ):  # pragma: no cover - Protocol validation error path, defensive check
                msg = (
                    f"Unexpected extension ID in response: "
                    f"expected {xet_message_id}, got {extension_id}"
                )
                raise ValueError(msg)  # pragma: no cover - Same context

            # Decode response
            if (
                len(response_payload) < 1
            ):  # pragma: no cover - Invalid payload validation, defensive check
                msg = "Invalid response payload"
                raise ValueError(msg)  # pragma: no cover - Same context

            message_type = response_payload[0]

            if message_type == 0x02:  # CHUNK_RESPONSE
                _request_id, chunk_data = xet_ext.decode_chunk_response(
                    response_payload
                )

                # Verify chunk hash
                from ccbt.storage.xet_hashing import XetHasher

                hasher = XetHasher()
                computed_hash = hasher.compute_chunk_hash(chunk_data)

                if computed_hash != chunk_hash:
                    msg = (
                        f"Chunk hash mismatch: expected {chunk_hash.hex()[:16]}, "
                        f"got {computed_hash.hex()[:16]}"
                    )
                    raise ValueError(msg)

                self.logger.debug(
                    "Successfully downloaded chunk %s (%d bytes) from peer %s",
                    chunk_hash.hex()[:16],
                    len(chunk_data),
                    peer,
                )

                return chunk_data

            if message_type == 0x03:  # CHUNK_NOT_FOUND
                msg = f"Chunk {chunk_hash.hex()[:16]} not found on peer {peer}"
                raise ValueError(msg)

            if message_type == 0x04:  # CHUNK_ERROR
                msg = f"Error retrieving chunk {chunk_hash.hex()[:16]} from peer {peer}"
                raise ValueError(msg)

            # pragma: no cover - Unknown message type error path, defensive protocol validation
            msg = f"Unknown response message type: {message_type:02x}"  # pragma: no cover - Same context
            raise ValueError(msg)  # pragma: no cover - Same context

        except Exception as e:
            self.logger.exception(
                "Failed to download chunk %s from peer %s",
                chunk_hash.hex()[:16],
                peer,
            )
            error_msg = f"Failed to download chunk: {e}"
            raise ValueError(error_msg) from e

        finally:
            # Clean up connection if we created it
            if (
                connection_created and connection
            ):  # pragma: no cover - Connection cleanup in finally block, defensive cleanup
                try:  # pragma: no cover - Same context
                    if connection.writer:  # pragma: no cover - Same context
                        connection.writer.close()  # pragma: no cover - Same context
                        await (
                            connection.writer.wait_closed()
                        )  # pragma: no cover - Same context
                    self.logger.debug(
                        "Closed temporary connection to peer %s",
                        peer,
                    )  # pragma: no cover - Same context
                except Exception as cleanup_error:  # pragma: no cover - Connection cleanup exception handling, defensive error path
                    self.logger.debug(
                        "Error closing connection to peer %s: %s",
                        peer,
                        cleanup_error,
                    )  # pragma: no cover - Same context

    def _extract_peer_from_dht(self, dht_result: Any) -> Optional[PeerInfo]:  # type: ignore[return]
        """Extract PeerInfo from DHT result.

        Args:
            dht_result: DHT query result

        Returns:
            PeerInfo if extractable, None otherwise

        """
        try:
            if isinstance(dht_result, PeerInfo):
                return dht_result

            if isinstance(dht_result, dict):
                if not self._verify_signed_chunk_metadata(dht_result):
                    return None
                # Extract IP and port from dict
                ip = dht_result.get("ip") or dht_result.get("address")
                port = dht_result.get("port")

                if ip and port:
                    return PeerInfo(ip=ip, port=port)

            if isinstance(dht_result, (list, tuple)) and len(dht_result) >= 2:
                # Assume (ip, port) tuple
                return PeerInfo(ip=str(dht_result[0]), port=int(dht_result[1]))

        except Exception as e:
            self.logger.debug("Failed to extract peer from DHT result: %s", e)

        return None

    def _extract_peer_from_dht_value(self, value: Any) -> Optional[PeerInfo]:  # type: ignore[return]
        """Extract PeerInfo from DHT stored value (BEP 44).

        Args:
            value: DHT stored value

        Returns:
            PeerInfo if extractable, None otherwise

        """
        try:
            # Check if it's a chunk metadata entry
            if isinstance(value, dict) and value.get("type") == "xet_chunk":
                if not self._verify_signed_chunk_metadata(value):
                    return None
                # Extract peer info from metadata
                ip = value.get("ip") or value.get("address")
                port = value.get("port")
                if ip and port:
                    return PeerInfo(ip=str(ip), port=int(port))
                peer_id = value.get("peer_id")
                if peer_id:
                    # Try to get peer info from peer_id
                    # This would require additional DHT lookup
                    pass  # pragma: no cover - Future feature path, not yet implemented
        except (
            Exception
        ):  # pragma: no cover - Defensive exception handling in peer extraction
            pass  # pragma: no cover - Same context

        return None

    def _deduplicate_peers(self, peers: list[PeerInfo]) -> list[PeerInfo]:
        """Remove duplicate peers.

        Args:
            peers: List of peers

        Returns:
            List of unique peers

        """
        seen = set()
        unique_peers = []

        for peer in peers:
            peer_key = (peer.ip, peer.port)
            if peer_key not in seen:
                seen.add(peer_key)
                unique_peers.append(peer)

        return unique_peers

    def register_local_chunk(self, chunk_hash: bytes, local_path: str) -> None:
        """Register a locally stored chunk.

        Args:
            chunk_hash: 32-byte chunk hash
            local_path: Path to local chunk file

        """
        if len(chunk_hash) != 32:
            msg = f"Chunk hash must be 32 bytes, got {len(chunk_hash)}"
            raise ValueError(msg)

        self.local_chunks[chunk_hash] = local_path
        self.logger.debug(
            "Registered local chunk %s at %s",
            chunk_hash.hex()[:16],
            local_path,
        )

    def get_local_chunk_path(self, chunk_hash: bytes) -> Optional[str]:
        """Get local path for a chunk if available.

        Args:
            chunk_hash: 32-byte chunk hash

        Returns:
            Local path if available, None otherwise

        """
        return self.local_chunks.get(chunk_hash)

    async def _establish_peer_connection(
        self,
        peer: PeerInfo,
        torrent_data: dict[str, Any],
        timeout: float = 30.0,
    ) -> AsyncPeerConnection:  # type: ignore[type-arg]  # AsyncPeerConnection uses conditionally imported types
        """Establish BitTorrent connection with peer and perform handshake.

        This method creates a TCP connection, performs the BitTorrent handshake,
        and returns an AsyncPeerConnection ready for extension protocol messages.

        Args:
            peer: Peer to connect to
            torrent_data: Torrent data dictionary containing info_hash
            timeout: Connection timeout in seconds

        Returns:
            AsyncPeerConnection with established handshake

        Raises:
            ValueError: If connection or handshake fails
            HandshakeError: If handshake validation fails

        """
        # Extract required data from torrent_data
        info_hash = torrent_data.get("info_hash")
        if not info_hash:
            msg = "torrent_data must contain 'info_hash'"
            raise ValueError(msg)

        if len(info_hash) != 20:
            msg = f"Info hash must be 20 bytes, got {len(info_hash)}"
            raise ValueError(msg)

        # Generate peer ID if not provided
        peer_id = b"-CC0101-" + b"x" * 12  # Default peer ID

        # Create connection object
        connection = AsyncPeerConnection(peer_info=peer, torrent_data=torrent_data)
        connection.state = ConnectionState.CONNECTING

        try:
            # Establish TCP connection
            self.logger.debug(
                "Connecting to peer %s:%s for chunk download",
                peer.ip,
                peer.port,
            )

            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(peer.ip, peer.port),
                timeout=timeout,
            )

            connection.reader = reader
            connection.writer = writer
            connection.state = ConnectionState.CONNECTED

            self.logger.debug("TCP connection established, performing handshake")

            # Perform BitTorrent handshake
            connection.state = ConnectionState.HANDSHAKE_SENT

            # Create and send handshake
            handshake = Handshake(info_hash, peer_id)
            handshake_data = handshake.encode()

            writer.write(handshake_data)
            await writer.drain()

            self.logger.debug("Handshake sent, waiting for peer response")

            # Receive and validate peer handshake
            peer_handshake_data = await asyncio.wait_for(
                reader.readexactly(68),
                timeout=timeout,
            )

            peer_handshake = Handshake.decode(peer_handshake_data)
            connection.peer_info.peer_id = peer_handshake.peer_id
            connection.state = ConnectionState.HANDSHAKE_RECEIVED

            # Validate handshake
            if peer_handshake.info_hash != info_hash:
                msg = (
                    f"Info hash mismatch: expected {info_hash.hex()[:16]}, "
                    f"got {peer_handshake.info_hash.hex()[:16]}"
                )
                raise HandshakeError(msg)

            self.logger.debug(
                "Handshake successful with peer %s (peer_id: %s)",
                peer,
                peer_handshake.peer_id.hex()[:16]
                if peer_handshake.peer_id
                else "unknown",
            )

            # Connection is now ready for extension protocol messages
            return connection

        except asyncio.TimeoutError as e:
            self.logger.warning(
                "Connection to peer %s timed out: %s",
                peer,
                e,
            )
            if connection.writer:  # pragma: no cover - Connection cleanup in exception handler, defensive cleanup path
                try:  # pragma: no cover - Same context
                    connection.writer.close()  # pragma: no cover - Same context
                    await (
                        connection.writer.wait_closed()
                    )  # pragma: no cover - Same context
                except Exception:  # pragma: no cover - Connection cleanup exception handling, defensive error path
                    pass  # pragma: no cover - Same context
            msg = f"Connection to peer {peer} timed out"
            raise ValueError(msg) from e

        except HandshakeError as e:
            self.logger.warning(
                "Handshake failed with peer %s: %s",
                peer,
                e,
            )
            if connection.writer:  # pragma: no cover - Connection cleanup in exception handler, defensive cleanup path
                try:  # pragma: no cover - Same context
                    connection.writer.close()  # pragma: no cover - Same context
                    await (
                        connection.writer.wait_closed()
                    )  # pragma: no cover - Same context
                except Exception:  # pragma: no cover - Connection cleanup exception handling, defensive error path
                    pass  # pragma: no cover - Same context
            raise

        except Exception as e:  # pragma: no cover - General exception handler for connection establishment failures, defensive error path
            self.logger.exception(
                "Failed to establish connection to peer %s",
                peer,
            )  # pragma: no cover - Same context
            if connection.writer:  # pragma: no cover - Connection cleanup in exception handler, defensive cleanup path
                try:  # pragma: no cover - Same context
                    connection.writer.close()  # pragma: no cover - Same context
                    await (
                        connection.writer.wait_closed()
                    )  # pragma: no cover - Same context
                except Exception:  # pragma: no cover - Connection cleanup exception handling, defensive error path
                    pass  # pragma: no cover - Same context
            msg = f"Failed to establish connection to peer {peer}: {e}"  # pragma: no cover - Same context
            raise ValueError(msg) from e  # pragma: no cover - Same context
