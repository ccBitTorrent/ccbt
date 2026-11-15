"""XetTransport: peer-facing XET chunk exchange over BEP 10.

Owns the peer registry, handshake/suite admission, authorization
checks, bounded in-flight chunk requests with timeouts, and metrics.
Wire encoding lives in ccbt.extensions.xet (v2 formats); this service
is the only supported way to exchange chunks between peers. Responses
are correlated by (peer, request_id) and verified against the chunk
hash before being delivered to callers.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Optional

from ccbt.extensions.xet import XetExtension, XetMessageType

logger = logging.getLogger(__name__)

SendCallable = Callable[[str, bytes], Awaitable[bool]]
AuthCheck = Callable[[str, Optional[str]], bool]


@dataclass
class PeerState:
    """Public class."""

    peer_id: str
    suite_ok: bool = False
    connected_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)


@dataclass
class TransportMetrics:
    """Public class."""

    requests_sent: int = 0
    requests_timed_out: int = 0
    responses_ok: int = 0
    responses_invalid: int = 0
    not_found: int = 0
    chunks_served: int = 0
    requests_rejected_inflight: int = 0
    messages_dropped_unauthorized: int = 0


class XetTransport:
    """Request/response chunk exchange with registered peers."""

    def __init__(
        self,
        extension: Optional[XetExtension] = None,
        send: Optional[SendCallable] = None,
        *,
        max_inflight_per_peer: int = 32,
        request_timeout: float = 30.0,
        auth_check: Optional[AuthCheck] = None,
    ) -> None:
        """Initialize instance."""
        if max_inflight_per_peer < 1:
            msg = "max_inflight_per_peer must be >= 1"
            raise ValueError(msg)
        self.extension = extension or XetExtension()
        self._send = send
        self.max_inflight_per_peer = max_inflight_per_peer
        self.request_timeout = request_timeout
        self.auth_check = auth_check
        self.peers: dict[str, PeerState] = {}
        self.metrics = TransportMetrics()
        self._pending: dict[
            tuple[str, int], tuple[asyncio.Future[Optional[bytes]], bytes]
        ] = {}
        self._inflight: dict[str, int] = {}
        # Optional push-inbound queue for discovery-coordinator receive_message.
        self.inbound_queue: dict[str, list[bytes]] = {}
        self._raft_handlers: dict[
            int, Callable[[str, bytes], Awaitable[Optional[bytes]]]
        ] = {}

    # ------------------------------------------------------------ peers
    def set_sender(self, send: SendCallable) -> None:
        """Public method."""
        self._send = send

    def has_sender(self) -> bool:
        """Return True when a wire sender callback is attached."""
        return self._send is not None

    async def send(self, peer_id: str, message: bytes) -> bool:
        """Send raw extension bytes via the attached sender callback."""
        if self._send is None:
            return False
        return await self._send(peer_id, message)

    def set_raft_handler(
        self,
        msg_type: int,
        handler: Callable[[str, bytes], Awaitable[Optional[bytes]]],
    ) -> None:
        """Register a Raft/consensus message handler (message-type -> coro)."""
        self._raft_handlers[msg_type] = handler

    def clear_raft_handler(
        self,
        msg_type: int,
        handler: Optional[Callable[[str, bytes], Awaitable[Optional[bytes]]]] = None,
    ) -> None:
        """Remove a Raft handler; if ``handler`` is set, only when it matches."""
        current = self._raft_handlers.get(msg_type)
        if current is None:
            return
        if handler is not None and current is not handler:
            return
        self._raft_handlers.pop(msg_type, None)

    def enqueue_inbound(self, peer_id: str, payload: bytes) -> None:
        """Queue an inbound payload for polling via receive_message."""
        self.inbound_queue.setdefault(peer_id, []).append(payload)

    def set_chunk_provider(self, provider: Callable[[bytes], Optional[bytes]]) -> None:
        """Public method."""
        self.extension.set_chunk_provider(provider)

    def register_peer(self, peer_id: str, handshake_data: dict) -> bool:
        """Admit a peer based on its extension handshake (+ auth hook)."""
        if not self.extension.decode_handshake(peer_id, handshake_data):
            return False
        if self.auth_check is not None and not self.auth_check(peer_id, None):
            return False
        self.peers[peer_id] = PeerState(peer_id=peer_id, suite_ok=True)
        return True

    def unregister_peer(self, peer_id: str) -> None:
        """Public method."""
        self.peers.pop(peer_id, None)
        for key in [k for k in self._pending if k[0] == peer_id]:
            future, _h = self._pending.pop(key)
            if not future.done():
                future.set_result(None)

    def is_registered(self, peer_id: str) -> bool:
        """Public method."""
        return peer_id in self.peers

    # ----------------------------------------------------------- client
    async def request_chunk(
        self, peer_id: str, chunk_hash: bytes, timeout: Optional[float] = None
    ) -> Optional[bytes]:
        """Fetch one chunk from a peer; None on not-found/timeout/error."""
        if peer_id not in self.peers:
            return None
        if self._send is None:
            return None
        if self._inflight.get(peer_id, 0) >= self.max_inflight_per_peer:
            self.metrics.requests_rejected_inflight += 1
            return None
        request_id, message = self.extension.encode_chunk_request_tracked(
            peer_id, chunk_hash
        )
        loop = asyncio.get_running_loop()
        future: asyncio.Future[Optional[bytes]] = loop.create_future()
        self._pending[(peer_id, request_id)] = (future, chunk_hash)
        self._inflight[peer_id] = self._inflight.get(peer_id, 0) + 1
        self.metrics.requests_sent += 1
        try:
            if not await self._send(peer_id, message):
                return None
            return await asyncio.wait_for(
                future, timeout=timeout or self.request_timeout
            )
        except asyncio.TimeoutError:
            self.metrics.requests_timed_out += 1
            return None
        finally:
            self._pending.pop((peer_id, request_id), None)
            self.extension.drop_outgoing_request(peer_id, request_id)
            self._inflight[peer_id] = max(0, self._inflight.get(peer_id, 1) - 1)

    # ----------------------------------------------------------- server
    async def handle_message(self, peer_id: str, payload: bytes) -> Optional[bytes]:
        """Dispatch one inbound extension payload; returns reply bytes or None."""
        if not payload:
            return None
        msg_type = payload[0]
        state = self.peers.get(peer_id)
        if state is not None:
            state.last_activity = time.time()

        if msg_type == XetMessageType.CHUNK_REQUEST:
            if self.auth_check is not None and not self.auth_check(peer_id, None):
                self.metrics.messages_dropped_unauthorized += 1
                return None
            try:
                request_id, chunk_hash = self.extension.decode_chunk_request(payload)
            except ValueError:
                return None
            response = await self.extension.handle_chunk_request(
                peer_id, request_id, chunk_hash
            )
            if response and response[0] == XetMessageType.CHUNK_RESPONSE:
                self.metrics.chunks_served += 1
            return response

        if msg_type == XetMessageType.CHUNK_RESPONSE:
            try:
                request_id, resp_hash, data = self.extension.decode_chunk_response(
                    payload
                )
            except ValueError:
                self.metrics.responses_invalid += 1
                return None
            entry = self._pending.get((peer_id, request_id))
            ok = await self.extension.handle_chunk_response(
                peer_id, request_id, resp_hash, data
            )
            if entry is not None and not entry[0].done():
                if ok:
                    self.metrics.responses_ok += 1
                    entry[0].set_result(data)
                else:
                    self.metrics.responses_invalid += 1
                    entry[0].set_result(None)
            return None

        if msg_type == XetMessageType.CHUNK_NOT_FOUND:
            try:
                request_id, _hash = self.extension.decode_chunk_not_found(payload)
            except ValueError:
                return None
            self.metrics.not_found += 1
            entry = self._pending.get((peer_id, request_id))
            if entry is not None and not entry[0].done():
                entry[0].set_result(None)
            return None

        if msg_type == XetMessageType.CHUNK_ERROR:
            try:
                request_id, _hash, _code, _msg = self.extension.decode_chunk_error(
                    payload
                )
            except ValueError:
                return None
            entry = self._pending.get((peer_id, request_id))
            if entry is not None and not entry[0].done():
                entry[0].set_result(None)
            return None

        raft_handler = self._raft_handlers.get(msg_type)
        if raft_handler is not None:
            return await raft_handler(peer_id, payload)

        # Other message families (folder sync, gossip, consensus) are
        # handled by the extension manager dispatcher / sync manager.
        self.enqueue_inbound(peer_id, payload)
        return None


def ensure_xet_discovery_graph(session: Any) -> None:
    """Initialize the shared XET discovery graph once per session manager.

    Extracted from SessionManager so session keeps only lifecycle calls.
    Mechanisms that are config-disabled are still constructed but not started;
    enable flags are read from ``session.config.xet_sync`` when present.
    """
    from ccbt.discovery.flooding import ControlledFlooding
    from ccbt.discovery.lpd import LocalPeerDiscovery
    from ccbt.discovery.pex import AsyncPexManager
    from ccbt.discovery.xet_bloom import XetChunkBloomFilter
    from ccbt.discovery.xet_cas import P2PCASClient
    from ccbt.discovery.xet_catalog import XetChunkCatalog
    from ccbt.discovery.xet_gossip import XetGossipManager
    from ccbt.discovery.xet_multicast import XetMulticastBroadcaster

    sync_cfg = getattr(getattr(session, "config", None), "xet_sync", None)

    if getattr(session, "xet_catalog", None) is None:
        session.xet_catalog = XetChunkCatalog()
    if getattr(session, "xet_bloom_filter", None) is None:
        session.xet_bloom_filter = XetChunkBloomFilter()
    if getattr(session, "pex_manager", None) is None:
        session.pex_manager = AsyncPexManager()

    enable_lpd = (
        True if sync_cfg is None else bool(getattr(sync_cfg, "enable_lpd", False))
    )
    enable_multicast = (
        True if sync_cfg is None else bool(getattr(sync_cfg, "enable_multicast", False))
    )
    enable_gossip = (
        True if sync_cfg is None else bool(getattr(sync_cfg, "enable_gossip", False))
    )
    enable_flooding = (
        True if sync_cfg is None else bool(getattr(sync_cfg, "enable_flooding", False))
    )

    if enable_lpd and getattr(session, "xet_lpd_client", None) is None:
        net = getattr(session.config, "network", None)
        xet_port = getattr(net, "xet_port", None) or getattr(net, "listen_port", 6881)
        session.xet_lpd_client = LocalPeerDiscovery(listen_port=xet_port)
    if enable_multicast and getattr(session, "xet_multicast_broadcaster", None) is None:
        net = getattr(session.config, "network", None)
        session.xet_multicast_broadcaster = XetMulticastBroadcaster(
            multicast_address=getattr(net, "xet_multicast_address", "239.192.152.143"),
            multicast_port=getattr(net, "xet_multicast_port", 6771),
        )
    build_node_id = getattr(session, "_build_xet_node_id", None)
    default_node_id = "ccbt-xet"
    if enable_gossip and getattr(session, "xet_gossip_manager", None) is None:
        node_id = build_node_id() if callable(build_node_id) else default_node_id
        session.xet_gossip_manager = XetGossipManager(node_id=str(node_id))
    if enable_flooding and getattr(session, "xet_flooding_client", None) is None:
        node_id = build_node_id() if callable(build_node_id) else default_node_id
        session.xet_flooding_client = ControlledFlooding(node_id=str(node_id))

    if getattr(session, "xet_cas_client", None) is None:
        session.xet_cas_client = P2PCASClient(
            dht_client=getattr(session, "dht_client", None),
            tracker_client=getattr(session, "udp_tracker_client", None),
            key_manager=getattr(session, "key_manager", None),
            bloom_filter=session.xet_bloom_filter,
            catalog=session.xet_catalog,
            extension_manager=getattr(session, "extension_manager", None),
        )
    if session.pex_manager is not None and session.xet_cas_client is not None:
        session.xet_cas_client.register_pex_manager(session.pex_manager)
    if session.xet_cas_client is not None:
        authorizer = getattr(session, "_is_xet_peer_authorized", None)
        if callable(authorizer):
            session.xet_cas_client.set_peer_authorizer(authorizer)
        notifier = getattr(session, "_mark_xet_discovery_success", None)
        if callable(notifier):
            session.xet_cas_client.set_discovery_backend_success_notifier(notifier)
    if getattr(session, "xet_lpd_client", None) is not None:
        lpd_cb = getattr(session, "_on_lpd_peer_discovered", None)
        if callable(lpd_cb):
            session.xet_lpd_client.peer_callback = lpd_cb
    if getattr(session, "xet_multicast_broadcaster", None) is not None:
        chunk_cb = getattr(session, "_on_xet_multicast_chunk", None)
        if callable(chunk_cb):
            session.xet_multicast_broadcaster.chunk_callback = chunk_cb
        update_cb = getattr(session, "_on_xet_multicast_update", None)
        if callable(update_cb):
            session.xet_multicast_broadcaster.update_callback = update_cb
    if getattr(session, "xet_gossip_manager", None) is not None:
        chunk_cb = getattr(session, "_on_xet_multicast_chunk", None)
        if callable(chunk_cb):
            session.xet_gossip_manager.chunk_callbacks.append(chunk_cb)
        update_cb = getattr(session, "_on_xet_multicast_update", None)
        if callable(update_cb):
            session.xet_gossip_manager.folder_callbacks.append(update_cb)
    update_status = getattr(session, "_update_xet_discovery_status", None)
    if callable(update_status):
        update_status()
