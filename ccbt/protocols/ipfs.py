"""IPFS protocol implementation.

from __future__ import annotations

Provides IPFS integration for content-addressed storage
and hybrid BitTorrent/IPFS mode.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Callable, TypeVar

import ipfshttpclient
import multiaddr

# Compatibility shim for asyncio.to_thread (Python 3.9+)
if hasattr(asyncio, "to_thread"):
    to_thread = asyncio.to_thread  # type: ignore[assignment]
else:
    # Fallback for Python 3.8
    T = TypeVar("T")  # pragma: no cover - Python 3.8 compatibility

    async def to_thread(  # type: ignore[no-redef]
        func: Callable[..., T], *args: Any, **kwargs: Any
    ) -> T:  # pragma: no cover - Python 3.8 compatibility shim, not testable in 3.9+
        """Compatibility wrapper for asyncio.to_thread."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: func(*args, **kwargs))


from ccbt.models import PeerInfo, TorrentInfo
from ccbt.protocols.base import (
    Protocol,
    ProtocolCapabilities,
    ProtocolState,
    ProtocolType,
)
from ccbt.utils.events import Event, EventType, emit_event


@dataclass
class IPFSPeer:
    """IPFS peer information."""

    peer_id: str
    multiaddr: str
    protocols: list[str]
    last_seen: float = 0.0
    bytes_sent: int = 0
    bytes_received: int = 0


@dataclass
class IPFSContent:
    """IPFS content information."""

    cid: str  # Content Identifier
    size: int
    blocks: list[str]
    links: list[dict[str, Any]]
    last_accessed: float = 0.0


class IPFSProtocol(Protocol):
    """IPFS protocol implementation."""

    def __init__(self, session_manager: Any | None = None):
        """Initialize IPFS protocol.

        Args:
            session_manager: Optional session manager reference for accessing shared components

        """
        super().__init__(ProtocolType.IPFS)

        # CRITICAL FIX: Store session manager reference for consistency
        # This allows protocol to use shared components if needed in the future
        self.session_manager = session_manager

        # Configuration will be set by session manager
        self.config: Any | None = None

        # IPFS-specific capabilities
        self.capabilities = ProtocolCapabilities(
            supports_encryption=True,
            supports_metadata=True,
            supports_pex=False,
            supports_dht=True,
            supports_webrtc=False,
            supports_ipfs=True,
            max_connections=1000,
            supports_ipv6=True,
        )

        # IPFS configuration
        self.ipfs_gateway_urls: list[str] = [
            "https://ipfs.io/ipfs/",
            "https://gateway.pinata.cloud/ipfs/",
            "https://cloudflare-ipfs.com/ipfs/",
        ]

        self.ipfs_api_url: str = "http://127.0.0.1:5001"
        self.ipfs_peers: dict[str, IPFSPeer] = {}
        self.ipfs_content: dict[str, IPFSContent] = {}

        # DHT configuration
        self.dht_bootstrap_nodes: list[str] = [
            "/ip4/104.131.131.82/tcp/4001/p2p/QmaCpDMGvV2BGHeYERUEnRQAwe3N8SzbUtfsmvsqQLuvuJ",
            "/ip4/104.131.131.82/udp/4001/quic/p2p/QmaCpDMGvV2BGHeYERUEnRQAwe3N8SzbUtfsmvsqQLuvuJ",
        ]

        # IPFS client and connection state
        self._ipfs_client: ipfshttpclient.Client | None = None
        self._ipfs_connected: bool = False
        self._connection_retries: int = 0
        self._last_connection_attempt: float = 0.0

        # Message handling
        self._message_queue: dict[str, list[bytes]] = {}
        self._peer_message_queues: dict[str, asyncio.Queue[bytes]] = {}
        self._message_buffers: dict[str, bytes] = {}

        # Content tracking
        self._pinned_cids: set[str] = set()
        self._discovery_cache: dict[str, tuple[list[str], float]] = {}
        self._content_stats_cache: dict[str, tuple[dict[str, Any], float]] = {}

        # Logger
        self.logger = logging.getLogger(__name__)

    async def start(self) -> None:
        """Start IPFS protocol."""
        try:
            # Connect to IPFS network
            await self._connect_to_ipfs_network()

            # Set state to connected
            self.set_state(ProtocolState.CONNECTED)

            # Emit protocol started event
            await emit_event(
                Event(
                    event_type=EventType.PROTOCOL_STARTED.value,
                    data={
                        "protocol_type": "ipfs",
                        "timestamp": time.time(),
                    },
                ),
            )

        except Exception:  # pragma: no cover - Exception re-raise
            self.set_state(ProtocolState.ERROR)
            raise

    async def stop(self) -> None:
        """Stop IPFS protocol."""
        try:
            # Disconnect from IPFS network
            await self._disconnect_from_ipfs_network()

            # Set state to disconnected
            self.set_state(ProtocolState.DISCONNECTED)

            # Emit protocol stopped event
            await emit_event(
                Event(
                    event_type=EventType.PROTOCOL_STOPPED.value,
                    data={
                        "protocol_type": "ipfs",
                        "timestamp": time.time(),
                    },
                ),
            )

        except Exception:  # pragma: no cover - Exception re-raise
            self.set_state(ProtocolState.ERROR)
            raise

    async def _connect_to_ipfs_network(self) -> None:
        """Connect to IPFS network."""
        api_url = self.ipfs_api_url
        timeout = 30  # Default timeout in seconds

        self._last_connection_attempt = time.time()

        try:
            # Connect to IPFS daemon
            self._ipfs_client = await to_thread(
                ipfshttpclient.connect, api_url, timeout=timeout
            )

            # Verify connection by getting node ID
            node_id = await to_thread(self._ipfs_client.id)
            if not node_id or "ID" not in node_id:
                msg = "Failed to verify IPFS connection"
                raise ConnectionError(msg)

            self._ipfs_connected = True
            self._connection_retries = 0
            self.logger.info("Connected to IPFS daemon at %s", api_url)

            # Emit peer discovered event (our own node)
            if "ID" in node_id:
                await emit_event(
                    Event(
                        event_type=EventType.IPFS_PEER_DISCOVERED.value,
                        data={
                            "peer_id": node_id["ID"],
                            "addresses": node_id.get("Addresses", []),
                            "timestamp": time.time(),
                        },
                    ),
                )

        except ipfshttpclient.exceptions.ConnectionError as e:
            self._ipfs_connected = False
            self._connection_retries += 1
            self.logger.exception("Failed to connect to IPFS daemon at %s", api_url)
            msg = f"IPFS daemon unavailable at {api_url}"
            raise ConnectionError(msg) from e

        except ipfshttpclient.exceptions.TimeoutError as e:
            self._ipfs_connected = False
            self._connection_retries += 1
            self.logger.exception("Timeout connecting to IPFS daemon at %s", api_url)
            msg = f"IPFS daemon connection timeout at {api_url}"
            raise TimeoutError(msg) from e

        except Exception:  # pragma: no cover - Generic exception handler
            self._ipfs_connected = False
            self._connection_retries += 1
            self.logger.exception("Unexpected error connecting to IPFS daemon")
            raise

    async def _disconnect_from_ipfs_network(self) -> None:
        """Disconnect from IPFS network."""
        # Close all peer connections
        peer_ids = list(self.ipfs_peers.keys())
        for peer_id in peer_ids:
            try:
                await self.disconnect_peer(peer_id)
            except (
                Exception
            ) as e:  # pragma: no cover - Generic peer disconnect error handler
                self.logger.warning("Error disconnecting peer %s: %s", peer_id, e)

        # Close IPFS client connection
        if self._ipfs_client is not None:
            try:
                # Wait for in-flight requests with timeout
                await asyncio.wait_for(to_thread(self._ipfs_client.close), timeout=5.0)
            except asyncio.TimeoutError:  # pragma: no cover - Timeout in cleanup
                self.logger.warning("Timeout waiting for IPFS client to close")
            except Exception as e:  # pragma: no cover - Generic cleanup error handler
                self.logger.warning("Error closing IPFS client: %s", e)
            finally:
                self._ipfs_client = None

        # Clean up resources
        self._ipfs_connected = False
        self.ipfs_peers.clear()
        self._message_queue.clear()
        self._peer_message_queues.clear()
        self._message_buffers.clear()

        self.logger.info("Disconnected from IPFS network")

    async def _check_ipfs_connection(self) -> bool:
        """Check IPFS connection health."""
        if not self._ipfs_connected or self._ipfs_client is None:
            return False

        try:
            # Ping the IPFS daemon
            await to_thread(self._ipfs_client.id)
            return True
        except Exception as e:  # pragma: no cover - Health check error handler
            self.logger.warning("IPFS connection health check failed: %s", e)
            self._ipfs_connected = False
            return False

    async def _reconnect_ipfs(self) -> bool:
        """Reconnect to IPFS network with exponential backoff."""
        max_retries = 3
        base_delay = 30  # seconds

        if self._connection_retries >= max_retries:
            self.logger.error(
                "Max reconnection attempts (%d) reached. IPFS connection failed.",
                max_retries,
            )
            return False

        # Exponential backoff: 30s, 60s, 120s
        delay = base_delay * (2**self._connection_retries)
        self.logger.info("Reconnecting to IPFS daemon in %d seconds...", delay)

        await asyncio.sleep(delay)

        try:
            await self._connect_to_ipfs_network()
            self.logger.info("Successfully reconnected to IPFS daemon")
            return True
        except Exception:
            self.logger.exception("Reconnection attempt failed")
            return False

    def _parse_multiaddr(self, addr_str: str) -> dict[str, Any]:
        """Parse multiaddr string into components."""
        try:
            addr = multiaddr.Multiaddr(addr_str)
            components = {}
            for protocol in addr.protocols():
                if protocol.name in {"ip4", "ip6"}:
                    components["ip"] = addr.value_for_protocol(protocol.code)
                elif protocol.name in {"tcp", "udp"}:
                    components["port"] = int(addr.value_for_protocol(protocol.code))
                elif protocol.name == "p2p":
                    components["peer_id"] = addr.value_for_protocol(protocol.code)
            return components
        except Exception as e:
            msg = f"Invalid multiaddr format: {addr_str}"
            raise ValueError(msg) from e

    def _validate_peer_info(self, peer_info: PeerInfo) -> bool:
        """Validate peer info has required fields."""
        return bool(
            peer_info.peer_id
            and peer_info.ip
            and peer_info.ip != "ipfs"
            and 0 < peer_info.port <= 65535
        )

    async def connect_peer(self, peer_info: PeerInfo) -> bool:
        """Connect to an IPFS peer."""
        if not self._ipfs_connected or self._ipfs_client is None:
            self.logger.warning("IPFS daemon not connected, cannot connect peer")
            return False

        if not self._validate_peer_info(peer_info):
            self.logger.warning("Invalid peer info for IPFS connection")
            return False

        try:
            # Parse multiaddr from peer info
            multiaddr_str = f"/ip4/{peer_info.ip}/tcp/{peer_info.port}"
            if peer_info.peer_id:
                peer_id_str = peer_info.peer_id.hex()
                multiaddr_str += f"/p2p/{peer_id_str}"

            # Validate multiaddr format
            try:
                self._parse_multiaddr(multiaddr_str)
            except ValueError as e:
                self.logger.warning("Invalid multiaddr: %s", e)
                return False

            # Connect to peer via IPFS daemon
            timeout = 30  # Default timeout
            try:
                await asyncio.wait_for(
                    to_thread(
                        self._ipfs_client.swarm.connect,  # type: ignore[attr-defined]
                        multiaddr_str,
                    ),
                    timeout=timeout,
                )
            except asyncio.TimeoutError as e:
                msg = f"Connection timeout to peer {multiaddr_str}"
                raise TimeoutError(msg) from e
            except ipfshttpclient.exceptions.Error as e:
                msg = f"Failed to connect to peer {multiaddr_str}"
                raise ConnectionError(msg) from e

            # Get peer ID from connection or use provided one
            peer_id = peer_info.peer_id.hex() if peer_info.peer_id else ""
            if not peer_id:
                # Try to get peer ID from IPFS daemon
                try:
                    peer_list = await to_thread(
                        self._ipfs_client.swarm.peers  # type: ignore[possibly-missing-attribute]
                    )
                    for peer in peer_list:
                        if peer.get("Addr") == multiaddr_str:
                            peer_id = peer.get("Peer", "")
                            break
                except (
                    Exception
                ):  # pragma: no cover - Silent fallback for peer ID lookup
                    pass

            # Create IPFS peer
            ipfs_peer = IPFSPeer(
                peer_id=peer_id,
                multiaddr=multiaddr_str,
                protocols=["/ipfs/bitswap/1.2.0"],
                last_seen=time.time(),
            )

            # Store peer using peer_id as key, fallback to IP
            peer_key = peer_id if peer_id else peer_info.ip
            self.ipfs_peers[peer_key] = ipfs_peer
            self.add_peer(peer_info)

            # Setup message listener for this peer
            await self._setup_message_listener(peer_key)

            # Flush any queued messages
            if peer_key in self._message_queue:
                queued_messages = self._message_queue[peer_key]
                del self._message_queue[peer_key]
                for msg in queued_messages:
                    await self.send_message(peer_key, msg)

            self.stats.connections_established += 1
            self.update_stats()

            self.logger.info("Connected to IPFS peer %s", peer_key)
            return True

        except (TimeoutError, ConnectionError) as e:
            self.stats.connections_failed += 1
            self.update_stats(errors=1)

            # Emit connection error event
            await emit_event(
                Event(
                    event_type=EventType.PEER_CONNECTION_FAILED.value,
                    data={
                        "protocol_type": "ipfs",
                        "peer_id": peer_info.peer_id.hex()
                        if peer_info.peer_id
                        else None,
                        "error": str(e),
                        "timestamp": time.time(),
                    },
                ),
            )

            return False
        except Exception:
            self.stats.connections_failed += 1
            self.update_stats(errors=1)
            self.logger.exception("Unexpected error connecting to IPFS peer")
            return False

    async def disconnect_peer(self, peer_id: str) -> None:
        """Disconnect from an IPFS peer."""
        if peer_id not in self.ipfs_peers:
            return

        ipfs_peer = self.ipfs_peers[peer_id]

        # Disconnect via IPFS daemon if connected
        if self._ipfs_connected and self._ipfs_client is not None:
            try:
                await to_thread(
                    self._ipfs_client.swarm.disconnect,  # type: ignore[attr-defined]
                    ipfs_peer.multiaddr,
                )
            except Exception as e:  # pragma: no cover - Disconnect error handler
                self.logger.warning("Error disconnecting peer via daemon: %s", e)

        # Clean up peer tracking
        del self.ipfs_peers[peer_id]
        self.remove_peer(peer_id)

        # Clean up message queues and buffers
        if peer_id in self._peer_message_queues:
            del self._peer_message_queues[peer_id]
        if peer_id in self._message_buffers:
            del self._message_buffers[peer_id]
        if peer_id in self._message_queue:
            del self._message_queue[peer_id]

    async def send_message(
        self,
        peer_id: str,
        message: bytes,
        want_list: list[str] | None = None,
        blocks: dict[str, bytes] | None = None,
    ) -> bool:
        """Send message to IPFS peer.

        Args:
            peer_id: IPFS peer ID to send message to
            message: Raw message bytes to send
            want_list: Optional list of CIDs to request from peer (Bitswap protocol)
            blocks: Optional dictionary of CID to block data we have available (Bitswap protocol)

        Returns:
            True if message sent successfully, False otherwise

        """
        if peer_id not in self.ipfs_peers:
            return False

        if not self._ipfs_connected or self._ipfs_client is None:
            # Queue message if not connected
            if peer_id not in self._message_queue:
                self._message_queue[peer_id] = []
            self._message_queue[peer_id].append(message)
            return False

        ipfs_peer = self.ipfs_peers[peer_id]

        # Format message with Bitswap protocol if want_list or blocks provided
        if want_list or blocks:
            formatted_message = self._format_bitswap_message(
                message, want_list=want_list, blocks=blocks
            )
        else:
            # Maintain backward compatibility: send raw bytes if no Bitswap params
            formatted_message = message

        # Validate message size (IPFS has limits)
        max_message_size = 1024 * 1024  # 1MB
        if len(formatted_message) > max_message_size:
            self.logger.warning(
                "Message too large for IPFS: %d bytes", len(formatted_message)
            )
            return False

        try:
            # Use IPFS pubsub for message sending
            # Create topic from peer_id for direct communication
            topic = f"/ccbt/peer/{peer_id}"

            # Send message via pubsub
            await to_thread(
                self._ipfs_client.pubsub.publish,  # type: ignore[attr-defined]
                topic,
                formatted_message,
            )

            ipfs_peer.bytes_sent += len(formatted_message)
            ipfs_peer.last_seen = time.time()

            self.update_stats(bytes_sent=len(formatted_message), messages_sent=1)
            return True

        except ipfshttpclient.exceptions.Error as e:
            self.logger.warning("Failed to send message to peer %s: %s", peer_id, e)
            self.update_stats(errors=1)
            return False
        except Exception:  # pragma: no cover - Generic error handler
            self.logger.exception("Unexpected error sending message")
            self.update_stats(errors=1)
            return False

    async def receive_message(
        self, peer_id: str, parse_bitswap: bool = True
    ) -> bytes | None:
        """Receive message from IPFS peer.

        Args:
            peer_id: IPFS peer ID to receive message from
            parse_bitswap: If True, attempt to parse Bitswap protocol messages

        Returns:
            Message payload bytes, or None if no message received

        """
        if peer_id not in self.ipfs_peers:
            return None

        if not self._ipfs_connected or self._ipfs_client is None:
            return None

        ipfs_peer = self.ipfs_peers[peer_id]

        # Ensure message queue exists for this peer
        if peer_id not in self._peer_message_queues:
            self._peer_message_queues[peer_id] = asyncio.Queue()

        message_queue = self._peer_message_queues[peer_id]

        try:
            # Wait for message with timeout (1 second)
            raw_message = await asyncio.wait_for(message_queue.get(), timeout=1.0)

            # Try to parse as Bitswap message if requested
            if parse_bitswap:
                try:
                    parsed = self._parse_bitswap_message(raw_message)
                    # If parsing succeeded and we got a payload, use it
                    if parsed.get("payload"):
                        message = parsed["payload"]
                    else:
                        # Not a Bitswap message or empty payload, return raw
                        message = raw_message
                except Exception:
                    # Parsing failed, return raw message (backward compatibility)
                    message = raw_message
            else:
                message = raw_message

            ipfs_peer.bytes_received += len(message)
            ipfs_peer.last_seen = time.time()
            self.update_stats(bytes_received=len(message), messages_received=1)

            return message

        except asyncio.TimeoutError:
            # No message received within timeout
            return None
        except Exception:  # pragma: no cover - Generic error handler
            self.logger.exception("Unexpected error receiving message")
            self.update_stats(errors=1)
            return None

    def _format_bitswap_message(
        self,
        message: bytes,
        want_list: list[str] | None = None,
        blocks: dict[str, bytes] | None = None,
    ) -> bytes:
        """Format message according to Bitswap protocol.

        Args:
            message: Raw message bytes to send
            want_list: List of CIDs to request from peer
            blocks: Dictionary of CID to block data that we have available

        Returns:
            Formatted Bitswap message as bytes (JSON encoded)

        """
        bitswap_msg = {
            "payload": message.hex() if message else "",
        }

        if want_list:
            bitswap_msg["want_list"] = want_list

        if blocks:
            # Convert block data to hex strings for JSON encoding
            blocks_hex = {cid: data.hex() for cid, data in blocks.items()}
            bitswap_msg["blocks"] = blocks_hex

        # Encode as JSON
        formatted = json.dumps(bitswap_msg).encode("utf-8")

        # Validate size limit (1MB max)
        # Note: hex encoding doubles size, so we need to check before encoding
        max_message_size = 1024 * 1024
        if len(formatted) > max_message_size:
            self.logger.warning(
                "Bitswap message too large: %d bytes (max %d)",
                len(formatted),
                max_message_size,
            )
            # Truncate payload if necessary (account for hex encoding: 2x size)
            # Reserve space for JSON metadata (estimate ~100 bytes)
            max_payload_bytes = (max_message_size - 500) // 2
            if len(message) > max_payload_bytes:
                truncated_msg = message[:max_payload_bytes]
                bitswap_msg["payload"] = truncated_msg.hex()
                formatted = json.dumps(bitswap_msg).encode("utf-8")
                # Final check - if still too large, return empty payload
                if len(formatted) > max_message_size:
                    bitswap_msg["payload"] = ""
                    formatted = json.dumps(bitswap_msg).encode("utf-8")

        return formatted

    def _parse_bitswap_message(self, data: bytes) -> dict[str, Any]:
        """Parse Bitswap protocol message.

        Args:
            data: Raw message bytes (JSON encoded)

        Returns:
            Dictionary with parsed components:
            - "payload": bytes (decoded from hex)
            - "want_list": list[str] (if present)
            - "blocks": dict[str, bytes] (if present)

        """
        try:
            # Decode JSON
            message_dict = json.loads(data.decode("utf-8"))

            result: dict[str, Any] = {}

            # Extract payload
            if "payload" in message_dict:
                payload_hex = message_dict["payload"]
                if payload_hex:
                    try:
                        result["payload"] = bytes.fromhex(payload_hex)
                    except ValueError as e:
                        self.logger.warning("Failed to decode payload hex: %s", e)
                        result["payload"] = b""
                else:
                    result["payload"] = b""
            else:
                result["payload"] = b""

            # Extract want_list
            if "want_list" in message_dict:
                want_list = message_dict["want_list"]
                if isinstance(want_list, list):
                    result["want_list"] = [str(cid) for cid in want_list]
                else:
                    result["want_list"] = []
            else:
                result["want_list"] = []

            # Extract blocks
            if "blocks" in message_dict:
                blocks_dict = message_dict["blocks"]
                if isinstance(blocks_dict, dict):
                    blocks = {}
                    for cid, block_hex in blocks_dict.items():
                        try:
                            blocks[str(cid)] = bytes.fromhex(block_hex)
                        except (ValueError, TypeError) as e:
                            self.logger.warning(
                                "Failed to decode block hex for CID %s: %s", cid, e
                            )
                    result["blocks"] = blocks
                else:
                    result["blocks"] = {}
            else:
                result["blocks"] = {}

            return result

        except json.JSONDecodeError as e:
            self.logger.warning("Failed to parse Bitswap message as JSON: %s", e)
            # Return empty result
            return {"payload": b"", "want_list": [], "blocks": {}}
        except UnicodeDecodeError as e:
            self.logger.warning("Failed to decode Bitswap message as UTF-8: %s", e)
            return {"payload": b"", "want_list": [], "blocks": {}}
        except Exception:  # pragma: no cover - Generic error handler
            self.logger.exception("Unexpected error parsing Bitswap message")
            return {"payload": b"", "want_list": [], "blocks": {}}

    async def _setup_message_listener(self, peer_id: str) -> None:
        """Setup pubsub subscription for receiving messages from a peer."""
        if not self._ipfs_connected or self._ipfs_client is None:
            return

        if peer_id not in self._peer_message_queues:
            self._peer_message_queues[peer_id] = asyncio.Queue()

        topic = f"/ccbt/peer/{peer_id}"

        try:
            # Subscribe to topic and process messages in background
            async def message_handler():
                try:
                    # Use pubsub subscribe to receive messages
                    # Subscribe returns synchronous generator, iterate in thread
                    for message in await to_thread(
                        lambda: list(self._ipfs_client.pubsub.subscribe(topic))  # type: ignore[possibly-missing-attribute]
                    ):
                        if peer_id in self._peer_message_queues:
                            await self._peer_message_queues[peer_id].put(
                                message["data"]
                            )
                except Exception as e:
                    self.logger.warning(  # pragma: no cover - Background task error
                        "Message listener error for peer %s: %s", peer_id, e
                    )

            # Start listener in background
            _task = asyncio.create_task(message_handler())  # noqa: RUF006 - Background task, reference not needed
            # Store task reference if needed for cleanup (optional)
            # self._message_listener_tasks[peer_id] = _task

        except Exception as e:
            self.logger.warning(
                "Failed to setup message listener for peer %s: %s", peer_id, e
            )

    async def announce_torrent(self, torrent_info: TorrentInfo) -> list[PeerInfo]:
        """Announce torrent to IPFS network."""
        peers = []

        try:
            # Convert torrent to IPFS content
            ipfs_content = await self._torrent_to_ipfs(torrent_info)

            # Find peers that have this content
            content_peers = await self._find_content_peers(ipfs_content.cid)

            # Convert IPFS peers to PeerInfo
            for peer_id in content_peers:
                peer_info = PeerInfo(
                    ip="ipfs",  # IPFS doesn't use traditional IP addresses
                    port=0,
                    peer_id=peer_id.encode(),
                )
                peers.append(peer_info)

        except Exception as e:  # pragma: no cover - Generic error handler in announce
            # Emit error event
            await emit_event(
                Event(
                    event_type=EventType.PROTOCOL_ERROR.value,
                    data={
                        "protocol_type": "ipfs",
                        "error": str(e),
                        "timestamp": time.time(),
                    },
                ),
            )

        return peers

    async def _torrent_to_ipfs(self, torrent_info: TorrentInfo) -> IPFSContent:
        """Convert torrent to IPFS content."""
        if not self._ipfs_connected or self._ipfs_client is None:
            # Fallback: create placeholder CID from info_hash
            content_hash = hashlib.sha256(torrent_info.info_hash).hexdigest()
            cid = f"Qm{content_hash[:44]}"  # IPFS CID format

            ipfs_content = IPFSContent(
                cid=cid,
                size=torrent_info.total_length,
                blocks=[],
                links=[],
            )
            self.ipfs_content[cid] = ipfs_content
            return ipfs_content

        try:
            # Create IPFS object representing torrent metadata
            # Structure: DAG node with links to piece blocks
            torrent_metadata = {
                "name": torrent_info.name,
                "info_hash": torrent_info.info_hash.hex(),
                "total_length": torrent_info.total_length,
                "piece_length": torrent_info.piece_length,
                "num_pieces": torrent_info.num_pieces,
                "files": [
                    {
                        "name": file.name,
                        "path": file.path,
                        "length": file.length,
                    }
                    for file in torrent_info.files
                ],
                "pieces": [piece.hex() for piece in torrent_info.pieces],
            }

            # Convert metadata to JSON bytes
            metadata_bytes = json.dumps(torrent_metadata, sort_keys=True).encode(
                "utf-8"
            )

            # Add metadata to IPFS
            metadata_cid = await to_thread(
                self._ipfs_client.add_bytes, metadata_bytes, cid_version=1
            )

            # Extract CID if it's a dict
            if isinstance(metadata_cid, dict):
                cid = metadata_cid.get("Hash", str(metadata_cid))
            else:
                cid = str(metadata_cid)

            # Note: TorrentInfo only contains piece hashes, not actual piece data
            # To create full DAG with piece blocks, piece data must be provided separately
            # For now, we create metadata structure and reference piece hashes

            # Create blocks list from piece hashes (for reference)
            # These are placeholders until actual piece data is available
            # Note: blocks list is reserved for future implementation when piece data is available
            # For now, blocks are not used - DAG creation happens when pieces are converted
            _blocks = [
                {
                    "hash": piece.hex(),
                    "index": i,
                    "size": min(
                        torrent_info.piece_length,
                        torrent_info.total_length - i * torrent_info.piece_length,
                    ),
                }
                for i, piece in enumerate(torrent_info.pieces)
            ]

            # Links will be populated when pieces are converted to blocks
            # For full DAG creation with piece data, use:
            # 1. Convert pieces to blocks: piece_blocks = [await _piece_to_block(piece_data, i, piece_length) for i, piece_data in enumerate(pieces)]
            # 2. Create DAG: root_cid = await _create_ipfs_dag_from_pieces(piece_blocks)
            links: list[dict[str, Any]] = []

            # Create IPFS content record
            # Note: blocks will be updated with actual CIDs when pieces are converted
            # For now, use empty list since blocks contains dicts, not CIDs (strings)
            ipfs_content = IPFSContent(
                cid=cid,
                size=torrent_info.total_length,
                blocks=[],  # Will be updated with actual CIDs when pieces are converted
                links=links,  # Will be populated from DAG structure
            )

            self.ipfs_content[cid] = ipfs_content

            # Auto-pin if enabled
            if (
                self.config
                and hasattr(self.config, "ipfs")
                and self.config.ipfs.enable_pinning
            ):
                await self.pin_content(cid)

            self.logger.info("Converted torrent to IPFS with CID %s", cid)
            return ipfs_content

        except Exception:  # pragma: no cover - Fallback error handler
            self.logger.exception("Error converting torrent to IPFS")
            # Fallback to placeholder
            content_hash = hashlib.sha256(torrent_info.info_hash).hexdigest()
            cid = f"Qm{content_hash[:44]}"

            ipfs_content = IPFSContent(
                cid=cid,
                size=torrent_info.total_length,
                blocks=[],
                links=[],
            )
            self.ipfs_content[cid] = ipfs_content
            return ipfs_content

    async def _piece_to_block(
        self,
        piece: bytes,
        index: int,
        piece_length: int,  # noqa: ARG002
    ) -> dict[str, Any]:
        """Convert torrent piece to IPFS block.

        Args:
            piece: Piece data bytes
            index: Piece index
            piece_length: Standard piece length (for size calculation)

        Returns:
            Dictionary with:
            - "cid": str (CID of the block)
            - "data": bytes (piece data)
            - "size": int (actual piece size)
            - "index": int (piece index)

        """
        # Calculate actual piece size (last piece may be smaller)
        actual_size = len(piece)

        # Generate CID v1 from piece data using multiformats
        # Use sha2-256 codec (standard for IPFS)
        try:
            # Hash the piece data (unused but kept for potential future use)
            _piece_hash = hashlib.sha256(piece).digest()

            # Create CID v1 using multiformats
            # First add the piece to IPFS to get the actual CID
            # For now, we'll use the IPFS client to generate the CID properly
            if self._ipfs_connected and self._ipfs_client is not None:
                # Add piece to IPFS to get proper CID
                cid_result = await to_thread(
                    self._ipfs_client.add_bytes, piece, cid_version=1
                )
                # Extract CID
                if isinstance(cid_result, dict):
                    cid_str = cid_result.get("Hash", "")
                else:
                    cid_str = str(cid_result)

                if cid_str:
                    return {
                        "cid": cid_str,
                        "data": piece,
                        "size": actual_size,
                        "index": index,
                    }

            # Fallback: create a hash-based identifier
            # This won't be a real CID but will work for internal tracking
            piece_hash_hex = hashlib.sha256(piece).hexdigest()
            # Format similar to CID v1 (bafy prefix for base32)
            cid_str = f"bafybei{piece_hash_hex[:46]}"

            return {
                "cid": cid_str,
                "data": piece,
                "size": actual_size,
                "index": index,
            }
        except Exception as e:
            self.logger.warning("Failed to generate CID for piece %d: %s", index, e)
            # Final fallback: create a simple hash-based identifier
            piece_hash_hex = hashlib.sha256(piece).hexdigest()
            cid_str = f"bafybei{piece_hash_hex[:46]}"
            return {
                "cid": cid_str,
                "data": piece,
                "size": actual_size,
                "index": index,
            }

    async def _create_ipfs_dag_from_pieces(self, pieces: list[dict[str, Any]]) -> str:
        """Create UnixFS DAG structure from IPFS blocks.

        Args:
            pieces: List of block dictionaries from _piece_to_block()

        Returns:
            Root CID (str) of the DAG

        """
        if not self._ipfs_connected or self._ipfs_client is None:
            msg = "IPFS daemon not connected"
            raise ConnectionError(msg)

        if not pieces:
            msg = "Cannot create DAG from empty pieces list"
            raise ValueError(msg)

        try:
            # IPFS has a limit on node size (typically 262144 bytes)
            max_node_size = 262144

            # If we have many pieces or large pieces, we need to create intermediate nodes
            # For simplicity, we'll create a single-level DAG linking all pieces sequentially
            # For large files, we'd need to chunk into multiple nodes

            # Create base object (empty UnixFS directory-like structure)
            base_obj = await to_thread(
                self._ipfs_client.object.new,  # type: ignore[attr-defined]
                "unixfs-dir",
            )

            # Extract object hash if it's a dict
            if isinstance(base_obj, dict):
                current_obj_hash = base_obj.get("Hash", "")
            else:
                current_obj_hash = str(base_obj)

            # Add links for each piece sequentially
            # For large files, we'd chunk pieces into groups
            piece_groups: list[list[dict[str, Any]]] = []
            current_group: list[dict[str, Any]] = []
            current_group_size = 0

            for piece in pieces:
                piece_size = piece.get("size", 0)
                # If adding this piece would exceed node size, start new group
                if current_group_size + piece_size > max_node_size and current_group:
                    piece_groups.append(current_group)
                    current_group = [piece]
                    current_group_size = piece_size
                else:
                    current_group.append(piece)
                    current_group_size += piece_size

            # Add remaining group
            if current_group:
                piece_groups.append(current_group)

            # First, ensure all piece blocks are added to IPFS
            # Add each piece block and get its CID
            piece_cids: list[str] = []
            for piece in pieces:
                piece_data = piece["data"]
                piece_cid_result = await to_thread(
                    self._ipfs_client.add_bytes,  # type: ignore[attr-defined]
                    piece_data,
                    cid_version=1,
                )
                # Extract CID
                if isinstance(piece_cid_result, dict):
                    piece_cid = piece_cid_result.get("Hash", piece["cid"])
                else:
                    piece_cid = str(piece_cid_result)
                piece_cids.append(piece_cid)
                # Update piece dict with actual CID
                piece["cid"] = piece_cid

            # If we have multiple groups, create intermediate nodes
            if len(piece_groups) > 1:
                # Create intermediate nodes for each group
                intermediate_nodes = []
                piece_idx = 0
                for group in piece_groups:
                    group_obj = await to_thread(
                        self._ipfs_client.object.new,  # type: ignore[attr-defined]
                        "unixfs-dir",
                    )
                    if isinstance(group_obj, dict):
                        group_hash = group_obj.get("Hash", "")
                    else:
                        group_hash = str(group_obj)

                    # Add links to pieces in this group
                    for piece in group:
                        piece_cid = piece_cids[piece_idx]
                        piece_idx += 1
                        # Add piece as a link (using object.patch.add_link)
                        patched_obj = await to_thread(
                            self._ipfs_client.object.patch.add_link,  # type: ignore[attr-defined]
                            group_hash,
                            f"piece_{piece['index']}",
                            piece_cid,
                        )
                        if isinstance(patched_obj, dict):
                            group_hash = patched_obj.get("Hash", group_hash)
                        else:
                            group_hash = str(patched_obj)

                    intermediate_nodes.append(group_hash)

                # Link intermediate nodes to root
                for i, node_hash in enumerate(intermediate_nodes):
                    patched_obj = await to_thread(
                        self._ipfs_client.object.patch.add_link,  # type: ignore[attr-defined]
                        current_obj_hash,
                        f"node_{i}",
                        node_hash,
                    )
                    if isinstance(patched_obj, dict):
                        current_obj_hash = patched_obj.get("Hash", current_obj_hash)
                    else:
                        current_obj_hash = str(patched_obj)
            else:
                # Single group: link pieces directly to root
                for i, piece in enumerate(pieces):
                    piece_cid = piece_cids[i]
                    # Add piece as a link
                    patched_obj = await to_thread(
                        self._ipfs_client.object.patch.add_link,  # type: ignore[attr-defined]
                        current_obj_hash,
                        f"piece_{piece['index']}",
                        piece_cid,
                    )
                    if isinstance(patched_obj, dict):
                        current_obj_hash = patched_obj.get("Hash", current_obj_hash)
                    else:
                        current_obj_hash = str(patched_obj)

            # Finalize the DAG
            root_cid = current_obj_hash
            self.logger.info("Created IPFS DAG with root CID %s", root_cid)
            return root_cid

        except Exception:
            self.logger.exception("Error creating IPFS DAG from pieces")
            raise

    async def _find_content_peers(self, cid: str) -> list[str]:
        """Find peers that have specific IPFS content."""
        # Check cache first
        if cid in self._discovery_cache:
            cached_peers, cached_time = self._discovery_cache[cid]
            cache_ttl = 300  # 5 minutes default
            if time.time() - cached_time < cache_ttl:
                return cached_peers

        if not self._ipfs_connected or self._ipfs_client is None:
            return []

        try:
            # Query IPFS DHT for content providers
            timeout = 30  # Default timeout
            providers = []

            # Run DHT query with timeout
            # Note: findprovs returns a synchronous generator, run it in a thread
            def query_dht():
                try:
                    return list(self._ipfs_client.dht.findprovs(cid))  # type: ignore[possibly-missing-attribute]
                except Exception as e:  # pragma: no cover - DHT query error handler
                    self.logger.warning("Error in DHT provider search: %s", e)
                    return []

            provider_results = await asyncio.wait_for(
                to_thread(query_dht),
                timeout=timeout,
            )

            # Process results
            for provider in provider_results:
                if isinstance(provider, dict):
                    peer_id = provider.get("ID", "")
                elif isinstance(provider, str):
                    peer_id = provider
                else:
                    continue

                if peer_id and self._validate_peer_id(peer_id):
                    providers.append(peer_id)

            # Cache results
            self._discovery_cache[cid] = (providers, time.time())

            return providers

        except asyncio.TimeoutError:
            self.logger.warning("DHT lookup timeout for CID %s", cid)
            return []
        except ipfshttpclient.exceptions.Error as e:
            self.logger.warning("DHT lookup failed for CID %s: %s", cid, e)
            # Retry logic for failed queries (max 2 retries)
            if (
                cid not in self._discovery_cache
                or time.time() - self._discovery_cache[cid][1] > 60
            ):
                # Only retry if cache is stale or doesn't exist
                try:
                    # Retry once
                    await asyncio.sleep(1)
                    provider_results = await asyncio.wait_for(
                        to_thread(lambda: list(self._ipfs_client.dht.findprovs(cid))),  # type: ignore[possibly-missing-attribute]
                        timeout=30,
                    )
                    providers = []
                    for provider in provider_results:
                        if isinstance(provider, dict):
                            peer_id = provider.get("ID", "")
                        elif isinstance(provider, str):
                            peer_id = provider
                        else:
                            continue
                        if peer_id and self._validate_peer_id(peer_id):
                            providers.append(peer_id)
                    if providers:
                        self._discovery_cache[cid] = (providers, time.time())
                        return providers
                except Exception:
                    pass  # Retry failed, return empty
            return []
        except Exception as e:
            self.logger.warning("Unexpected error in DHT lookup: %s", e)
            return []

    def _cache_discovery_result(
        self,
        cid: str,
        peers: list[str],
        ttl: int = 300,  # noqa: ARG002
    ) -> None:
        """Cache discovery result with TTL.

        Args:
            cid: Content ID to cache
            peers: List of peer IDs
            ttl: Time-to-live in seconds (default: 300)

        """
        self._discovery_cache[cid] = (peers, time.time())

    def _get_cached_discovery_result(
        self, cid: str, ttl: int = 300
    ) -> list[str] | None:
        """Get cached discovery result if valid.

        Args:
            cid: Content ID to look up
            ttl: Time-to-live in seconds (default: 300)

        Returns:
            List of peer IDs if cache is valid, None otherwise

        """
        if cid not in self._discovery_cache:
            return None

        cached_peers, cached_time = self._discovery_cache[cid]
        if time.time() - cached_time < ttl:
            return cached_peers

        # Cache expired, remove it
        del self._discovery_cache[cid]
        return None

    def _validate_peer_id(self, peer_id: str) -> bool:
        """Validate peer ID format (base58 CID format)."""
        if not peer_id:
            return False
        # Basic validation: peer IDs are typically base58 encoded, 46+ chars
        if len(peer_id) < 46:
            return False
        # Check for valid base58 characters (alphanumeric excluding 0, O, I, l)
        valid_chars = set("123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz")
        return all(c in valid_chars for c in peer_id)

    async def scrape_torrent(self, torrent_info: TorrentInfo) -> dict[str, int]:
        """Scrape torrent statistics from IPFS network."""
        stats = {
            "seeders": 0,
            "leechers": 0,
            "completed": 0,
        }

        try:
            # Convert torrent to IPFS content
            ipfs_content = await self._torrent_to_ipfs(torrent_info)

            # Get content statistics from IPFS
            content_stats = await self._get_content_stats(ipfs_content.cid)

            stats.update(content_stats)

        except Exception as e:  # pragma: no cover - Generic error handler in announce
            # Emit error event
            await emit_event(
                Event(
                    event_type=EventType.PROTOCOL_ERROR.value,
                    data={
                        "protocol_type": "ipfs",
                        "error": str(e),
                        "timestamp": time.time(),
                    },
                ),
            )

        return stats

    async def _get_content_stats(self, cid: str) -> dict[str, int]:
        """Get content statistics from IPFS."""
        # Check cache first
        if cid in self._content_stats_cache:
            cached_stats, cached_time = self._content_stats_cache[cid]
            if time.time() - cached_time < 60:  # 60 second TTL
                return {
                    "seeders": cached_stats.get("seeders", 0),
                    "leechers": cached_stats.get("leechers", 0),
                    "completed": cached_stats.get("completed", 0),
                }

        if not self._ipfs_connected or self._ipfs_client is None:
            return {"seeders": 0, "leechers": 0, "completed": 0}

        try:
            # Query IPFS for object statistics
            stats = await to_thread(
                self._ipfs_client.object.stat,  # type: ignore[attr-defined]
                cid,
            )

            # Extract statistics
            size = stats.get("CumulativeSize", 0)
            links_count = stats.get("NumLinks", 0)
            block_count = stats.get("NumLinks", 0)  # Links represent blocks

            # Cache the results
            stats_dict = {
                "size": size,
                "blocks_count": block_count,
                "links_count": links_count,
            }
            self._content_stats_cache[cid] = (stats_dict, time.time())

            # Get actual seeder count from DHT provider queries
            seeders = 0
            try:
                # Query DHT for providers
                providers = await self._find_content_peers(cid)
                seeders = len(providers)
            except Exception as e:
                self.logger.debug("Failed to get seeder count for CID %s: %s", cid, e)

            # Return enhanced stats
            return {
                "seeders": seeders,
                "leechers": 0,  # IPFS doesn't track leechers the same way
                "completed": 1 if size > 0 else 0,
                "size": size,
                "blocks_count": block_count,
            }

        except ipfshttpclient.exceptions.Error as e:
            self.logger.warning("Failed to get content stats for CID %s: %s", cid, e)
            return {"seeders": 0, "leechers": 0, "completed": 0}
        except Exception as e:  # pragma: no cover - Generic error handler
            self.logger.warning("Unexpected error getting content stats: %s", e)
            return {"seeders": 0, "leechers": 0, "completed": 0}

    async def add_content(self, data: bytes) -> str:
        """Add content to IPFS and return CID."""
        if not self._ipfs_connected or self._ipfs_client is None:
            self.logger.error("IPFS daemon not connected, cannot add content")
            return ""

        try:
            # Add content to IPFS daemon
            # Use add_bytes for direct binary data
            result = await to_thread(self._ipfs_client.add_bytes, data, cid_version=1)

            # Extract CID from result
            if isinstance(result, str):
                cid = result
            elif isinstance(result, dict):
                cid = result.get("Hash", "")
            else:
                cid = str(result)

            if not cid:
                msg = "IPFS daemon returned empty CID"
                raise ValueError(msg)

            # Pin content if enabled (handled by add_bytes with pin parameter if needed)
            # For now, we track it separately

            # Create IPFS content record
            ipfs_content = IPFSContent(
                cid=cid,
                size=len(data),
                blocks=[],  # Would need to extract from IPFS object
                links=[],
            )

            self.ipfs_content[cid] = ipfs_content

            # Emit content added event
            await emit_event(
                Event(
                    event_type=EventType.IPFS_CONTENT_ADDED.value,
                    data={
                        "cid": cid,
                        "size": len(data),
                        "timestamp": time.time(),
                    },
                ),
            )

            self.logger.info("Added content to IPFS with CID %s", cid)
            return cid

        except ipfshttpclient.exceptions.Error as e:
            self.logger.exception("Failed to add content to IPFS")
            # Emit error event
            await emit_event(
                Event(
                    event_type=EventType.PROTOCOL_ERROR.value,
                    data={
                        "protocol_type": "ipfs",
                        "error": str(e),
                        "timestamp": time.time(),
                    },
                ),
            )
            return ""
        except Exception as e:  # pragma: no cover - Generic error handler
            self.logger.exception("Unexpected error adding content to IPFS")
            # Emit error event
            await emit_event(
                Event(
                    event_type=EventType.PROTOCOL_ERROR.value,
                    data={
                        "protocol_type": "ipfs",
                        "error": str(e),
                        "timestamp": time.time(),
                    },
                ),
            )
            return ""

    async def get_content(self, cid: str) -> bytes | None:
        """Get content from IPFS by CID.

        First tries to retrieve from IPFS daemon, then falls back to peer-based retrieval.
        """
        if not self._ipfs_connected or self._ipfs_client is None:
            self.logger.warning("IPFS daemon not connected, cannot retrieve content")
            return None

        # First, try daemon retrieval (faster if content is local)
        try:
            content_data = await to_thread(
                lambda: self._ipfs_client.cat(cid)  # type: ignore[arg-type]
            )

            if content_data:
                # Verify CID integrity
                if self._verify_cid_integrity(content_data, cid):
                    # Update content tracking
                    if cid in self.ipfs_content:
                        content = self.ipfs_content[cid]
                        content.last_accessed = time.time()
                    else:
                        ipfs_content = IPFSContent(
                            cid=cid,
                            size=len(content_data),
                            blocks=[],
                            links=[],
                            last_accessed=time.time(),
                        )
                        self.ipfs_content[cid] = ipfs_content

                    # Emit content retrieved event
                    await emit_event(
                        Event(
                            event_type=EventType.IPFS_CONTENT_RETRIEVED.value,
                            data={
                                "cid": cid,
                                "size": len(content_data),
                                "timestamp": time.time(),
                            },
                        ),
                    )

                    self.logger.info(
                        "Retrieved content from IPFS daemon with CID %s", cid
                    )
                    return content_data
                self.logger.warning("CID verification failed for %s", cid)

        except ipfshttpclient.exceptions.Error as e:
            self.logger.debug(
                "Daemon retrieval failed for CID %s, trying peers: %s", cid, e
            )
        except Exception as e:  # pragma: no cover - Generic error handler
            self.logger.debug("Error in daemon retrieval: %s", e)

        # Fallback: peer-based retrieval
        try:
            self.logger.info("Attempting peer-based retrieval for CID %s", cid)

            # Find peers that have this content
            content_peers = await self._find_content_peers(cid)

            if not content_peers:
                self.logger.warning("No peers found with content for CID %s", cid)
                return None

            # Request blocks from peers
            # For now, request the root CID as a single block
            # In a full implementation, we'd need to get the DAG structure first
            requested_blocks = await self._request_blocks_from_peers(
                [cid], content_peers
            )

            if cid not in requested_blocks:
                self.logger.warning("Failed to retrieve block %s from peers", cid)
                return None

            # Reconstruct content (for simple cases, block is the content)
            content_data = requested_blocks[cid]

            # Verify CID integrity
            if not self._verify_cid_integrity(content_data, cid):
                self.logger.warning(
                    "CID verification failed for peer-retrieved content %s", cid
                )
                return None

            # Update content tracking
            if cid in self.ipfs_content:
                content = self.ipfs_content[cid]
                content.last_accessed = time.time()
            else:
                ipfs_content = IPFSContent(
                    cid=cid,
                    size=len(content_data),
                    blocks=[],
                    links=[],
                    last_accessed=time.time(),
                )
                self.ipfs_content[cid] = ipfs_content

            # Emit content retrieved event
            await emit_event(
                Event(
                    event_type=EventType.IPFS_CONTENT_RETRIEVED.value,
                    data={
                        "cid": cid,
                        "size": len(content_data),
                        "timestamp": time.time(),
                    },
                ),
            )

            self.logger.info("Retrieved content from peers with CID %s", cid)
            return content_data

        except Exception as e:  # pragma: no cover - Generic error handler
            self.logger.exception("Error in peer-based retrieval for CID %s", cid)
            # Emit error event
            await emit_event(
                Event(
                    event_type=EventType.PROTOCOL_ERROR.value,
                    data={
                        "protocol_type": "ipfs",
                        "error": str(e),
                        "timestamp": time.time(),
                    },
                ),
            )
            return None

    async def _request_blocks_from_peers(
        self, cids: list[str], peers: list[str]
    ) -> dict[str, bytes]:
        """Request blocks from IPFS peers using Bitswap protocol.

        Args:
            cids: List of CIDs to request
            peers: List of peer IDs to request from

        Returns:
            Dictionary mapping CID to block data (only successfully retrieved blocks)

        """
        if not cids or not peers:
            return {}

        if not self._ipfs_connected or self._ipfs_client is None:
            self.logger.warning("IPFS daemon not connected, cannot request blocks")
            return {}

        blocks: dict[str, bytes] = {}
        max_retries = 3
        timeout_per_block = 30  # seconds

        # Request blocks from peers in parallel
        async def request_from_peer(peer_id: str, cid: str) -> tuple[str, bytes | None]:
            """Request a single block from a peer."""
            for attempt in range(max_retries):
                try:
                    # Send Bitswap want_list message
                    want_list = [cid]
                    empty_message = b""
                    success = await self.send_message(
                        peer_id, empty_message, want_list=want_list
                    )

                    if not success:
                        self.logger.warning(
                            "Failed to send want_list to peer %s for CID %s (attempt %d/%d)",
                            peer_id,
                            cid,
                            attempt + 1,
                            max_retries,
                        )
                        await asyncio.sleep(1 * (attempt + 1))  # Exponential backoff
                        continue

                    # Wait for block response
                    start_time = time.time()
                    while time.time() - start_time < timeout_per_block:
                        # Check if peer has the block by trying to receive
                        response = await self.receive_message(peer_id)
                        if response:
                            # Parse Bitswap response
                            parsed = self._parse_bitswap_message(response)
                            if cid in parsed.get("blocks", {}):
                                return (cid, parsed["blocks"][cid])
                        await asyncio.sleep(0.5)  # Poll interval

                    # Timeout waiting for block
                    self.logger.warning(
                        "Timeout waiting for block %s from peer %s (attempt %d/%d)",
                        cid,
                        peer_id,
                        attempt + 1,
                        max_retries,
                    )

                except Exception as e:
                    self.logger.warning(
                        "Error requesting block %s from peer %s (attempt %d/%d): %s",
                        cid,
                        peer_id,
                        attempt + 1,
                        max_retries,
                        e,
                    )
                    await asyncio.sleep(1 * (attempt + 1))

            return (cid, None)

        # Request all blocks from all peers in parallel
        tasks = [request_from_peer(peer_id, cid) for cid in cids for peer_id in peers]

        # Wait for all requests to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        for result in results:
            if isinstance(result, BaseException):
                self.logger.warning("Exception in block request: %s", result)
                continue

            if not isinstance(result, tuple) or len(result) != 2:
                self.logger.warning("Unexpected result format: %s", result)
                continue

            cid, block_data = result
            if block_data is not None and cid not in blocks:
                blocks[cid] = block_data

        self.logger.info("Retrieved %d/%d blocks from peers", len(blocks), len(cids))
        return blocks

    async def _reconstruct_content_from_blocks(
        self, blocks: dict[str, bytes], dag_structure: dict[str, Any] | None = None
    ) -> bytes:
        """Reconstruct content from IPFS blocks following DAG structure.

        Args:
            blocks: Dictionary mapping CID to block data
            dag_structure: Optional DAG structure dict (if None, will fetch from IPFS)

        Returns:
            Reconstructed content as bytes

        """
        if not blocks:
            return b""

        if not self._ipfs_connected or self._ipfs_client is None:
            msg = "IPFS daemon not connected"
            raise ConnectionError(msg)

        try:
            # If DAG structure not provided, we need to reconstruct from blocks directly
            # For a simple case, we can concatenate blocks in order
            # For complex DAGs, we'd need to follow links

            if dag_structure is None:
                # Simple reconstruction: concatenate blocks in CID order
                # This works for simple linear DAGs
                # For complex DAGs, we'd need to fetch DAG structure first
                sorted_blocks = sorted(blocks.items())
                return b"".join(block_data for _, block_data in sorted_blocks)

            # Follow DAG structure to reconstruct content
            # Get root object if needed
            root_cid = dag_structure.get("root_cid")
            if root_cid:
                # Get object structure
                try:
                    obj_data = await to_thread(
                        self._ipfs_client.object.get,  # type: ignore[attr-defined]
                        root_cid,
                    )

                    # Parse object to get links
                    links = dag_structure.get("links", [])
                    if not links and isinstance(obj_data, dict):
                        links = obj_data.get("Links", [])

                    # Ensure links is iterable
                    if not isinstance(links, (list, tuple)):
                        links = []

                    # Reconstruct by following links in order
                    content_parts: list[bytes] = []
                    for link in links:
                        if isinstance(link, dict):
                            link_cid = link.get("Hash", "")
                        else:
                            link_cid = str(link)

                        if link_cid and link_cid in blocks:
                            content_parts.append(blocks[link_cid])
                        else:
                            self.logger.warning(
                                "Missing block %s in reconstruction", link_cid
                            )

                    return b"".join(content_parts)
                except Exception as e:
                    self.logger.warning("Error getting DAG structure: %s", e)
                    # Fallback to simple concatenation
                    return b"".join(blocks.values())

            # Fallback: concatenate all blocks
            return b"".join(blocks.values())

        except Exception:
            self.logger.exception("Error reconstructing content from blocks")
            raise

    def _verify_cid_integrity(self, data: bytes, expected_cid: str) -> bool:
        """Verify that data matches expected CID.

        Args:
            data: Data bytes to verify
            expected_cid: Expected CID string

        Returns:
            True if CID matches, False otherwise

        """
        try:
            # Regenerate CID from data using IPFS client if available
            if self._ipfs_connected and self._ipfs_client is not None:
                # Use IPFS client to add data and get CID
                # This is synchronous but we're in a sync method
                try:
                    result = self._ipfs_client.add_bytes(data, cid_version=1)
                    if isinstance(result, dict):
                        actual_cid = result.get("Hash", "")
                    else:
                        actual_cid = str(result)

                    # Compare CIDs
                    return actual_cid == expected_cid
                except Exception as e:
                    self.logger.warning("Failed to verify CID using IPFS client: %s", e)

            # Fallback: hash-based verification
            # For CID v1, we can't easily regenerate without IPFS
            # So we'll use a simple hash check as fallback
            data_hash = hashlib.sha256(data).hexdigest()

            # Simple check: if expected_cid contains the hash (basic validation)
            # This is not perfect but works as a fallback
            if expected_cid and data_hash:
                # Check if hash appears in CID (basic integrity check)
                return data_hash[:32] in expected_cid or expected_cid[:32] in data_hash

            return False

        except Exception as e:
            self.logger.warning("Error verifying CID integrity: %s", e)
            return False

    async def pin_content(self, cid: str) -> bool:
        """Pin content in IPFS."""
        if not self._ipfs_connected or self._ipfs_client is None:
            self.logger.warning("IPFS daemon not connected, cannot pin content")
            return False

        try:
            # Pin content in IPFS daemon
            await to_thread(
                self._ipfs_client.pin.add,  # type: ignore[attr-defined]
                cid,
            )

            # Track pinned CID
            self._pinned_cids.add(cid)

            # Emit content pinned event
            await emit_event(
                Event(
                    event_type=EventType.IPFS_CONTENT_PINNED.value,
                    data={
                        "cid": cid,
                        "timestamp": time.time(),
                    },
                ),
            )

            self.logger.info("Pinned content with CID %s", cid)
            return True

        except ipfshttpclient.exceptions.Error as e:
            self.logger.warning("Failed to pin content with CID %s: %s", cid, e)
            # Emit error event
            await emit_event(
                Event(
                    event_type=EventType.PROTOCOL_ERROR.value,
                    data={
                        "protocol_type": "ipfs",
                        "error": str(e),
                        "timestamp": time.time(),
                    },
                ),
            )
            return False
        except Exception as e:  # pragma: no cover - Generic error handler
            self.logger.exception("Unexpected error pinning content")
            # Emit error event
            await emit_event(
                Event(
                    event_type=EventType.PROTOCOL_ERROR.value,
                    data={
                        "protocol_type": "ipfs",
                        "error": str(e),
                        "timestamp": time.time(),
                    },
                ),
            )
            return False

    async def unpin_content(self, cid: str) -> bool:
        """Unpin content from IPFS."""
        if not self._ipfs_connected or self._ipfs_client is None:
            self.logger.warning("IPFS daemon not connected, cannot unpin content")
            return False

        try:
            # Unpin content from IPFS daemon
            await to_thread(
                self._ipfs_client.pin.rm,  # type: ignore[attr-defined]
                cid,
            )

            # Remove from pinned tracking
            self._pinned_cids.discard(cid)

            # Emit content unpinned event
            await emit_event(
                Event(
                    event_type=EventType.IPFS_CONTENT_UNPINNED.value,
                    data={
                        "cid": cid,
                        "timestamp": time.time(),
                    },
                ),
            )

            self.logger.info("Unpinned content with CID %s", cid)
            return True

        except ipfshttpclient.exceptions.Error as e:
            self.logger.warning("Failed to unpin content with CID %s: %s", cid, e)
            # Emit error event
            await emit_event(
                Event(
                    event_type=EventType.PROTOCOL_ERROR.value,
                    data={
                        "protocol_type": "ipfs",
                        "error": str(e),
                        "timestamp": time.time(),
                    },
                ),
            )
            return False
        except Exception as e:  # pragma: no cover - Generic error handler
            self.logger.exception("Unexpected error unpinning content")
            # Emit error event
            await emit_event(
                Event(
                    event_type=EventType.PROTOCOL_ERROR.value,
                    data={
                        "protocol_type": "ipfs",
                        "error": str(e),
                        "timestamp": time.time(),
                    },
                ),
            )
            return False

    def add_gateway(self, gateway_url: str) -> None:
        """Add IPFS gateway."""
        if gateway_url not in self.ipfs_gateway_urls:
            self.ipfs_gateway_urls.append(gateway_url)

    def remove_gateway(self, gateway_url: str) -> None:
        """Remove IPFS gateway."""
        if gateway_url in self.ipfs_gateway_urls:
            self.ipfs_gateway_urls.remove(gateway_url)

    def get_ipfs_peers(self) -> dict[str, IPFSPeer]:
        """Get IPFS peers."""
        return self.ipfs_peers.copy()

    def get_ipfs_content(self) -> dict[str, IPFSContent]:
        """Get IPFS content."""
        return self.ipfs_content.copy()

    def get_content_stats(self, cid: str) -> dict[str, Any] | None:
        """Get content statistics."""
        if cid not in self.ipfs_content:
            return None

        content = self.ipfs_content[cid]

        return {
            "cid": cid,
            "size": content.size,
            "blocks_count": len(content.blocks),
            "links_count": len(content.links),
            "last_accessed": content.last_accessed,
        }

    def get_all_content_stats(self) -> dict[str, dict[str, Any]]:
        """Get statistics for all content."""
        stats = {}

        for cid, content in self.ipfs_content.items():
            stats[cid] = {
                "size": content.size,
                "blocks_count": len(content.blocks),
                "links_count": len(content.links),
                "last_accessed": content.last_accessed,
            }

        return stats
